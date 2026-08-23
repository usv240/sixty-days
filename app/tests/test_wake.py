from datetime import timedelta

import pytest

from spine.clock import MemoryClockStateStore, SimulatedClock
from spine.wake import (
    MemoryWakeStore,
    WakeScheduler,
    WakeStatus,
    wake_id_for,
)


@pytest.fixture
def clock():
    return SimulatedClock(MemoryClockStateStore())


@pytest.fixture
def scheduler(clock):
    return WakeScheduler(MemoryWakeStore(), clock)


def test_a_wake_does_not_fire_early(scheduler, clock):
    scheduler.sleep_for("run_1", "deescalation_review", timedelta(hours=48))
    clock.advance(timedelta(hours=47))
    assert scheduler.scan_due() == []


def test_a_wake_fires_when_its_time_arrives(scheduler, clock):
    scheduler.sleep_for("run_1", "deescalation_review", timedelta(hours=48))
    clock.advance(timedelta(hours=52))
    due = scheduler.scan_due()
    assert [w.kind for w in due] == ["deescalation_review"]


def test_the_five_week_ladder_fires_in_order(scheduler, clock):
    """The complete wake ladder is registered up front so it survives a crash."""
    ladder = [
        ("deescalation_review", timedelta(hours=48)),
        ("iv_to_oral_review", timedelta(days=5)),
        ("stop_date_check", timedelta(days=7)),
        ("discharge_recon", timedelta(days=9)),
        ("readmission_check", timedelta(days=39)),
    ]
    for kind, delta in ladder:
        scheduler.sleep_for("run_course", kind, delta)

    fired: list[str] = []
    for _ in range(6):
        clock.advance(timedelta(days=7))
        for wake in scheduler.scan_due():
            fired.append(wake.kind)
            scheduler.complete(wake.wake_id)

    assert fired == [
        "deescalation_review",
        "iv_to_oral_review",
        "stop_date_check",
        "discharge_recon",
        "readmission_check",
    ]


def test_sixty_day_window_compresses_into_one_advance(scheduler, clock):
    scheduler.sleep_for("run_appeal", "day_58_final_alert", timedelta(days=58))
    clock.advance(timedelta(days=59))
    assert [w.kind for w in scheduler.scan_due()] == ["day_58_final_alert"]


def test_registration_is_idempotent(scheduler):
    """Re-running registration after a crash must not create a second wake."""
    first = scheduler.sleep_for("run_1", "deescalation_review", timedelta(hours=48))
    second = scheduler.sleep_for("run_1", "deescalation_review", timedelta(hours=48))
    assert first.wake_id == second.wake_id
    assert len(scheduler.pending_for("run_1")) == 1


def test_wake_ids_are_stable_and_distinct():
    assert wake_id_for("r", "k") == wake_id_for("r", "k")
    assert wake_id_for("r", "k") != wake_id_for("r", "k2")
    assert wake_id_for("r", "k", "patient_a") != wake_id_for("r", "k", "patient_b")


def test_a_wake_is_claimed_by_exactly_one_worker(clock):
    """Duplicate delivery must not prepare the same pharmacist escalation twice."""
    store = MemoryWakeStore()
    worker_a = WakeScheduler(store, clock)
    worker_b = WakeScheduler(store, clock)

    worker_a.sleep_for("run_1", "page", timedelta(hours=1))
    clock.advance(timedelta(hours=2))

    claimed_a = worker_a.scan_due()
    claimed_b = worker_b.scan_due()

    assert len(claimed_a) + len(claimed_b) == 1


def test_an_expired_claim_becomes_available_again(clock):
    """A worker that died holding a wake must not wedge it forever."""
    store = MemoryWakeStore()
    scheduler = WakeScheduler(store, clock, lease_seconds=90)
    scheduler.sleep_for("run_1", "page", timedelta(hours=1))
    clock.advance(timedelta(hours=2))

    assert len(scheduler.scan_due()) == 1
    assert scheduler.scan_due() == []  # still leased

    clock.advance(timedelta(seconds=91))
    assert len(scheduler.scan_due()) == 1


def test_completed_wakes_do_not_fire_again(scheduler, clock):
    scheduler.sleep_for("run_1", "page", timedelta(hours=1))
    clock.advance(timedelta(hours=2))
    wake = scheduler.scan_due()[0]
    scheduler.complete(wake.wake_id)
    clock.advance(timedelta(days=1))
    assert scheduler.scan_due() == []


