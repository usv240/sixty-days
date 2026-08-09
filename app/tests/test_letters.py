"""Sixty Days letter interpretation and evidence-routing tests.

The safety property is the same one proven by Day Three intake: a deficiency is usable only
when its source text really appears in the letter.  Routing also has to produce a concrete next
action for every category; silently returning no plan would strand an applicant.
"""

from datetime import date

import pytest

from sixty_days.letters import (
    APPEAL_WINDOW,
    Deficiency,
    Determination,
    FoundDeficiency,
    Letter,
    Quote,
    Source,
    as_utc_date,
    escalates_to_legal_aid,
    plan_requirements,
)


def found(kind: Deficiency, quote: str = "unable to verify ownership") -> FoundDeficiency:
    return FoundDeficiency(kind, "Plain explanation.", Quote(quote))


def test_quote_matching_tolerates_case_and_whitespace_only():
    document = "We were UNABLE   TO\nverify ownership of the damaged dwelling."
    assert Quote("unable to verify ownership").appears_in(document)
    assert not Quote("unable to verify occupancy").appears_in(document)


def test_an_empty_quote_never_counts_as_evidence():
    assert not Quote("").appears_in("any document at all")
    assert not Quote("   ").appears_in("any document at all")


def test_default_deadline_is_letter_date_plus_sixty_days():
    letter = Letter(date(2026, 8, 1), Determination.DENIED)
    assert letter.deadline == date(2026, 8, 1) + APPEAL_WINDOW


def test_earlier_stated_deadline_wins():
    letter = Letter(
        date(2026, 8, 1),
        Determination.DENIED,
        stated_deadline=date(2026, 9, 20),
    )
    assert letter.deadline == date(2026, 9, 20)


def test_later_stated_deadline_does_not_extend_the_sixty_day_window():
    letter = Letter(
        date(2026, 8, 1),
        Determination.DENIED,
        stated_deadline=date(2026, 10, 15),
    )
    assert letter.deadline == date(2026, 9, 30)


def test_deadline_conflict_exposes_both_dates():
    letter = Letter(
        date(2026, 8, 1),
        Determination.DENIED,
        stated_deadline=date(2026, 9, 20),
    )
    assert "2026-09-20" in (letter.deadline_conflict or "")
    assert "2026-09-30" in (letter.deadline_conflict or "")


def test_matching_deadlines_do_not_report_a_conflict():
    letter = Letter(
        date(2026, 8, 1),
        Determination.DENIED,
        stated_deadline=date(2026, 9, 30),
    )
    assert letter.deadline_conflict is None


def test_days_remaining_can_be_negative_after_expiry():
    letter = Letter(date(2026, 8, 1), Determination.DENIED)
    assert letter.days_remaining(date(2026, 10, 2)) == -2


def test_requirements_are_routed_least_burden_first():
    requirements = plan_requirements(
        [
            found(Deficiency.DAMAGE_EVIDENCE),
            found(Deficiency.INSURANCE),
            found(Deficiency.OWNERSHIP),
        ]
    )
    assert [r.source for r in requirements] == [
        Source.PUBLIC_RECORD,
        Source.THIRD_PARTY,
        Source.THIRD_PARTY,
        Source.APPLICANT_ONLY,
    ]
    by_key = {item.key: item for item in requirements}
    assert "guarantee" not in " ".join(item.plain_description for item in requirements)
    assert "signed statement" in by_key["insurance_denial"].plain_description
    assert "optional supporting context" in by_key["photo_wide"].plain_description


def test_duplicate_deficiencies_do_not_duplicate_requests():
    requirements = plan_requirements(
        [found(Deficiency.OWNERSHIP), found(Deficiency.OWNERSHIP)]
    )
    assert [r.key for r in requirements] == ["deed"]


@pytest.mark.parametrize("kind", list(Deficiency))
def test_every_deficiency_has_a_concrete_route(kind: Deficiency):
    requirements = plan_requirements([found(kind)])
    assert requirements, f"{kind.value} would leave the applicant with no next action"
    assert all(r.routed_to and r.plain_description for r in requirements)


def test_legal_question_routes_to_legal_aid_instead_of_more_paperwork():
    deficiencies = [found(Deficiency.LEGAL)]
    requirement = plan_requirements(deficiencies)[0]
    assert escalates_to_legal_aid(deficiencies)
    assert requirement.source is Source.LEGAL_AID
    assert "No document" in requirement.plain_description


def test_documentary_problem_does_not_claim_to_need_legal_aid():
    assert not escalates_to_legal_aid([found(Deficiency.OWNERSHIP)])


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-08-01", date(2026, 8, 1)),
        ("2026-08-01T23:59:00-04:00", date(2026, 8, 1)),
        ("2026-08-01T12:00:00Z", date(2026, 8, 1)),
    ],
)
def test_iso_dates_parse_deterministically(raw: str, expected: date):
    assert as_utc_date(raw) == expected


def test_invalid_date_is_rejected():
    with pytest.raises(ValueError):
        as_utc_date("not-a-date")
