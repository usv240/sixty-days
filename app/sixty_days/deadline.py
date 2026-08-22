"""The Deadline Keeper: holding a 60 day clock on behalf of someone who cannot.

This is the whole product. FEMA generally requires an Individual Assistance appeal within 60 days
of the date on the decision letter. A survivor in the aftermath of a disaster may have to gather
case-specific evidence from several sources while that clock runs, so the agent holds the schedule:
it registers every contact it will ever make at intake, then sleeps.

Design decisions that matter for the wake ladder:

* **Registered up front.** A crash between contacts cannot lose the rest of the schedule.
* **Deterministic ids.** Re-running registration after a restart is a no-op, so nobody in crisis
  gets contacted twice about the same thing.
* **Re-planning, not repetition.** If a requirement fails repeatedly the agent changes the ask
  rather than nagging for something the applicant evidently cannot get.
* **A partial packet before the deadline.** At day 52 it assembles whatever has been accepted, so
  an incomplete appeal exists rather than none at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from spine.wake import Wake, WakeScheduler


class Contact(StrEnum):
    UNDERSTOOD_CHECK = "understood_check"
    NUDGE = "nudge"
    REPLAN = "replan"
    ESCALATE = "escalate"
    BUILD_PARTIAL = "build_partial"
    FINAL_ALERT = "final_alert"


# (contact, days after the letter, what it is for). Escalating in directness, never in volume.
LADDER: tuple[tuple[Contact, int, str], ...] = (
    (Contact.UNDERSTOOD_CHECK, 3,
     "Did the plain language summary land? If it was never opened, explain it a different way."),
    (Contact.NUDGE, 7, "First reminder of what is still outstanding."),
    (Contact.NUDGE, 14, "Second reminder."),
    (Contact.NUDGE, 21,
     "Third reminder. Any third party request with no reply by now gets chased separately."),
    (Contact.REPLAN, 30,
     "Anything that has failed three times gets a different ask, not a fourth repeat."),
    (Contact.ESCALATE, 45,
     "Direct escalation, plus the offer of free legal aid."),
    (Contact.BUILD_PARTIAL, 52,
     "Assemble the appeal from whatever has been accepted, so a partial appeal exists."),
    (Contact.FINAL_ALERT, 58, "Final alert. Two days left."),
)

MAX_ATTEMPTS_BEFORE_REPLAN = 3
THIRD_PARTY_CHASE_DAYS = 21


@dataclass
class Case:
    case_id: str
    run_id: str
    letter_date: date
    deadline: date

    def day_of(self, when: date) -> int:
        return (when - self.letter_date).days

    def days_remaining(self, today: date) -> int:
        return (self.deadline - today).days


class DeadlineKeeper:
    def __init__(self, scheduler: WakeScheduler) -> None:
        self._scheduler = scheduler

    def open_case(self, case: Case) -> list[Wake]:
        """Register every contact at intake. Nothing is scheduled lazily."""
        from datetime import datetime, time, timezone

        if case.deadline < case.letter_date:
            raise ValueError("appeal deadline cannot be before the letter date")

        window_days = (case.deadline - case.letter_date).days
        registered: list[Wake] = []
        for contact, day, _why in LADDER:
            # The normal 60-day window lands these at days 52 and 58. If the letter states an
            # earlier deadline, keep the same safety margins instead of dropping the two most
            # important actions from the schedule entirely.
            effective_day = day
            if contact is Contact.BUILD_PARTIAL:
                effective_day = min(day, max(0, window_days - 8))
            elif contact is Contact.FINAL_ALERT:
                effective_day = min(day, max(0, window_days - 2))

            due_date = case.letter_date + timedelta(days=effective_day)
            if due_date > case.deadline:
                continue  # a contact after the deadline would be cruel and useless
            registered.append(
                self._scheduler.sleep_until(
                    run_id=case.run_id,
                    kind=contact.value,
                    due_at=datetime.combine(due_date, time(9, 0), tzinfo=timezone.utc),
                    payload={"case_id": case.case_id, "day": effective_day},
                    discriminator=f"{case.case_id}:{contact.value}:{effective_day}",
                )
            )
        return registered

    def chase_third_party(self, case: Case, requirement_key: str, requested_on: date) -> Wake:
        """A request sent to an insurer or a utility gets its own clock.

        Without this the case waits on a reply that may never come, and the deadline arrives with
        nothing gathered. If there is no reply by day 21, the plan changes around it.
        """
        from datetime import datetime, time, timezone

        if requested_on > case.deadline:
            raise ValueError("third party request cannot be created after the appeal deadline")
        due_date = requested_on + timedelta(days=THIRD_PARTY_CHASE_DAYS)
        return self._scheduler.sleep_until(
            run_id=case.run_id,
            kind=f"chase:{requirement_key}",
            due_at=datetime.combine(
                min(due_date, case.deadline), time(9, 0), tzinfo=timezone.utc
            ),
            payload={"case_id": case.case_id, "requirement": requirement_key},
            discriminator=f"{case.case_id}:chase:{requirement_key}",
        )

    def close(self, case: Case, reason: str, except_wake_id: str = "") -> int:
        """Appeal submitted, or the case resolved. Stop contacting them.

        When the decision to close is made from inside a running wake, that wake is excluded: it is
        not a remaining reminder, it is the one that just did its job.
        """
        return self._scheduler.cancel_run(case.run_id, reason, except_wake_id=except_wake_id)

    @staticmethod
    def explain(contact: Contact) -> str:
        for kind, _day, why in LADDER:
            if kind is contact:
                return why
        return ""

    @staticmethod
    def urgency(days_remaining: int) -> str:
        """Drives the UI. Text label, never colour alone."""
        if days_remaining <= 7:
            return "critical"
        if days_remaining <= 14:
            return "urgent"
        if days_remaining <= 30:
            return "attention"
        return "on track"
