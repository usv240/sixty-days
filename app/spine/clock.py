"""The injectable clock.

This is the keystone of the system. Durable workflows may span hours, weeks, or months, while a
short evaluation cannot wait for real time to pass.

`SimulatedClock` lets a demo compress real elapsed time while the agents genuinely react, using
*the same code path* that runs against wall clock time in production. Nothing is faked: wake rows,
messages and traces are all real. Only the reading of "now" changes.

Honesty rule from the design: the demo states out loud that the clock is simulated. Rules.md
line 1111 warns against overstating what is running, so this is stated rather than hidden.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol, runtime_checkable


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@runtime_checkable
class Clock(Protocol):
    """Anything that can tell the system what time it is."""

    def now(self) -> datetime: ...


@dataclass(frozen=True)
class ClockState:
    """Persisted simulation state.

    offset_seconds: added to wall clock time to produce simulated now.
    frozen_at:      when set, now() returns this exact instant, for narration during recording.
    """

    offset_seconds: float = 0.0
    frozen_at: datetime | None = None


class ClockStateStore(ABC):
    """Where simulation state lives.

    Cloud Run runs many instances. The simulated clock must be shared across all of them, so in
    production this is backed by Firestore. Tests use the in-memory implementation.
    """

    @abstractmethod
    def read(self) -> ClockState: ...

    @abstractmethod
    def write(self, state: ClockState) -> None: ...


class MemoryClockStateStore(ClockStateStore):
    def __init__(self, state: ClockState | None = None) -> None:
        self._state = state or ClockState()
        self._lock = threading.Lock()

    def read(self) -> ClockState:
        with self._lock:
            return self._state

    def write(self, state: ClockState) -> None:
        with self._lock:
            self._state = state


class RealClock:
    """Wall clock time. The production default."""

    simulated = False

    def now(self) -> datetime:
        return utcnow()


class SimulatedClock:
    """Wall clock time plus a persisted offset, optionally frozen.

    The offset only ever moves forward. There is no rewind, because agents have already acted on
    the times they observed and moving time backwards would let a wake fire twice.
    """

    simulated = True

    def __init__(self, store: ClockStateStore) -> None:
        self._store = store

    def now(self) -> datetime:
        state = self._store.read()
        if state.frozen_at is not None:
            return state.frozen_at
        return utcnow() + timedelta(seconds=state.offset_seconds)

    def advance(self, delta: timedelta) -> datetime:
        """Move simulated time forward. Returns the new simulated now."""
        if delta.total_seconds() < 0:
            raise ValueError(
                "the simulated clock cannot move backwards. Agents have already acted on the "
                "times they observed, and rewinding would let a wake fire twice."
            )
        state = self._store.read()
        if state.frozen_at is not None:
            # Advancing while frozen moves the frozen instant, keeping the freeze.
            self._store.write(
                ClockState(offset_seconds=state.offset_seconds, frozen_at=state.frozen_at + delta)
            )
        else:
            self._store.write(
                ClockState(
                    offset_seconds=state.offset_seconds + delta.total_seconds(),
                    frozen_at=None,
                )
            )
        return self.now()

    def freeze(self) -> datetime:
        """Stop the clock at the current simulated instant, for narration during recording."""
        state = self._store.read()
        if state.frozen_at is not None:
            return state.frozen_at
        frozen = utcnow() + timedelta(seconds=state.offset_seconds)
        self._store.write(ClockState(offset_seconds=state.offset_seconds, frozen_at=frozen))
        return frozen

    def unfreeze(self) -> datetime:
        """Resume, preserving the elapsed simulated time accumulated while frozen."""
        state = self._store.read()
        if state.frozen_at is None:
            return self.now()
        offset = (state.frozen_at - utcnow()).total_seconds()
        self._store.write(ClockState(offset_seconds=offset, frozen_at=None))
        return self.now()

    def state(self) -> ClockState:
        return self._store.read()


def build_clock(sim_mode: bool, store: ClockStateStore | None = None) -> Clock:
    """Single place the rest of the system asks for a clock.

    No module constructs a clock directly, and no module calls datetime.now(). That discipline is
    what makes the demo possible and is asserted by a test.
    """
    if not sim_mode:
        return RealClock()
    if store is None:
        raise ValueError("simulated mode requires a ClockStateStore")
    return SimulatedClock(store)