def test_direct_dispatch_handles_and_completes_a_due_wake_once(scheduler, clock):
    wake = scheduler.sleep_for("run_1", "page", timedelta(hours=1))
    clock.advance(timedelta(hours=2))
    handled = []

    dispatched = scheduler.dispatch_due(lambda due: handled.append(due.wake_id))

    assert handled == [wake.wake_id]
    assert [item.wake_id for item in dispatched] == [wake.wake_id]
    assert scheduler._store.get(wake.wake_id).status is WakeStatus.DONE
    assert scheduler.dispatch_due(lambda due: handled.append(due.wake_id)) == []
    assert handled == [wake.wake_id]

    other = scheduler.sleep_for("run_2", "other_project", timedelta(hours=1))
    clock.advance(timedelta(hours=2))
    assert scheduler.dispatch_due(
        lambda _due: None,
        predicate=lambda candidate: candidate.run_id == "run_1",
    ) == []
    assert scheduler._store.get(other.wake_id).status is WakeStatus.PENDING
    assert [item.wake_id for item in scheduler.dispatch_due(lambda _due: None)] == [other.wake_id]


def test_direct_dispatch_failure_releases_the_wake_for_bounded_retry(clock):
    store = MemoryWakeStore()
    scheduler = WakeScheduler(store, clock, lease_seconds=1, max_attempts=3)
    wake = scheduler.sleep_for("run_1", "flaky", timedelta(hours=1))
    clock.advance(timedelta(hours=2))

    def fail(_wake):
        raise RuntimeError("action store unavailable")

    assert scheduler.dispatch_due(fail) == []
    failed = store.get(wake.wake_id)
    assert failed.status is WakeStatus.PENDING
    assert failed.last_error == "RuntimeError: action store unavailable"
    clock.advance(timedelta(seconds=2))
    assert len(scheduler.dispatch_due(lambda _wake: None)) == 1
    assert store.get(wake.wake_id).status is WakeStatus.DONE


def test_exact_dispatch_is_not_starved_by_unrelated_due_backlog(clock):
    store = MemoryWakeStore()
    scheduler = WakeScheduler(store, clock)
    for index in range(75):
        scheduler.sleep_for(f"old_{index}", "old_action", timedelta(hours=1))
    target = scheduler.sleep_for("acceptance", "deadline", timedelta(hours=2))
    clock.advance(timedelta(hours=3))

    handled = []
    dispatched = scheduler.dispatch_wake(target.wake_id, lambda wake: handled.append(wake.wake_id))

    assert dispatched is not None
    assert dispatched.wake_id == target.wake_id
    assert handled == [target.wake_id]
    assert store.get(target.wake_id).status is WakeStatus.DONE


def test_repeated_failure_dead_letters_rather_than_looping(clock):
    store = MemoryWakeStore()
    scheduler = WakeScheduler(store, clock, lease_seconds=1, max_attempts=3)
    scheduler.sleep_for("run_1", "flaky", timedelta(hours=1))
    clock.advance(timedelta(hours=2))

    for _ in range(6):
        for wake in scheduler.scan_due():
            scheduler.fail(wake.wake_id, "downstream API down")
        clock.advance(timedelta(seconds=2))

    assert scheduler.dead_letters, "a permanently failing wake must stop and be recorded"
    assert scheduler.dead_letters[0].last_error == "downstream API down"
    assert scheduler.scan_due() == []


def test_a_transient_failure_is_retried(clock):
    store = MemoryWakeStore()
    scheduler = WakeScheduler(store, clock, lease_seconds=1, max_attempts=5)
    scheduler.sleep_for("run_1", "flaky", timedelta(hours=1))
    clock.advance(timedelta(hours=2))

    first = scheduler.scan_due()[0]
    scheduler.fail(first.wake_id, "timeout")
    clock.advance(timedelta(seconds=2))

    retried = scheduler.scan_due()
    assert len(retried) == 1
    assert retried[0].attempts == 2


def test_discharge_cancels_the_rest_of_the_ladder(scheduler, clock):
    for kind, delta in [
        ("iv_to_oral_review", timedelta(days=5)),
        ("stop_date_check", timedelta(days=7)),
        ("readmission_check", timedelta(days=39)),
    ]:
        scheduler.sleep_for("run_course", kind, delta)

    cancelled = scheduler.cancel_run("run_course", "therapy discontinued")
    assert cancelled == 3

    clock.advance(timedelta(days=60))
    assert scheduler.scan_due() == []


def test_cancelled_wakes_are_marked_not_deleted(scheduler):
    """The audit trail must show what would have happened and why it did not."""
    scheduler.sleep_for("run_course", "stop_date_check", timedelta(days=7))
    scheduler.cancel_run("run_course", "patient discharged")

    store_wakes = scheduler._store.for_run("run_course")
    assert len(store_wakes) == 1
    assert store_wakes[0].status is WakeStatus.CANCELLED
    assert store_wakes[0].cancelled_reason == "patient discharged"


