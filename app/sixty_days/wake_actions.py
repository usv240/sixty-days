"""Typed actions executed when a Sixty Days wake becomes due.

The scheduler is transport. This module owns domain meaning. A due wake must do more than prove that
time passed, and more than leave a note saying somebody ought to do something: where the case
contains enough to decide, the wake decides and the work is done when nobody is watching.

Two wakes complete real work rather than describing it. The packet safeguard assembles a reviewable
draft from whatever has been accepted. The reply check reroutes a failing evidence request: it
notices that a third party never answered, weighs the time left against how long another
organisation would take to reply, chooses a different route to the same requirement, and drafts the
new request ready for the applicant to read.

The boundary is unchanged by any of it. Rerouting changes how a requirement is satisfied, never what
the letter asked for, and deciding to write a different letter is not permission to send it.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sixty_days.deadline import Case, Contact, DeadlineKeeper
from sixty_days.outreach import RequestPreparer
from sixty_days.packet import PacketBuilder
from sixty_days.lifecycle import evaluate
from sixty_days.replan import decide
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


def _field(case: Any, name: str) -> Any:
    """Cases arrive as a Firestore dict here and as an object in tests; read either."""
    if isinstance(case, dict):
        return case.get(name)
    return getattr(case, name, None)


class DeadlineActionExecutor:
    """Resolve a claimed wake into one idempotent case action."""

    def __init__(self, cases, now=None, keeper: DeadlineKeeper | None = None) -> None:
        self._cases = cases
        # With a keeper the loop closes: a changed route gets its own follow-up check, and a case
        # that is finished cancels what is left instead of continuing to nag.
        self._keeper = keeper
        # The demo runs on a simulated clock and the beta API on the wall clock. Deciding how much
        # time a case has left from real "now" would be wrong in the demo by however far it has
        # been advanced, so the caller passes the clock that owns this wake.
        self._now = now

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
            result = self._reroute(case_id, case, requirement)
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
        outcome = self._converge(case, result, wake.wake_id)
        if outcome is not None:
            recorded["lifecycle"] = outcome
        self._cases.record_due_action(case_id, recorded)
        return recorded

    def _rearm(self, case: Any, requirement_key: str) -> bool:
        """Give the replacement request its own follow-up check, capped by the deadline."""
        if self._keeper is None:
            return False
        tracked = self._as_case(case)
        if tracked is None:
            return False
        try:
            self._keeper.chase_third_party(tracked, requirement_key, self._today())
        except ValueError:
            # Past the deadline a new check would be noise, not diligence.
            return False
        return True

    def _converge(self, case: Any, action: dict[str, Any], wake_id: str) -> dict[str, Any] | None:
        """Stop when the letter's requirements are met, exhausted, or out of time.

        A fixed ladder that keeps firing after the work is done is not autonomy, it is an alarm
        clock nobody can switch off.
        """
        required = self._required(case)
        if not required:
            return None

        # The action that just ran is not in the stored case yet: it is written after this.
        # Without folding it in, a case that becomes exhausted on this very wake is only noticed
        # on the next one, and if this was the last wake it is never noticed at all.
        outcome = evaluate(
            required,
            self._satisfied(case),
            today=self._today(),
            deadline=self._deadline(case),
            exhausted_keys=self._exhausted(case) + self._exhausted_by(action),
        )
        if not outcome.terminal:
            return outcome.as_dict()

        cancelled = 0
        tracked = self._as_case(case)
        if self._keeper is not None and tracked is not None:
            cancelled = self._keeper.close(tracked, outcome.reason, except_wake_id=wake_id)
        payload = outcome.as_dict()
        payload["cancelled_reminders"] = cancelled
        return payload

    @staticmethod
    def _required(case: Any) -> tuple[str, ...]:
        requirements = _field(case, "requirements") or []
        keys: list[str] = []
        for item in requirements if isinstance(requirements, list) else []:
            key = item.get("key") if isinstance(item, dict) else getattr(item, "key", None)
            if key:
                keys.append(str(key))
        return tuple(keys)

    def _exhausted(self, case: Any) -> tuple[str, ...]:
        """Requirements a previous wake already found no remaining route for."""
        keys: list[str] = []
        for action in _field(case, "due_actions") or []:
            if not isinstance(action, dict):
                continue
            plan = action.get("replan")
            if isinstance(plan, dict) and plan.get("handoff") == "legal_aid":
                key = str(plan.get("failed_key", ""))
                if key:
                    keys.append(key)
        return tuple(keys)

    @staticmethod
    def _exhausted_by(action: dict[str, Any]) -> tuple[str, ...]:
        """A requirement this action just found no remaining route for."""
        plan = action.get("replan")
        if isinstance(plan, dict) and plan.get("handoff") == "legal_aid":
            key = str(plan.get("failed_key", ""))
            if key:
                return (key,)
        return ()

    @staticmethod
    def _deadline(case: Any):
        value = _field(case, "deadline")
        if not value:
            return None
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None

    def _as_case(self, case: Any) -> Case | None:
        """The keeper works on a Case; stored cases arrive as plain dictionaries."""
        case_id = _field(case, "case_id")
        run_id = _field(case, "run_id")
        letter_date = _field(case, "letter_date")
        deadline = self._deadline(case)
        if not (case_id and run_id and letter_date and deadline):
            return None
        try:
            start = date.fromisoformat(str(letter_date)[:10])
        except ValueError:
            return None
        return Case(case_id=str(case_id), run_id=str(run_id), letter_date=start, deadline=deadline)

    def _reroute(self, case_id: str, case: Any, requirement_key: str) -> dict[str, Any]:
        """Nobody replied. Choose a different way to satisfy the same requirement, and draft it.

        This is the step that separates an agent from a reminder. The applicant is not told that
        their insurer has gone quiet and left to work out what to do about it three weeks before a
        deadline; the route is changed, the replacement request is written, and the reasoning is
        recorded in the letter's own terms.
        """
        decision = decide(
            requirement_key,
            days_left=self._days_left(case),
            satisfied_keys=self._satisfied(case),
        )

        if not decision.changed:
            return {
                "action": "third_party_reply_check_due",
                "detail": decision.reason,
                "requirement": requirement_key,
                "replan": decision.as_dict(),
            }

        drafted = None
        rearmed = False
        if decision.needs_request:
            # Written, not sent. The applicant reads it and decides, exactly as before.
            try:
                prepared = RequestPreparer().prepare(
                    {
                        "key": decision.alternative_key,
                        "title": decision.alternative_title,
                        "routed_to": decision.alternative_routed_to,
                        "source": decision.alternative_source,
                    },
                    self._today(),
                )
                drafted = prepared.as_dict()
                self._cases.record_prepared_request(case_id, drafted)
                # The new route is now the thing that can go unanswered, so it gets its own
                # follow-up. Without this the agent reroutes once and then stops watching, which
                # is the failure it was built to prevent.
                rearmed = self._rearm(case, decision.alternative_key)
            except Exception:  # noqa: BLE001 - a failed draft must not lose the routing decision
                drafted = None

        return {
            "action": "evidence_route_changed",
            "detail": decision.reason,
            "requirement": requirement_key,
            "replan": decision.as_dict(),
            "drafted_request": bool(drafted),
            "follow_up_scheduled": bool(rearmed),
        }

    def _days_left(self, case: Any) -> int | None:
        deadline = _field(case, "deadline")
        if not deadline:
            return None
        try:
            due = date.fromisoformat(str(deadline)[:10])
        except ValueError:
            return None
        return (due - self._today()).days

    def _today(self) -> date:
        if self._now is None:
            return datetime.now(timezone.utc).date()
        moment = self._now() if callable(self._now) else self._now
        return moment.date() if hasattr(moment, "date") else moment

    @staticmethod
    def _satisfied(case: Any) -> tuple[str, ...]:
        """Requirement keys already covered by accepted evidence or a received record."""
        evidence = _field(case, "evidence") or []
        keys: list[str] = []
        for item in evidence if isinstance(evidence, list) else []:
            if not isinstance(item, dict):
                continue
            key = str(item.get("requirement_key") or item.get("requirement") or "")
            decision = str(item.get("decision", ""))
            if key and decision in {"ready_for_review", "accepted"}:
                keys.append(key)
        return tuple(keys)
