"""HTTP surface for Sixty Days: read, route, gather evidence, and hold the clock."""

from __future__ import annotations

import json
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from spine.clock import ClockState
from sixty_days.deadline import Case, Contact, DeadlineKeeper
from sixty_days.evidence import EvidenceChecker
from sixty_days.letters import plan_requirements
from sixty_days.outreach import RequestPreparer
from sixty_days.packet import PacketBuilder, PacketRenderer
from sixty_days.reader import LetterExtractionError, LetterReader, LetterReplayClient
from sixty_days.store import CaseStore

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
SCANS = FIXTURES / "letter_scans"
RECORDINGS = FIXTURES / "letter_recordings"
EVIDENCE_SCANS = FIXTURES / "evidence_scans"
EVIDENCE_RECORDINGS = FIXTURES / "evidence_recordings"


class OpenCaseRequest(BaseModel):
    fixture: str
    applicant_ref: str = Field(
        default="DEMO-APPLICATION", min_length=1, max_length=40,
        pattern=r"^DEMO-[A-Za-z0-9._-]+$",
    )
    disaster_ref: str = Field(
        default="DR-DEMO", min_length=1, max_length=40,
        pattern=r"^DR-DEMO(?:-[A-Za-z0-9._-]+)?$",
    )


class DemoPresetRequest(BaseModel):
    fixture: str


class ChaseRequest(BaseModel):
    requirement_key: str
    requested_on: date


class EvidenceCheckRequest(BaseModel):
    fixture: str
    requirement_key: str


class PreparedRequestRequest(BaseModel):
    requirement_key: str
    requested_on: date


class PacketRequest(BaseModel):
    applicant_statement: str = ""


def _safe_name(name: str) -> str:
    safe = "".join(char for char in name if char.isalnum() or char == "_")
    if safe != name or not safe:
        raise HTTPException(status_code=400, detail="invalid fixture name")
    return safe


