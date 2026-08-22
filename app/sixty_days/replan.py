"""Change the plan when a route stops working, instead of repeating a request that failed.

A scheduler that wakes up and writes "someone should replan" has not replanned. It has produced a
reminder with extra steps, and the applicant is still the one who has to notice the insurer never
wrote back, work out that a different document would satisfy the same requirement, and start again
with three weeks left.

This module makes that decision instead. When a request to a third party has gone unanswered, or
when the calendar no longer leaves enough time for one to come back, it picks a different route to
the *same* deficiency and says why, in the letter's own terms.

Three rules keep the autonomy honest:

* **It only ever changes the route, never the requirement.** The deficiency comes from the decision
  letter, quoted word for word. Nothing here can invent, drop, or soften what the letter asked for.
* **It prefers routes the applicant controls**, because the failure being handled is precisely that
  someone else is not responding. Waiting harder on the same silent party is not a plan.
* **It refuses rather than guesses.** With no alternative route for a deficiency, it says so and
  hands over to the legal-aid path. A confident wrong answer here costs a survivor their deadline.

Nothing in this module contacts anyone. Choosing to write a different letter is not permission to
send it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sixty_days.letters import REQUIREMENTS, Requirement, Source

#: Below this, a request that depends on someone else replying is not a plan, it is a hope.
#: FEMA's own appeal guidance gives sixty days in total; two weeks is the point at which posting a
#: request to a third party and waiting for a reply stops being a responsible use of the remaining
#: time, so the applicant-controlled route is preferred even when the third party might still answer.
THIRD_PARTY_TURNAROUND_DAYS = 14


@dataclass(frozen=True)
class ReplanDecision:
    """What the agent decided to do about a failing route, and why."""

    changed: bool
    deficiency: str
    failed_key: str
    failed_title: str = ""
    alternative_key: str = ""
    alternative_title: str = ""
    alternative_routed_to: str = ""
    alternative_source: str = ""
    reason: str = ""
    days_left: int | None = None
    needs_request: bool = False
    handoff: str = ""
    considered: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "changed": self.changed,
            "deficiency": self.deficiency,
            "failed_key": self.failed_key,
            "failed_title": self.failed_title,
            "alternative_key": self.alternative_key,
            "alternative_title": self.alternative_title,
            "alternative_routed_to": self.alternative_routed_to,
            "alternative_source": self.alternative_source,
            "reason": self.reason,
            "days_left": self.days_left,
            "needs_request": self.needs_request,
            "handoff": self.handoff,
            "considered": list(self.considered),
        }


def _catalogue() -> dict[str, tuple[Requirement, str]]:
    """Every requirement by key, with the deficiency it cures."""
    index: dict[str, tuple[Requirement, str]] = {}
    for deficiency, requirements in REQUIREMENTS.items():
        for requirement in requirements:
            index[requirement.key] = (requirement, deficiency.value)
    return index


def alternatives_for(failed_key: str) -> list[Requirement]:
    """Other ways to satisfy the same deficiency, best route first.

    Ordered by who has to act: the applicant, then a public record, then another third party. The
    request that just failed is excluded, because repeating it is the behaviour this replaces.
    """
    index = _catalogue()
    entry = index.get(failed_key)
    if entry is None:
        return []
    _, deficiency_value = entry

    preference = {
        Source.APPLICANT_ONLY: 0,
        Source.PUBLIC_RECORD: 1,
        Source.THIRD_PARTY: 2,
        Source.LEGAL_AID: 3,
    }
    siblings = [
        requirement
        for key, (requirement, value) in index.items()
        if value == deficiency_value and key != failed_key
    ]
    return sorted(siblings, key=lambda r: preference[r.source])


def decide(
    failed_key: str,
    *,
    days_left: int | None = None,
    satisfied_keys: tuple[str, ...] = (),
) -> ReplanDecision:
    """Pick a different route to the same deficiency, or refuse and hand over.

    `days_left` is the time to the appeal deadline. It is what turns this from a lookup into a
    judgement: with three weeks in hand another third-party request is reasonable, and with five
    days it is not.
    """
    index = _catalogue()
    entry = index.get(failed_key)
    if entry is None:
        return ReplanDecision(
            changed=False,
            deficiency="unknown",
            failed_key=failed_key,
            reason="This requirement is not in the routed plan, so there is nothing to reroute.",
            days_left=days_left,
        )

    failed, deficiency_value = entry

    if failed_key in satisfied_keys:
        return ReplanDecision(
            changed=False,
            deficiency=deficiency_value,
            failed_key=failed_key,
            failed_title=failed.title,
            reason="This record already arrived, so the route did not need changing.",
            days_left=days_left,
        )

    options = alternatives_for(failed_key)
    considered = [r.key for r in options]

    for option in options:
        if option.key in satisfied_keys:
            return ReplanDecision(
                changed=False,
                deficiency=deficiency_value,
                failed_key=failed_key,
                failed_title=failed.title,
                alternative_key=option.key,
                alternative_title=option.title,
                alternative_routed_to=option.routed_to,
                alternative_source=option.source.value,
                reason=(
                    f"No new request is needed: {option.title.lower()} already covers the same "
                    "requirement from the letter."
                ),
                days_left=days_left,
                considered=considered,
            )

        # With little time left, another route that depends on someone else replying is not a plan.
        tight = days_left is not None and days_left <= THIRD_PARTY_TURNAROUND_DAYS
        if tight and option.source is Source.THIRD_PARTY:
            continue

        if tight:
            why = (
                f"{days_left} days remain, which is too few to rely on another organisation "
                f"replying, so the route moved to something you control: {option.title.lower()}."
            )
        else:
            why = (
                f"The request to the {failed.routed_to} has gone unanswered, so the route moved to "
                f"{option.title.lower()} instead of asking the same party again."
            )

        return ReplanDecision(
            changed=True,
            deficiency=deficiency_value,
            failed_key=failed_key,
            failed_title=failed.title,
            alternative_key=option.key,
            alternative_title=option.title,
            alternative_routed_to=option.routed_to,
            alternative_source=option.source.value,
            reason=why,
            days_left=days_left,
            needs_request=option.source is not Source.APPLICANT_ONLY,
            considered=considered,
        )

    return ReplanDecision(
        changed=False,
        deficiency=deficiency_value,
        failed_key=failed_key,
        failed_title=failed.title,
        reason=(
            "The letter asks for this specific record and there is no other route to it, so "
            "guessing an alternative would be worse than saying so."
        ),
        days_left=days_left,
        handoff="legal_aid",
        considered=considered,
    )
