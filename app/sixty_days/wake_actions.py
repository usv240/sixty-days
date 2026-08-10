"""Typed actions executed when a Sixty Days wake becomes due.

The scheduler is transport. This module owns domain meaning. A due wake must do more than prove
that time passed: it creates an idempotent, human-visible case action, and the day-52 wake builds
the partial packet metadata from the case as it exists at that moment. No action contacts a third
party or submits anything for the applicant.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sixty_days.deadline import Contact
from sixty_days.packet import PacketBuilder
from spine.wake import Wake


ACTION_BY_KIND = {
    Contact.UNDERSTOOD_CHECK.value: (
        "understanding_check_due",
        "Check whether the letter summary was understood; offer a clearer explanation if needed.",
    ),
    Contact.NUDGE.value: (
        "evidence_reminder_due",
        "Review the case for outstanding evidence and show the next incomplete item.",
    ),
    Contact.REPLAN.value: (
        "evidence_replan_due",
        "Change the evidence route after repeated failure instead of repeating the same request.",
    ),
    Contact.ESCALATE.value: (
        "legal_aid_offer_due",
        "Surface the free legal-aid option while preserving the applicant's decision authority.",
    ),
    Contact.FINAL_ALERT.value: (
        "final_deadline_alert_due",
        "Surface the final deadline alert and the current list of missing items.",
    ),
}


class DeadlineActionExecutor:
    """Resolve a claimed wake into one idempotent case action."""

    def __init__(self, cases) -> None:
        self._cases = cases

    def execute(self, wake: Wake) -> dict[str, Any]:
        case_id = str(wake.payload.get("case_id", ""))
        if not case_id:
            return {
                "action": "generic_wake_recorded",
                "detail": "The wake became due; it is not attached to a Sixty Days case.",
            }

        case = self._cases.get(case_id)
        if case is None:
            raise KeyError(f"wake {wake.wake_id} refers to missing case {case_id}")

        if wake.kind == Contact.BUILD_PARTIAL.value:
            packet = PacketBuilder().build(case)
            self._cases.record_packet(case_id, packet.status, packet.missing)
            result = {
                "action": "partial_packet_built",
                "detail": "A reviewable partial packet snapshot was built from accepted evidence.",
                "packet_status": packet.status,
                "missing": list(packet.missing),
            }
        elif wake.kind.startswith("chase:"):
            requirement = str(wake.payload.get("requirement", wake.kind.partition(":")[2]))
            result = {
                "action": "third_party_reply_check_due",
                "detail": "No reply is assumed. Replan around the missing record before the deadline.",
                "requirement": requirement,
            }
        else:
            action, detail = ACTION_BY_KIND.get(
                wake.kind,
                ("case_review_due", "Review the case because its scheduled work is now due."),
            )
            result = {"action": action, "detail": detail}

        recorded = {
            "wake_id": wake.wake_id,
            "kind": wake.kind,
            "due_at": wake.due_at.isoformat(),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "external_side_effect": False,
            **result,
        }
        self._cases.record_due_action(case_id, recorded)
        return recorded
