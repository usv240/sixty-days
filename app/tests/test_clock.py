from datetime import timedelta

import pytest

from spine.clock import (
    ClockState,
    MemoryClockStateStore,
    RealClock,
    SimulatedClock,
    build_clock,
    utcnow,
)


def test_real_clock_tracks_wall_time():
    clock = RealClock()
    before = utcnow()
    now = clock.now()
    after = utcnow()
    assert before <= now <= after
    assert clock.simulated is False


def test_simulated_clock_starts_at_wall_time():
    clock = SimulatedClock(MemoryClockStateStore())
    delta = abs((clock.now() - utcnow()).total_seconds())
    assert delta < 1.0


def test_advance_moves_time_forward():
    clock = SimulatedClock(MemoryClockStateStore())
    start = clock.now()
    clock.advance(timedelta(hours=52))
    moved = (clock.now() - start).total_seconds()
    assert 52 * 3600 - 2 < moved < 52 * 3600 + 2


def test_long_deadline_compresses_into_one_call():
    """A long deadline can be demonstrated without pretending real time passed."""
    clock = SimulatedClock(MemoryClockStateStore())
    start = clock.now()
    clock.advance(timedelta(days=60))
    assert (clock.now() - start).days == 60


def test_multi_week_schedule_advances_in_steps():
    """A multi-week wake ladder advances deterministically in several steps."""
    clock = SimulatedClock(MemoryClockStateStore())
    start = clock.now()
    for step in (timedelta(hours=48), timedelta(days=4), timedelta(days=8), timedelta(days=16)):
        clock.advance(step)
    assert (clock.now() - start).days == 30


def test_clock_cannot_move_backwards():
    """Rewinding would let an already fired wake fire again."""
    clock = SimulatedClock(MemoryClockStateStore())
    with pytest.raises(ValueError, match="cannot move backwards"):
        clock.advance(timedelta(hours=-1))


def test_freeze_holds_the_instant():
    clock = SimulatedClock(MemoryClockStateStore())
    frozen = clock.freeze()
    assert clock.now() == frozen
    assert clock.now() == frozen


def test_advance_while_frozen_keeps_the_freeze():
    clock = SimulatedClock(MemoryClockStateStore())
    frozen = clock.freeze()
    clock.advance(timedelta(days=1))
    assert clock.state().frozen_at is not None
    assert (clock.now() - frozen).days == 1


def test_unfreeze_preserves_elapsed_simulated_time():
    clock = SimulatedClock(MemoryClockStateStore())
    clock.advance(timedelta(days=10))
    clock.freeze()
    clock.advance(timedelta(days=5))
    before = clock.now()
    clock.unfreeze()
    assert abs((clock.now() - before).total_seconds()) < 1.0
    assert clock.state().frozen_at is None


def test_state_is_shared_across_clock_instances():
    """Cloud Run runs many instances. They must agree on what time it is."""
    store = MemoryClockStateStore()
    instance_a = SimulatedClock(store)
    instance_b = SimulatedClock(store)
    instance_a.advance(timedelta(days=3))
    delta = abs((instance_a.now() - instance_b.now()).total_seconds())
    assert delta < 1.0


def test_build_clock_returns_real_by_default():
    assert isinstance(build_clock(sim_mode=False), RealClock)


def test_build_clock_requires_a_store_in_sim_mode():
    with pytest.raises(ValueError, match="requires a ClockStateStore"):
        build_clock(sim_mode=True)


def test_clock_state_defaults_are_inert():
    state = ClockState()
    assert state.offset_seconds == 0.0
    assert state.frozen_at is None
