"""Deadline Keeper tests.

These tests compress the full appeal window through the shared spine clock.  The key promise is
not merely that reminders exist: the whole schedule survives a restart, adapts to an earlier
deadline, and creates an appeal packet before time runs out.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from sixty_days.deadline import (
    LADDER,
    MAX_ATTEMPTS_BEFORE_REPLAN,
    THIRD_PARTY_CHASE_DAYS,
    Case,
    Contact,
    DeadlineKeeper,
)
from spine.clock import ClockState, MemoryClockStateStore, SimulatedClock
from spine.wake import MemoryWakeStore, WakeScheduler, WakeStatus


@pytest.fixture
def clock():
    return SimulatedClock(
        MemoryClockStateStore(
            ClockState(frozen_at=datetime(2026, 8, 1, 9, tzinfo=timezone.utc))
        )
    )


@pytest.fixture
def scheduler(clock):
    return WakeScheduler(MemoryWakeStore(), clock)


@pytest.fixture
def keeper(scheduler):
    return DeadlineKeeper(scheduler)


@pytest.fixture
def case():
    return Case("case_1", "run_1", date(2026, 8, 1), date(2026, 9, 30))


def test_opening_a_case_registers_the_entire_ladder(keeper, scheduler, case):
    registered = keeper.open_case(case)
    assert len(registered) == len(LADDER)
    assert len(scheduler.pending_for(case.run_id)) == len(LADDER)


def test_reopening_after_a_restart_is_idempotent(keeper, scheduler, case):
    first = keeper.open_case(case)
    second = keeper.open_case(case)
    assert [w.wake_id for w in first] == [w.wake_id for w in second]
    assert len(scheduler.pending_for(case.run_id)) == len(LADDER)


def test_repeated_nudges_have_distinct_wake_ids(keeper, case):
    registered = keeper.open_case(case)
    nudges = [w for w in registered if w.kind == Contact.NUDGE.value]
    assert len(nudges) == 3
    assert len({w.wake_id for w in nudges}) == 3


def test_ladder_fires_in_order_across_sixty_days(keeper, scheduler, clock, case):
    keeper.open_case(case)
    fired: list[str] = []
    for _ in range(60):
        clock.advance(timedelta(days=1))
        for wake in scheduler.scan_due():
            fired.append(wake.kind)
            scheduler.complete(wake.wake_id)
    assert fired == [contact.value for contact, _day, _why in LADDER]


def test_every_contact_has_a_plain_language_explanation():
    for contact in Contact:
        explanation = DeadlineKeeper.explain(contact)
        assert len(explanation) > 20
        assert explanation[0].isupper()


@pytest.mark.parametrize(
    ("remaining", "urgency"),
    [(31, "on track"), (30, "attention"), (14, "urgent"), (7, "critical"), (-1, "critical")],
)
def test_urgency_is_explicit_text_not_colour_alone(remaining: int, urgency: str):
    assert DeadlineKeeper.urgency(remaining) == urgency


def test_earlier_deadline_still_builds_a_partial_packet_and_warns_two_days_before(
    keeper, case
):
    shortened = Case(case.case_id, case.run_id, case.letter_date, date(2026, 9, 15))
    registered = keeper.open_case(shortened)
    due = {w.kind: w.due_at.date() for w in registered}
    assert due[Contact.BUILD_PARTIAL.value] == shortened.deadline - timedelta(days=8)
    assert due[Contact.FINAL_ALERT.value] == shortened.deadline - timedelta(days=2)


def test_invalid_deadline_before_letter_is_rejected(keeper, case):
    invalid = Case(case.case_id, case.run_id, case.letter_date, date(2026, 7, 31))
    with pytest.raises(ValueError, match="deadline"):
        keeper.open_case(invalid)


def test_third_party_request_gets_its_own_chase_clock(keeper, scheduler, case):
    wake = keeper.chase_third_party(case, "insurance_denial", date(2026, 8, 5))
    assert wake.kind == "chase:insurance_denial"
    assert wake.due_at.date() == date(2026, 8, 5) + timedelta(days=THIRD_PARTY_CHASE_DAYS)
    assert wake.payload["requirement"] == "insurance_denial"
    assert len(scheduler.pending_for(case.run_id)) == 1


def test_third_party_chase_never_lands_after_the_appeal_deadline(keeper, case):
    wake = keeper.chase_third_party(case, "utility_bill", date(2026, 9, 20))
    assert wake.due_at.date() == case.deadline


def test_request_created_after_deadline_is_rejected(keeper, case):
    with pytest.raises(ValueError, match="after the appeal deadline"):
        keeper.chase_third_party(case, "utility_bill", date(2026, 10, 1))


def test_two_third_party_requirements_do_not_collide(keeper, scheduler, case):
    a = keeper.chase_third_party(case, "insurance_denial", date(2026, 8, 5))
    b = keeper.chase_third_party(case, "utility_bill", date(2026, 8, 5))
    assert a.wake_id != b.wake_id
    assert len(scheduler.pending_for(case.run_id)) == 2


def test_close_marks_every_remaining_contact_cancelled(keeper, scheduler, case):
    keeper.open_case(case)
    cancelled = keeper.close(case, "appeal submitted")
    assert cancelled == len(LADDER)
    all_wakes = scheduler._store.for_run(case.run_id)
    assert all(w.status is WakeStatus.CANCELLED for w in all_wakes)
    assert all(w.cancelled_reason == "appeal submitted" for w in all_wakes)


def test_case_day_and_days_remaining_are_calendar_based(case):
    assert case.day_of(date(2026, 8, 31)) == 30
    assert case.days_remaining(date(2026, 9, 20)) == 10


def test_replan_threshold_is_three_failed_attempts():
    assert MAX_ATTEMPTS_BEFORE_REPLAN == 3
