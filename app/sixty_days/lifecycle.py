"""Decide when the case is finished, and stop.

Registering a fixed ladder of reminders is easy. Knowing when to stop is the part that decides
whether this is an agent or an alarm clock, and getting it wrong is not symmetric:

* Stopping too early abandons someone mid-appeal with a deadline still running.
* Stopping too late means a survivor who already gathered everything keeps being told what is
  missing, until the product feels like one more thing shouting at them.

So the loop is closed here rather than left open. After every action the case is evaluated against
the letter's own requirements, and it reaches exactly one of four states. Three of them are terminal
and cancel the remaining reminders; the fourth keeps working.

Nothing in this module contacts anyone or judges the appeal. "Resolved" means the documents the
letter asked for have been gathered, never that the appeal will succeed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any


class State(StrEnum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    DEADLINE_PASSED = "deadline_passed"
    EXHAUSTED = "exhausted"


@dataclass(frozen=True)
class Outcome:
    state: State
    reason: str
    satisfied: tuple[str, ...] = ()
    outstanding: tuple[str, ...] = ()
    days_left: int | None = None

    @property
    def terminal(self) -> bool:
        return self.state is not State.ACTIVE

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "reason": self.reason,
            "satisfied": list(self.satisfied),
            "outstanding": list(self.outstanding),
            "days_left": self.days_left,
            "terminal": self.terminal,
        }


def evaluate(
    required_keys: tuple[str, ...],
    satisfied_keys: tuple[str, ...],
    *,
    today: date,
    deadline: date | None,
    exhausted_keys: tuple[str, ...] = (),
) -> Outcome:
    """Where the case stands, and whether there is any reason to keep working on it.

    `exhausted_keys` are requirements with no remaining route -- the insurer's own decision letter,
    for example, which nothing else can substitute for. They are counted as closed for the purpose
    of stopping, because continuing to chase something that has no route left is not persistence.
    """
    required = tuple(dict.fromkeys(required_keys))
    satisfied = tuple(k for k in required if k in set(satisfied_keys))
    closed = set(satisfied_keys) | set(exhausted_keys)
    outstanding = tuple(k for k in required if k not in closed)
    days_left = (deadline - today).days if deadline else None

    if required and not outstanding:
        if satisfied and len(satisfied) == len(required):
            reason = (
                "Every document the letter asked for has been gathered. Nothing further is "
                "scheduled; you decide what to do with the draft."
            )
        else:
            reason = (
                "Everything the letter asked for is either gathered or has no route left to "
                "chase, so there is nothing useful left to schedule."
            )
        state = State.RESOLVED if satisfied and len(satisfied) == len(required) else State.EXHAUSTED
        return Outcome(state, reason, satisfied, outstanding, days_left)

    if deadline is not None and days_left is not None and days_left < 0:
        return Outcome(
            State.DEADLINE_PASSED,
            (
                "The 60-day window has closed, so no further reminders are scheduled. The draft "
                "and everything gathered stay available to you. A late appeal can still be "
                "accepted for good cause, so a disaster legal-aid service is worth asking before "
                "you treat this as over."
            ),
            satisfied,
            outstanding,
            days_left,
        )

    return Outcome(
        State.ACTIVE,
        f"{len(outstanding)} of {len(required)} item(s) still outstanding.",
        satisfied,
        outstanding,
        days_left,
    )
