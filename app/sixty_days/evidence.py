"""Conservative screening for synthetic appeal-evidence fixtures.

This module never decides whether FEMA will accept evidence. It answers a narrower, observable
question: does the image contain the features the current evidence request asked the applicant to
show? A passing result is "ready for applicant review", not "valid" or "sufficient".

Model responses are record-once/replay-everywhere. Only booleans and non-identifying guidance are
retained; raw images, transcriptions, names, addresses and case numbers are not persisted here.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class EvidenceDecision(StrEnum):
    READY_FOR_REVIEW = "ready_for_review"
    RETAKE = "retake"
    MANUAL_REVIEW = "manual_review"


@dataclass(frozen=True)
class EvidenceResult:
    artifact_id: str
    requirement_key: str
    decision: EvidenceDecision
    checks: dict[str, bool | None]
    guidance: str
    model: str
    recorded: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "requirement_key": self.requirement_key,
            "decision": self.decision.value,
            "checks": self.checks,
            "guidance": self.guidance,
            "model": self.model,
            "recorded": self.recorded,
            "safety": (
                "Screening only. The applicant reviews every item; this does not predict whether "
                "an agency will accept it."
            ),
        }


REQUIRED_CHECKS: dict[str, tuple[str, ...]] = {
    "deed": ("legible", "applicant_name_visible", "address_visible",
             "applicant_match", "address_match"),
    "occupancy": ("legible", "applicant_name_visible", "address_visible",
                  "applicant_match", "address_match"),
    "insurance_denial": ("legible", "applicant_name_visible", "decision_visible",
                         "applicant_match"),
    "identity": ("legible", "applicant_name_visible", "applicant_match"),
    "photo_wide": ("damage_visible", "floor_and_wall_visible", "water_line_visible"),
    "photo_scale": ("damage_visible", "scale_visible"),
    "photo_exterior": ("exterior_visible", "house_number_visible"),
}

EVIDENCE_PROMPT = """You screen a disaster-evidence image for observable framing only.

Return only the requested boolean checks. True means the feature is plainly visible, false means
it is plainly absent, and null means the image is ambiguous. Do not identify a person, read or
return names, addresses, registration numbers, or other text. Do not decide authenticity,
eligibility, legal sufficiency, or whether an agency will accept the evidence.
"""

ACTIONABLE_GUIDANCE: dict[str, str] = {
    "legible": "Retake the page in brighter, even light and keep every edge in frame.",
    "applicant_name_visible": "Retake the page with the applicant-name line visible.",
    "address_visible": "Retake the page with the damaged-property address visible.",
    "applicant_match": "This appears to name someone else. Review it and upload the applicant's document.",
    "address_match": "This appears to show a different address. Upload a document for the damaged property.",
    "decision_visible": "Include the insurer's decision or settlement line in the frame.",
    "damage_visible": "Retake the photo with the damaged area clearly visible.",
    "floor_and_wall_visible": "Step back and include both the floor and wall for context.",
    "water_line_visible": "Retake the photo so the water line is visible in the frame.",
    "scale_visible": "Place a ruler or familiar object beside the damage and retake the photo.",
    "exterior_visible": "Step back and include the building exterior.",
    "house_number_visible": "Include the house number in the exterior photo.",
}


class EvidenceModelClient(ABC):
    @abstractmethod
    def inspect(self, image: bytes, requested_checks: tuple[str, ...]) -> dict[str, Any]: ...


class EvidenceReplayClient(EvidenceModelClient):
    def __init__(self, responses: dict[str, dict[str, Any]], key: str = "default") -> None:
        self._responses = responses
        self.key = key
        self.calls = 0

    def inspect(self, image: bytes, requested_checks: tuple[str, ...]) -> dict[str, Any]:
        self.calls += 1
        try:
            return self._responses[self.key]
        except KeyError as exc:
            raise ValueError(f"no recorded evidence response for {self.key!r}") from exc


class EvidenceVertexClient(EvidenceModelClient):
    def __init__(self, project: str, location: str, model: str = "gemini-3.5-flash") -> None:
        self._project = project
        self._location = location
        self._model = model

    def inspect(self, image: bytes, requested_checks: tuple[str, ...]) -> dict[str, Any]:
        from google import genai
        from google.genai import types

        client = genai.Client(vertexai=True, project=self._project, location=self._location)
        request = (
            "Inspect only these observable checks: "
            + ", ".join(requested_checks)
            + ". Return one value for each requested check."
        )
        schema = {
            "type": "object",
            "properties": {
                "checks": {
                    "type": "object",
                    "properties": {
                        key: {"type": "boolean", "nullable": True}
                        for key in requested_checks
                    },
                    "required": list(requested_checks),
                },
            },
            "required": ["checks"],
        }
        response = client.models.generate_content(
            model=self._model,
            contents=[types.Content(role="user", parts=[
                types.Part.from_bytes(data=image, mime_type="image/png"),
                types.Part.from_text(text=request),
            ])],
            config=types.GenerateContentConfig(
                system_instruction=EVIDENCE_PROMPT,
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.0,
            ),
        )
        try:
            parsed = json.loads(response.text)
        except (json.JSONDecodeError, AttributeError, TypeError) as exc:
            raise ValueError(f"model returned unparseable evidence JSON: {exc}") from exc
        return {"model": self._model, "recorded": False, **parsed}


class EvidenceChecker:
    def check(
        self,
        requirement_key: str,
        artifact_id: str,
        response: dict[str, Any],
    ) -> EvidenceResult:
        required = REQUIRED_CHECKS.get(requirement_key)
        if required is None:
            return EvidenceResult(
                artifact_id, requirement_key, EvidenceDecision.MANUAL_REVIEW, {},
                "This evidence type has no safe automated screening policy. Ask a caseworker to review it.",
                str(response.get("model", "unknown")), bool(response.get("recorded", False)),
            )

        raw_checks = response.get("checks")
        if not isinstance(raw_checks, dict):
            raw_checks = {}
        checks = {
            key: raw_checks.get(key) if isinstance(raw_checks.get(key), bool) else None
            for key in required
        }
        unknown = next((key for key in required if checks[key] is None), None)
        if unknown is not None:
            return EvidenceResult(
                artifact_id, requirement_key, EvidenceDecision.MANUAL_REVIEW, checks,
                f"The checker could not determine {unknown.replace('_', ' ')}. Ask a person to review the image.",
                str(response.get("model", "unknown")), bool(response.get("recorded", False)),
            )

        failed = next((key for key in required if checks[key] is False), None)
        if failed:
            return EvidenceResult(
                artifact_id, requirement_key, EvidenceDecision.RETAKE, checks,
                ACTIONABLE_GUIDANCE[failed], str(response.get("model", "unknown")),
                bool(response.get("recorded", False)),
            )
        return EvidenceResult(
            artifact_id, requirement_key, EvidenceDecision.READY_FOR_REVIEW, checks,
            "The requested features are visible. Review the image yourself before adding it to the draft packet.",
            str(response.get("model", "unknown")), bool(response.get("recorded", False)),
        )
