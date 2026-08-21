"""One shared wake collection, several services: a scanner must claim only its own work.

Claiming a wake is a compare and swap and a wake fires once. Those two properties make overlapping
scheduler calls safe within a service, and dangerous across services sharing a database: a
neighbouring worker that claims a wake it has no handler for still completes it. The safeguard is
then permanently retired, with no error raised anywhere.

This suite is the regression barrier for that failure. It was written after the deployed shared
scanner was found claiming every due wake in the collection, including this project's.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from spine.clock import ClockState, MemoryClockStateStore, SimulatedClock
from spine.state import MemoryStateStore, Runner
from spine.wake import MemoryWakeStore, Wake, WakeScheduler, WakeStatus
from spine.wake_ownership import owning_project, project_predicate


START = datetime(2026, 8, 5, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def world():
    clock = SimulatedClock(MemoryClockStateStore(ClockState(frozen_at=START)))
    state_store = MemoryStateStore()
    wake_store = MemoryWakeStore()
    scheduler = WakeScheduler(wake_store, clock, lease_seconds=90)
    return clock, state_store, wake_store, scheduler


def _register(state_store, scheduler, project: str, kind: str) -> Wake:
    runner = Runner(
        state_store,
        SimulatedClock(MemoryClockStateStore(ClockState(frozen_at=START))),
        owner="test-worker",
    )
    run_id = runner.start(project, "case", {})
    return scheduler.sleep_until(run_id, kind, START + timedelta(days=1))


def test_a_scanner_claims_only_the_projects_it_can_execute(world) -> None:
    clock, state_store, wake_store, scheduler = world
    mine = _register(state_store, scheduler, "sixty-days", "packet_safeguard")
    neighbour = _register(state_store, scheduler, "neighbour-service", "unrelated_followup")
    clock.advance(timedelta(days=2))

    handled: list[str] = []
    claimed = scheduler.dispatch_due(
        lambda wake: handled.append(wake.wake_id),
        predicate=project_predicate(state_store.get_run, "sixty-days"),
    )

    assert [w.wake_id for w in claimed] == [mine.wake_id]
    assert handled == [mine.wake_id]
    assert status_of(wake_store, neighbour) is WakeStatus.PENDING


def test_a_neighbouring_scanner_cannot_retire_this_project_s_safeguard(world) -> None:
    """The exact deployed failure: a shared worker completing a wake it has no handler for."""
    clock, state_store, wake_store, scheduler = world
    safeguard = _register(state_store, scheduler, "sixty-days", "packet_safeguard")
    clock.advance(timedelta(days=2))

    neighbour_claimed = scheduler.dispatch_due(
        lambda wake: None,
        predicate=project_predicate(state_store.get_run, "spine", "neighbour-service"),
    )
    assert neighbour_claimed == []
    assert status_of(wake_store, safeguard) is WakeStatus.PENDING

    executed: list[str] = []
    owner_claimed = scheduler.dispatch_due(
        lambda wake: executed.append(wake.kind),
        predicate=project_predicate(state_store.get_run, "sixty-days"),
    )
    assert [w.wake_id for w in owner_claimed] == [safeguard.wake_id]
    assert executed == ["packet_safeguard"]


def test_the_demo_surface_never_claims_a_beta_tenant_wake(world) -> None:
    """The two surfaces run on different clocks. Crossing them would fire beta work on sim time."""
    clock, state_store, wake_store, scheduler = world
    demo = _register(state_store, scheduler, "sixty-days", "day_three_check")
    beta = _register(state_store, scheduler, "sixty-days-beta", "day_three_check")
    clock.advance(timedelta(days=2))

    claimed = scheduler.dispatch_due(
        lambda wake: None, predicate=project_predicate(state_store.get_run, "sixty-days")
    )

    assert [w.wake_id for w in claimed] == [demo.wake_id]
    assert status_of(wake_store, beta) is WakeStatus.PENDING


def test_a_wake_whose_run_cannot_be_resolved_is_left_pending(world) -> None:
    """Safer to leave it visible and reclaimable than to complete work nobody understood."""
    clock, state_store, wake_store, scheduler = world
    orphan = scheduler.sleep_until("run_does_not_exist", "packet_safeguard", START + timedelta(days=1))
    clock.advance(timedelta(days=2))

    claimed = scheduler.dispatch_due(
        lambda wake: None, predicate=project_predicate(state_store.get_run, "sixty-days")
    )

    assert claimed == []
    assert owning_project(state_store.get_run, orphan) is None
    assert status_of(wake_store, orphan) is WakeStatus.PENDING


def test_ownership_matching_ignores_surrounding_case_and_whitespace(world) -> None:
    _, state_store, _, scheduler = world
    wake = _register(state_store, scheduler, "sixty-days", "packet_safeguard")
    predicate = project_predicate(state_store.get_run, "  Sixty-Days  ")
    assert predicate(wake) is True


def test_an_empty_ownership_list_claims_nothing(world) -> None:
    """A misconfigured allowlist must fail closed, not open."""
    clock, state_store, _, scheduler = world
    _register(state_store, scheduler, "sixty-days", "packet_safeguard")
    clock.advance(timedelta(days=2))

    claimed = scheduler.dispatch_due(
        lambda wake: None, predicate=project_predicate(state_store.get_run, "", "   ")
    )
    assert claimed == []


def status_of(wake_store: MemoryWakeStore, wake: Wake) -> WakeStatus:
    stored = wake_store.get(wake.wake_id)
    assert stored is not None
    return stored.status
