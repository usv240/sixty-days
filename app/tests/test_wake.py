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
    """Day Three registers the whole course at once so the schedule survives a crash."""
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
