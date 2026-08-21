"""Authenticated API for de-identified Sixty Days letters and private case state."""

from __future__ import annotations

from datetime import date
from typing import Any, Callable, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from service.sixty_days_routes import PacketRequest, PreparedRequestRequest
from sixty_days.deadline import Case, Contact, DeadlineKeeper
from sixty_days.letters import plan_requirements
from sixty_days.outreach import RequestPreparer
from sixty_days.packet import PacketBuilder
from sixty_days.reader import (
    LetterExtractionError,
    LetterReader,
    LetterVertexClient,
)
from sixty_days.store import CaseStore
from spine.model_armor import ModelArmorScreen
from spine.api_access import ApiKeyAuthenticator, ApiPrincipal, require_scope
from spine.redact import GemmaReviewer, RedactionError, Redactor


class OpenBetaCaseRequest(BaseModel):
    # Same reasoning as KeyRequest: a silently dropped field reads as an accepted one.
    model_config = ConfigDict(extra="forbid")

    document: str = Field(min_length=40, max_length=30_000)
    applicant_ref: str = Field(
        min_length=3, max_length=40, pattern=r"^SUBJECT-[A-Za-z0-9._-]+$"
    )
    disaster_ref: str = Field(
        min_length=3, max_length=40, pattern=r"^DR-[A-Za-z0-9._-]+$"
    )
    acknowledge_deidentified: Literal[True]


def _reject_obvious_identifiers(document: str) -> None:
    found = Redactor().redact(document).replacements
    if found:
        kinds = sorted({item.kind for item in found})
        raise HTTPException(
            status_code=422,
            detail=(
                "The beta accepts de-identified text only. Remove these detected identifier "
                f"types before retrying: {', '.join(kinds)}."
            ),
        )