def build_sixty_days_router(client, clock, scheduler, runner) -> APIRouter:
    router = APIRouter(prefix="/sixty-days", tags=["sixty-days"])
    cases = CaseStore(client)

    def require_case(case_id: str) -> dict[str, Any]:
        found = cases.get(case_id)
        if found is None or found.get("tenant_id") is not None:
            raise HTTPException(status_code=404, detail=f"no case {case_id}")
        return found

    def require_requirement(found: dict[str, Any], key: str) -> dict[str, Any]:
        match = next(
            (item for item in found.get("requirements", []) if item.get("key") == key),
            None,
        )
        if match is None:
            raise HTTPException(status_code=422, detail=f"case does not require {key}")
        return match

    @router.get("/fixtures")
    def list_fixtures() -> dict[str, Any]:
        names = sorted(
            path.stem
            for path in RECORDINGS.glob("*.json")
            if not path.stem.startswith("_")
            and (SCANS / f"{path.stem}.jpg").exists()
            and (SCANS / f"{path.stem}.txt").exists()
        )
        report_path = RECORDINGS / "_accuracy_report.json"
        report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else []
        return {
            "fixtures": names,
            "measured": {
                "correct": sum(row.get("correct", 0) for row in report),
                "total": sum(row.get("total", 0) for row in report),
                "recorded_calls": len([row for row in report if "error" not in row]),
            },
            "note": "Live Gemini 3.5 Flash outputs, graded against adjacent synthetic truth.",
        }

    @router.get("/fixtures/{name}")
    def get_fixture(name: str) -> dict[str, Any]:
        safe = _safe_name(name)
        recording = RECORDINGS / f"{safe}.json"
        truth = SCANS / f"{safe}.truth.json"
        if not recording.exists() or not truth.exists():
            raise HTTPException(status_code=404, detail=f"no complete recording for {safe}")
        return {
            "name": safe,
            "extraction": json.loads(recording.read_text(encoding="utf-8")),
            "truth": json.loads(truth.read_text(encoding="utf-8")),
            "image_url": f"/sixty-days/fixtures/{safe}/image",
        }

    @router.get("/fixtures/{name}/image")
    def get_fixture_image(name: str) -> FileResponse:
        safe = _safe_name(name)
        image = SCANS / f"{safe}.jpg"
        if not image.exists():
            raise HTTPException(status_code=404, detail=f"no letter image for {safe}")
        return FileResponse(image, media_type="image/jpeg")

    @router.get("/evidence/fixtures")
    def list_evidence_fixtures() -> dict[str, Any]:
        names = sorted(
            path.stem
            for path in EVIDENCE_RECORDINGS.glob("*.json")
            if not path.stem.startswith("_")
            and (EVIDENCE_SCANS / f"{path.stem}.png").exists()
        )
        report_path = EVIDENCE_RECORDINGS / "_accuracy_report.json"
        report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else []
        return {
            "fixtures": names,
            "measured": {
                "correct": sum(row.get("correct", 0) for row in report),
                "total": sum(row.get("total", 0) for row in report),
                "recorded_calls": len([row for row in report if "error" not in row]),
            },
            "note": (
                "Recorded Gemini image screening on clearly synthetic fixtures. "
                "Results concern observable framing only."
            ),
        }

    @router.get("/evidence/fixtures/{name}/image")
    def get_evidence_fixture_image(name: str) -> FileResponse:
        safe = _safe_name(name)
        image = EVIDENCE_SCANS / f"{safe}.png"
        if not image.exists():
            raise HTTPException(status_code=404, detail=f"no evidence image for {safe}")
        return FileResponse(image, media_type="image/png")

    @router.post("/demo/anchor")
    def preset_demo_clock(request: DemoPresetRequest) -> dict[str, Any]:
        """Anchor the labelled demo clock to the selected synthetic letter.

        Fixture dates are fixed evidence. Without this explicit demo-only anchor, a rehearsal
        would change as wall time advances and eventually begin with several wakes already due.
        No case or audit data is deleted.
        """
        name = _safe_name(request.fixture)
        recording_path = RECORDINGS / f"{name}.json"
        if not recording_path.exists():
            raise HTTPException(status_code=404, detail=f"no complete recording for {name}")
        extraction = json.loads(recording_path.read_text(encoding="utf-8"))
        start = datetime.combine(
            date.fromisoformat(extraction["letter_date"]),
            time(9, 0),
            tzinfo=timezone.utc,
        )
        simulated = clock
        if not getattr(simulated, "simulated", False):
            raise HTTPException(status_code=409, detail="demo preset requires simulation mode")
        simulated._store.write(ClockState(frozen_at=start))
        return {
            "fixture": name,
            "simulated_now": simulated.now().isoformat(),
            "deleted_cases": 0,
            "label": "Synthetic demo clock anchored to the selected letter date.",
        }

    @router.post("/cases")
    def open_case(request: OpenCaseRequest) -> dict[str, Any]:
        name = _safe_name(request.fixture)
        recording_path = RECORDINGS / f"{name}.json"
        transcript_path = SCANS / f"{name}.txt"
        if not recording_path.exists() or not transcript_path.exists():
            raise HTTPException(status_code=404, detail=f"no complete recording for {name}")
        extraction = json.loads(recording_path.read_text(encoding="utf-8"))
        reader = LetterReader(LetterReplayClient({"default": extraction}))
        try:
            result = reader.parse(
                artifact_id=f"letter_{name}",
                document=transcript_path.read_text(encoding="utf-8"),
            )
        except LetterExtractionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        run_id = runner().start(
            "sixty-days", "appeal-case", {"fixture": name, "applicant": request.applicant_ref}
        )
        case = Case(
            case_id=f"case_{name}_{run_id[-8:]}",
            run_id=run_id,
            letter_date=result.letter.letter_date,
            deadline=result.letter.deadline,
        )
        keeper = DeadlineKeeper(scheduler())
        registered = keeper.open_case(case)
        requirements = plan_requirements(result.letter.deficiencies)
        cases.save(case, request.applicant_ref, request.disaster_ref, result.letter, requirements)
        return {
            "case_id": case.case_id,
            "application_ref": request.applicant_ref,
            "disaster_ref": request.disaster_ref,
            "run_id": run_id,
            "determination": result.letter.determination.value,
            "letter_date": case.letter_date.isoformat(),
            "deadline": case.deadline.isoformat(),
            "deadline_conflict": result.letter.deadline_conflict,
            "days_in_window": (case.deadline - case.letter_date).days,
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
                    "day": wake.payload["day"],
                    "why": DeadlineKeeper.explain(Contact(wake.kind)),
                }
                for wake in registered
            ],
            "dropped": result.dropped,
            "redacted": result.redacted_count,
            "quarantined": len(result.quarantined),
            "safety": "Draft and organize only. The applicant reviews and submits; not legal advice.",
        }

    @router.get("/cases")
    def list_cases() -> dict[str, Any]:
        return {"cases": [item for item in cases.all() if item.get("tenant_id") is None]}

    @router.get("/cases/{case_id}")
    def get_case(case_id: str) -> dict[str, Any]:
        return require_case(case_id)

    @router.post("/cases/{case_id}/evidence/check")
    def check_evidence(case_id: str, request: EvidenceCheckRequest) -> dict[str, Any]:
        found = require_case(case_id)
        require_requirement(found, request.requirement_key)
        fixture = _safe_name(request.fixture)
        recording_path = EVIDENCE_RECORDINGS / f"{fixture}.json"
        image_path = EVIDENCE_SCANS / f"{fixture}.png"
        if not recording_path.exists() or not image_path.exists():
            raise HTTPException(status_code=404, detail=f"no complete evidence fixture {fixture}")
        recorded = json.loads(recording_path.read_text(encoding="utf-8"))
        result = EvidenceChecker().check(
            request.requirement_key,
            artifact_id=f"evidence_{fixture}",
            response=recorded,
        )
        body = result.as_dict()
        cases.record_evidence(case_id, body, fixture)
        return body

    @router.post("/cases/{case_id}/requests/prepare")
    def prepare_request(case_id: str, request: PreparedRequestRequest) -> dict[str, Any]:
        found = require_case(case_id)
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
    def build_packet(case_id: str, request: PacketRequest) -> dict[str, Any]:
        packet = PacketBuilder().build(require_case(case_id), request.applicant_statement)
        cases.record_packet(case_id, packet.status, packet.missing)
        return packet.as_dict()

    @router.post("/cases/{case_id}/packet.pdf")
    def build_packet_pdf(case_id: str, request: PacketRequest) -> Response:
        packet = PacketBuilder().build(require_case(case_id), request.applicant_statement)
        image_paths = {
            item.artifact_id: EVIDENCE_SCANS / f"{item.fixture}.png"
            for item in packet.evidence
            if item.fixture
        }
        raw = PacketRenderer().render(packet, image_paths)
        cases.record_packet(case_id, packet.status, packet.missing)
        return Response(
            raw,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="draft-appeal-{case_id}.pdf"',
                "X-Submission-Status": "not-submitted",
            },
        )

    @router.post("/cases/{case_id}/chase")
    def chase(case_id: str, request: ChaseRequest) -> dict[str, Any]:
        found = require_case(case_id)
        requirement = require_requirement(found, request.requirement_key)
        if requirement.get("source") not in {"third_party", "public_record"}:
            raise HTTPException(status_code=422, detail="only an applicant-sent records request can be tracked")
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
        return {"wake_id": wake.wake_id, "kind": wake.kind, "due_at": wake.due_at.isoformat()}

    @router.get("/conformance")
    def conformance() -> dict[str, Any]:
        appeals_source = (
            "https://www.fema.gov/sites/default/files/documents/"
            "fema_ia-quick-reference_appeals.pdf"
        )
        tips_source = "https://www.fema.gov/fact-sheet/8-tips-appealing-femas-decision-1"
        ihp_source = (
            "https://www.fema.gov/fact-sheet/"
            "fema-individuals-and-households-program-application-eligibility-"
            "registration-and-appeals"
        )
        return {
            "standard": "Current FEMA public Individual Assistance appeals guidance",
            "rules": [
                {
                    "rule": "An appeal is due within 60 days of the determination letter date.",
                    "source": appeals_source,
                    "implementation": "sixty_days/letters.py: Letter.deadline",
                    "test": "tests/test_letters.py::test_default_deadline_is_letter_date_plus_sixty_days",
                },
                {
                    "rule": (
                        "The decision letter identifies the reason and documents that may help; "
                        "the evidence plan is selected from that letter's quoted reason."
                    ),
                    "source": tips_source,
                    "implementation": "sixty_days/letters.py: REQUIREMENTS, plan_requirements",
                    "test": "tests/test_letters.py::test_every_deficiency_has_a_concrete_route",
                },
                {
                    "rule": (
                        "Evidence-image automation screens observable framing only and never "
                        "predicts authenticity, legal sufficiency, or agency acceptance."
                    ),
                    "source": tips_source,
                    "implementation": "sixty_days/evidence.py: EvidenceChecker",
                    "test": (
                        "tests/test_evidence.py::"
                        "test_good_wide_damage_photo_is_ready_for_applicant_review_not_declared_valid"
                    ),
                },
                {
                    "rule": (
                        "Third-party records requests are prepared and tracked, but the applicant "
                        "reviews and sends them."
                    ),
                    "source": tips_source,
                    "implementation": "sixty_days/outreach.py: RequestPreparer",
                    "test": "tests/test_outreach.py::test_third_party_request_is_prepared_for_applicant_and_never_sent",
                },
                {
                    "rule": (
                        "A system-authored statement about the decision reproduces an exact quote "
                        "from that decision letter."
                    ),
                    "source": tips_source,
                    "implementation": "sixty_days/packet.py: DecisionLetterVerifier",
                    "test": "tests/test_packet.py::test_regulatory_paraphrase_is_rejected_even_when_it_cites_a_real_quote",
                },
                {
                    "rule": (
                        "The draft repeats the synthetic application and disaster references "
                        "in the footer of every PDF page for applicant verification."
                    ),
                    "source": ihp_source,
                    "implementation": "sixty_days/packet.py: PacketRenderer.footer",
                    "test": (
                        "tests/test_packet.py::"
                        "test_pdf_is_parseable_labeled_draft_and_page_numbered"
                    ),
                },
                {
                    "rule": "The system never submits on the applicant's behalf.",
                    "source": appeals_source,
                    "implementation": "No submission endpoint exists; packet work remains draft-only.",
                    "test": (
                        "tests/test_sixty_days_routes.py::"
                        "test_router_exposes_no_bulk_delete_or_submission_endpoint"
                    ),
                },
            ],
            "safety": [
                "Synthetic data only; fixtures carry no agency marks.",
                "Not legal advice and no prediction of appeal outcome.",
                "Every extracted reason must quote the applicant's own letter.",
                "A separate appeal letter or form is optional under the cited current guidance; "
                "the PDF is an organizing draft, not a required agency form.",
            ],
        }

    return router
