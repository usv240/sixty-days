"""Reading a FEMA determination letter, and deciding what would actually cure it.

The documented friction is narrower and better supported: FEMA decisions are time-sensitive,
letters can identify case-specific missing evidence, and GAO found missing supporting evidence
among common historical ineligibility reasons. The product provides one translation and one
clock without predicting eligibility or an appeal outcome.

Two rules are load bearing:

1. **Nothing is extracted that cannot be quoted.** Every deficiency must quote the letter, which
   means the system structurally cannot invent a reason FEMA did not give.
2. **The deadline comes from the letter, never from arithmetic.** If the letter's stated date and
   letterDate plus 60 days disagree, the earlier date wins and both are shown. Getting a deadline
   wrong here would be worse than doing nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import StrEnum

APPEAL_WINDOW = timedelta(days=60)


class Determination(StrEnum):
    APPROVED = "approved"
    DENIED = "denied"
    PARTIAL = "partial"


class Deficiency(StrEnum):
    """What FEMA could not confirm. Drives everything downstream."""

    OWNERSHIP = "ownership"
    OCCUPANCY = "occupancy"
    DAMAGE_EVIDENCE = "damage_evidence"
    INSURANCE = "insurance"
    IDENTITY = "identity"
    LEGAL = "legal"  # not curable with documents; routes to legal aid
    OTHER = "other"


class Source(StrEnum):
    """Who can actually produce the evidence. This is the routing decision."""

    PUBLIC_RECORD = "public_record"
    THIRD_PARTY = "third_party"
    APPLICANT_ONLY = "applicant_only"
    LEGAL_AID = "legal_aid"


@dataclass(frozen=True)
class Quote:
    text: str

    def appears_in(self, document: str) -> bool:
        def collapse(text: str) -> str:
            return re.sub(r"\s+", " ", text).strip().casefold()

        needle = collapse(self.text)
        return bool(needle) and needle in collapse(document)


@dataclass(frozen=True)
class FoundDeficiency:
    kind: Deficiency
    plain_language: str
    quote: Quote


@dataclass(frozen=True)
class Requirement:
    """One concrete thing to obtain, and who should be asked for it."""

    key: str
    title: str
    plain_description: str
    source: Source
    routed_to: str
    cures: Deficiency


@dataclass
class Letter:
    letter_date: date
    determination: Determination
    deficiencies: list[FoundDeficiency] = field(default_factory=list)
    stated_deadline: date | None = None
    deadline_conflict: str | None = None
    def __post_init__(self) -> None:
        computed = self.letter_date + APPEAL_WINDOW
        if self.stated_deadline is not None and self.stated_deadline < self.letter_date:
            raise ValueError("stated deadline cannot be before the letter date")
        if (
            self.deadline_conflict is None
            and self.stated_deadline is not None
            and self.stated_deadline != computed
        ):
            self.deadline_conflict = (
                f"The letter states {self.stated_deadline.isoformat()}, while 60 days from the "
                f"letter date is {computed.isoformat()}. We use the earlier date."
            )


    @property
    def deadline(self) -> date:
        """The date we hold the applicant to.

        When the letter's own stated date and the 60 day rule disagree, take the earlier. A
        deadline that is too early costs an unnecessary week; one that is too late costs the
        entire appeal.
        """
        computed = self.letter_date + APPEAL_WINDOW
        if self.stated_deadline is None:
            return computed
        return min(self.stated_deadline, computed)

    def days_remaining(self, today: date) -> int:
        return (self.deadline - today).days


# What actually cures each deficiency, and who can produce it. Held as a versioned table rather
# than generated, so it is auditable and testable. Derived from FEMA's published guidance on what
# documentation supports an appeal. The ownership/occupancy examples come from FEMA's
# "Verifying Home Ownership or Occupancy" fact sheet; insurance examples come from the October
# 2024 "Help for Survivors with Insurance" quick reference. These are conservative routing
# examples, not a claim that any single document guarantees eligibility.
REQUIREMENTS: dict[Deficiency, tuple[Requirement, ...]] = {
    Deficiency.OWNERSHIP: (
        Requirement(
            key="deed",
            title="Proof you own the home",
            plain_description=(
                "A deed or property-tax record showing your name and the damaged address. FEMA "
                "also lists mortgage, title, insurance, will, and certain court records; review "
                "the decision letter before choosing an alternative."
            ),
            source=Source.PUBLIC_RECORD,
            routed_to="county recorder",
            cures=Deficiency.OWNERSHIP,
        ),
    ),
    Deficiency.OCCUPANCY: (
        Requirement(
            key="occupancy",
            title="Proof you were living there",
            plain_description=(
                "A lease, rent receipt, utility bill, pay stub, bank statement, state ID, or "
                "another FEMA-listed record showing the damaged address. FEMA's fact sheet says "
                "occupancy records should be dated within one year before the disaster."
            ),
            source=Source.THIRD_PARTY,
            routed_to="utility provider",
            cures=Deficiency.OCCUPANCY,
        ),
    ),
    Deficiency.DAMAGE_EVIDENCE: (
        Requirement(
            key="repair_record",
            title="Repair estimate, bill, or receipt",
            plain_description=(
                "A contractor estimate, repair bill, or receipt may help document disaster-related "
                "work or cost. The decision letter controls which record is relevant."
            ),
            source=Source.THIRD_PARTY,
            routed_to="contractor or repair vendor",
            cures=Deficiency.DAMAGE_EVIDENCE,
        ),
        Requirement(
            key="photo_wide",
            title="A wide context photo for applicant review",
            plain_description=(
                "Stand back so the floor and the wall are both in frame, and the water line is "
                "visible. This is optional supporting context, not proof that FEMA will accept "
                "or find the damage sufficient."
            ),
            source=Source.APPLICANT_ONLY,
            routed_to="you",
            cures=Deficiency.DAMAGE_EVIDENCE,
        ),
    ),
    Deficiency.INSURANCE: (
        Requirement(
            key="insurance_denial",
            title="Your insurer's decision letter",
            plain_description=(
                "An insurance settlement, denial letter, or policy document showing an exclusion "
                "or lack of coverage. This product does not treat an unsupported signed statement "
                "as equivalent to insurer documentation."
            ),
            source=Source.THIRD_PARTY,
            routed_to="your insurer",
            cures=Deficiency.INSURANCE,
        ),
    ),
    Deficiency.IDENTITY: (
        Requirement(
            key="identity",
            title="Government photo ID",
            plain_description="Must match the name on your application.",
            source=Source.APPLICANT_ONLY,
            routed_to="you",
            cures=Deficiency.IDENTITY,
        ),
    ),
    Deficiency.LEGAL: (
        Requirement(
            key="legal_aid",
            title="Free legal help",
            plain_description=(
                "Your denial turns on a legal question about who owns the property. No document "
                "you send will resolve it, so we are connecting you to free legal aid instead of "
                "sending you after paperwork that cannot succeed."
            ),
            source=Source.LEGAL_AID,
            routed_to="disaster legal services",
            cures=Deficiency.LEGAL,
        ),
    ),
    Deficiency.OTHER: (
        Requirement(
            key="case_review",
            title="A caseworker review of the exact letter language",
            plain_description=(
                "This reason does not match a documentary category safely. A disaster recovery "
                "caseworker should review the quoted passage before you are asked to gather "
                "anything."
            ),
            source=Source.THIRD_PARTY,
            routed_to="disaster recovery caseworker",
            cures=Deficiency.OTHER,
        ),
    ),
}


def plan_requirements(deficiencies: list[FoundDeficiency]) -> list[Requirement]:
    """What to gather, in the order that costs the applicant least effort.

    Public records first: those we can chase without troubling someone who has just lost a home.
    Third party requests next, because they can be drafted and sent while other things proceed.
    Things only the applicant can produce come last, so they are asked for as little as possible.
    """
    order = {
        Source.PUBLIC_RECORD: 0,
        Source.THIRD_PARTY: 1,
        Source.APPLICANT_ONLY: 2,
        Source.LEGAL_AID: 3,
    }
    by_key: dict[str, Requirement] = {}
    for found in deficiencies:
        for requirement in REQUIREMENTS.get(found.kind, ()):
            by_key.setdefault(requirement.key, requirement)
    return sorted(by_key.values(), key=lambda r: order[r.source])


def escalates_to_legal_aid(deficiencies: list[FoundDeficiency]) -> bool:
    """Knowing when to hand off is part of completing the workflow, not an admission of failure."""
    return any(d.kind is Deficiency.LEGAL for d in deficiencies)


def as_utc_date(value: str) -> date:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc).date()