def test_cancel_run_can_spare_the_wake_that_is_currently_running():
    """A handler may decide mid-flight that the whole run is finished.

    The wake it is running inside is CLAIMED, so a blanket cancel would sweep it up. The dispatcher
    then marks it DONE a moment later, silently reverting the cancellation and leaving the returned
    count one higher than the number of reminders that were actually stopped.
    """
    from datetime import datetime, timedelta, timezone

    from spine.clock import ClockState, MemoryClockStateStore, SimulatedClock
    from spine.wake import MemoryWakeStore, WakeScheduler, WakeStatus

    start = datetime(2026, 8, 5, 9, 0, tzinfo=timezone.utc)
    store = MemoryWakeStore()
    scheduler = WakeScheduler(store, SimulatedClock(MemoryClockStateStore(ClockState(frozen_at=start))))

    running = scheduler.sleep_until("run_1", "nudge", start + timedelta(days=1))
    later = scheduler.sleep_until("run_1", "final_alert", start + timedelta(days=30))

    cancelled = scheduler.cancel_run("run_1", "case complete", except_wake_id=running.wake_id)

    assert cancelled == 1
    assert store.get(running.wake_id).status is WakeStatus.PENDING
    assert store.get(later.wake_id).status is WakeStatus.CANCELLED
    assert store.get(later.wake_id).cancelled_reason == "case complete"


def test_cancel_run_without_an_exclusion_still_cancels_everything():
    from datetime import datetime, timedelta, timezone

    from spine.clock import ClockState, MemoryClockStateStore, SimulatedClock
    from spine.wake import MemoryWakeStore, WakeScheduler, WakeStatus

    start = datetime(2026, 8, 5, 9, 0, tzinfo=timezone.utc)
    store = MemoryWakeStore()
    scheduler = WakeScheduler(store, SimulatedClock(MemoryClockStateStore(ClockState(frozen_at=start))))
    first = scheduler.sleep_until("run_2", "nudge", start + timedelta(days=1))
    second = scheduler.sleep_until("run_2", "final_alert", start + timedelta(days=30))

    assert scheduler.cancel_run("run_2", "closed") == 2
    assert store.get(first.wake_id).status is WakeStatus.CANCELLED
    assert store.get(second.wake_id).status is WakeStatus.CANCELLED


def test_a_rejected_head_does_not_starve_owned_wakes_behind_it():
    """The bug this exists for: a filtered scanner used to see only the first page.

    A frozen clock in a neighbouring project left fifty overdue wakes it could not claim sitting
    at the head of the shared queue. This scanner did not own them, rejected the whole page, and
    stopped -- so every wake registered afterwards was starved, silently, with no error anywhere.
    """
    store = MemoryWakeStore()
    clock = SimulatedClock(MemoryClockStateStore())
    scheduler = WakeScheduler(store, clock)

    for index in range(120):
        scheduler.sleep_for("run_theirs", "nudge", timedelta(seconds=-10), discriminator=str(index))
    ours = scheduler.sleep_for("run_ours", "live_proof", timedelta(seconds=-1))

    claimed = scheduler.scan_due(limit=50, predicate=lambda w: w.run_id == "run_ours")
    assert [w.wake_id for w in claimed] == [ours.wake_id], (
        "the owned wake sat behind 120 unowned ones and must still be found"
    )


def test_an_unfiltered_scan_still_respects_its_limit():
    store = MemoryWakeStore()
    scheduler = WakeScheduler(store, SimulatedClock(MemoryClockStateStore()))
    for index in range(30):
        scheduler.sleep_for("run", "nudge", timedelta(seconds=-5), discriminator=str(index))
    assert len(scheduler.scan_due(limit=10)) == 10


def test_a_filtered_scan_claims_no_more_than_its_limit():
    store = MemoryWakeStore()
    scheduler = WakeScheduler(store, SimulatedClock(MemoryClockStateStore()))
    for index in range(30):
        scheduler.sleep_for("run_ours", "nudge", timedelta(seconds=-5), discriminator=str(index))
    claimed = scheduler.scan_due(limit=10, predicate=lambda w: w.run_id == "run_ours")
    assert len(claimed) == 10


def test_paging_terminates_when_nothing_matches():
    store = MemoryWakeStore()
    scheduler = WakeScheduler(store, SimulatedClock(MemoryClockStateStore()))
    for index in range(200):
        scheduler.sleep_for("run_theirs", "nudge", timedelta(seconds=-5), discriminator=str(index))
    assert scheduler.scan_due(limit=50, predicate=lambda w: w.run_id == "run_ours") == []
