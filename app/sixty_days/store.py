"""Firestore persistence for long-lived appeal cases.

Only structured, pseudonymized facts are retained. The PII-dense transcription and the model's
raw response deliberately do not enter this store.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sixty_days.deadline import Case
from sixty_days.letters import Letter, Requirement

CASES_COLLECTION = "sixty_day_cases"


class CaseStore:
    def __init__(self, client) -> None:
        self._collection = client.collection(CASES_COLLECTION)

    def save(
        self,
        case: Case,
        applicant_ref: str,
        disaster_ref: str,
        letter: Letter,
        requirements: list[Requirement],
    ) -> None:
        self._collection.document(case.case_id).set(
            {
                "run_id": case.run_id,
                "applicant_ref": applicant_ref,
                "disaster_ref": disaster_ref,
                "letter_date": case.letter_date.isoformat(),
                "deadline": case.deadline.isoformat(),
                "determination": letter.determination.value,
                "deadline_conflict": letter.deadline_conflict,
                "deficiencies": [
                    {
                        "kind": item.kind.value,
                        "plain_language": item.plain_language,
                        "quoted_text": item.quote.text,
                    }
                    for item in letter.deficiencies
                ],
                "requirements": [
                    {
                        "key": item.key,
                        "title": item.title,
                        "plain_description": item.plain_description,
                        "source": item.source.value,
                        "routed_to": item.routed_to,
                        "cures": item.cures.value,
                        "status": "pending",
                    }
                    for item in requirements
                ],
                "status": "gathering",
                "created_at": datetime.now(timezone.utc),
            }
        )

    def get(self, case_id: str) -> dict | None:
        snapshot = self._collection.document(case_id).get()
        return {"case_id": case_id, **(snapshot.to_dict() or {})} if snapshot.exists else None

    def all(self) -> list[dict]:
        return [{"case_id": doc.id, **(doc.to_dict() or {})} for doc in self._collection.stream()]

    def record_evidence(self, case_id: str, result: dict[str, Any], fixture: str) -> dict:
        def change(data: dict) -> None:
            evidence = [
                item for item in data.get("evidence", [])
                if item.get("requirement_key") != result["requirement_key"]
            ]
            evidence.append({
                "requirement_key": result["requirement_key"],
                "artifact_id": result["artifact_id"],
                "decision": result["decision"],
                "checks": result["checks"],
                "guidance": result["guidance"],
                "model": result["model"],
                "recorded": result["recorded"],
                "fixture": fixture,
                "screened_at": datetime.now(timezone.utc).isoformat(),
            })
            data["evidence"] = evidence
            for requirement in data.get("requirements", []):
                if requirement["key"] == result["requirement_key"]:
                    requirement["status"] = result["decision"]

        return self._mutate(case_id, change)

    def record_prepared_request(self, case_id: str, prepared: dict[str, Any]) -> dict:
        def change(data: dict) -> None:
            requests = [
                item for item in data.get("prepared_requests", [])
                if item.get("requirement_key") != prepared["requirement_key"]
            ]
            requests.append(prepared)
            data["prepared_requests"] = requests

        return self._mutate(case_id, change)

    def record_packet(self, case_id: str, status: str, missing: list[str]) -> dict:
        def change(data: dict) -> None:
            data["packet"] = {
                "status": status,
                "missing": list(missing),
                "built_at": datetime.now(timezone.utc).isoformat(),
                "applicant_statement_persisted": False,
            }

        return self._mutate(case_id, change)

    def record_due_action(self, case_id: str, action: dict[str, Any]) -> dict:
        """Upsert a due action by wake id so a retry cannot duplicate visible work."""

        def change(data: dict) -> None:
            actions = [
                item for item in data.get("due_actions", [])
                if item.get("wake_id") != action["wake_id"]
            ]
            actions.append(dict(action))
            data["due_actions"] = actions

        return self._mutate(case_id, change)

    def _mutate(self, case_id: str, change) -> dict:
        document = self._collection.document(case_id)
        snapshot = document.get()
        if not snapshot.exists:
            raise KeyError(case_id)
        data = snapshot.to_dict() or {}
        change(data)
        document.set(data)
        return {"case_id": case_id, **data}