def build_beta_router(
    client,
    clock,
    scheduler,
    runner,
    auth: ApiKeyAuthenticator,
    *,
    reader_factory: Callable[[], LetterReader] | None = None,
    project_id: str = "",
    model_location: str = "global",
    armor_screen: ModelArmorScreen | None = None,
) -> APIRouter:
    # A disabled screen is the local and test default, and behaves exactly as before.
    armor_screen = armor_screen or ModelArmorScreen(project_id="", template="")

    router = APIRouter(prefix="/v1", tags=["beta-api"])
    cases = CaseStore(client)

    def reader() -> LetterReader:
        if reader_factory is not None:
            return reader_factory()
        return LetterReader(
            LetterVertexClient(project_id, model_location),
            reviewer=GemmaReviewer(project_id, model_location),
        )

    def authorize(principal: ApiPrincipal) -> None:
        require_scope(principal, "sixty-days:use")

    def require_case(case_id: str, principal: ApiPrincipal) -> dict[str, Any]:
        authorize(principal)
        found = cases.get_for_tenant(case_id, principal.tenant_id)
        if found is None:
            raise HTTPException(status_code=404, detail=f"no case {case_id}")
        return found

    def require_requirement(found: dict[str, Any], key: str) -> dict[str, Any]:
        item = next(
            (row for row in found.get("requirements", []) if row.get("key") == key), None
        )
        if item is None:
            raise HTTPException(status_code=422, detail=f"case does not require {key}")
        return item

    @router.get("")
    def api_info(principal: ApiPrincipal = Depends(auth)) -> dict[str, Any]:
        authorize(principal)
        return {
            "product": "Sixty Days",
            "api_version": "v1",
            "tenant": principal.tenant_id,
            "key_id": principal.key_id,
            "input": "De-identified determination-letter text only.",
            "retention": "Raw letter text and model response are not persisted.",
            "boundary": "Preparation only. No legal advice, outcome prediction, contact, or submission.",
        }

    @router.post("/cases", status_code=201)
    def open_case(
        request: OpenBetaCaseRequest,
        principal: ApiPrincipal = Depends(auth),
    ) -> dict[str, Any]:
        authorize(principal)
        _reject_obvious_identifiers(request.document)
        # Model Armor screens ahead of the deterministic layer, and can only make this stricter:
        # an unavailable screen hands the decision straight back to the checks below.
        armor = armor_screen.screen(request.document)
        if armor.blocked:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Model Armor flagged this text as a prompt-injection or jailbreak attempt. "
                    "The document was not sent to the model."
                ),
            )
        try:
            result = reader().parse(
                artifact_id=f"letter_{principal.key_id}", document=request.document
            )
        except RedactionError as exc:
            raise HTTPException(
                status_code=503,
                detail="Privacy review unavailable; the document was not processed.",
            ) from exc
        except LetterExtractionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        run_id = runner().start(
            "sixty-days-beta",
            "appeal-case",
            {"tenant": principal.tenant_id, "applicant": request.applicant_ref},
        )
        case = Case(
            case_id=f"case_{principal.key_id}_{run_id[-8:]}",
            run_id=run_id,
            letter_date=result.letter.letter_date,
            deadline=result.letter.deadline,
        )
        registered = DeadlineKeeper(scheduler()).open_case(case)
        requirements = plan_requirements(result.letter.deficiencies)
        cases.save(
            case,
            request.applicant_ref,
            request.disaster_ref,
            result.letter,
            requirements,
            tenant_id=principal.tenant_id,
        )
        return {
            "case_id": case.case_id,
            "application_ref": request.applicant_ref,
            "disaster_ref": request.disaster_ref,
            "determination": result.letter.determination.value,
            "letter_date": case.letter_date.isoformat(),
            "deadline": case.deadline.isoformat(),
            "deadline_conflict": result.letter.deadline_conflict,
            "deficiencies": [
                {
                    "kind": item.kind.value,
                    "plain_language": item.plain_language,
                    "quoted_text": item.quote.text,
                }
                for item in result.letter.deficiencies
            ],
            "requirements": [
                {
                    "key": item.key,
                    "title": item.title,
                    "source": item.source.value,
                    "routed_to": item.routed_to,
                    "plain_description": item.plain_description,
                }
                for item in requirements
            ],
            "wakes": [
                {
                    "kind": wake.kind,
                    "due_at": wake.due_at.isoformat(),
                    "why": DeadlineKeeper.explain(Contact(wake.kind)),
                }
                for wake in registered
            ],
            "dropped": result.dropped,
            "redacted": result.redacted_count,
            "raw_document_persisted": False,
            # Reported rather than merely acted on: a screen that silently passes is
            # indistinguishable from a screen that never ran.
            "model_armor": armor.as_dict(),
            "quarantined_lines": len(result.quarantined),
            "safety": "Draft and organize only. The applicant reviews and submits.",
        }

    @router.get("/cases")
    def list_cases(principal: ApiPrincipal = Depends(auth)) -> dict[str, Any]:
        authorize(principal)
        return {"cases": cases.all_for_tenant(principal.tenant_id)}

    @router.get("/cases/{case_id}")
    def get_case(
        case_id: str, principal: ApiPrincipal = Depends(auth)
    ) -> dict[str, Any]:
        return require_case(case_id, principal)

    @router.post("/cases/{case_id}/requests/prepare")
    def prepare_request(
        case_id: str,
        request: PreparedRequestRequest,
        principal: ApiPrincipal = Depends(auth),
    ) -> dict[str, Any]:
        found = require_case(case_id, principal)
        requirement = require_requirement(found, request.requirement_key)
        try:
            prepared = RequestPreparer().prepare(requirement, request.requested_on)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        case = Case(
            case_id=case_id,
            run_id=found["run_id"],
            letter_date=date.fromisoformat(found["letter_date"]),
            deadline=date.fromisoformat(found["deadline"]),
        )
        try:
            wake = DeadlineKeeper(scheduler()).chase_third_party(
                case, request.requirement_key, request.requested_on
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        body = prepared.as_dict()
        cases.record_prepared_request(case_id, body)
        return {
            **body,
            "tracking": {
                "wake_id": wake.wake_id,
                "due_at": wake.due_at.isoformat(),
                "if_no_reply": "Replan around the missing record; do not wait past the deadline.",
            },
        }

    @router.post("/cases/{case_id}/packet")
    def build_packet(
        case_id: str,
        request: PacketRequest,
        principal: ApiPrincipal = Depends(auth),
    ) -> dict[str, Any]:
        found = require_case(case_id, principal)
        packet = PacketBuilder().build(found, request.applicant_statement)
        cases.record_packet(case_id, packet.status, packet.missing)
        return packet.as_dict()

    return router
