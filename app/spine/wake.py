"""Sleep until T.

This is what makes an agent's normal state silence. Day Three registers a five week ladder of
wakes at the start of an antibiotic course, Sixty Days holds a sixty day appeal window, and
Downstream nudges an owner between sessions. All three sleep, cost nothing while sleeping, and
act on their own when the time comes.

In production a Cloud Scheduler cron calls `/internal/scan-due`, which finds due wakes, claims
each in a transaction, invokes an idempotent handler directly, then marks it complete. Locally the
same dispatch path runs against the memory store, so the logic under test is the logic that ships.

Two properties matter more than anything else here:

* A wake fires **once**. Registration uses a deterministic id, and claiming is a compare and swap,
  so overlapping scheduler calls cannot process the same action twice.
* A wake that keeps failing **stops**, and goes to a dead letter queue with its history rather
  than retrying forever.
"""

from __future__ import annotations

import hashlib
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Callable

from spine.clock import Clock


class WakeStatus(StrEnum):
    PENDING = "pending"
    CLAIMED = "claimed"
    DONE = "done"
    CANCELLED = "cancelled"
    DEAD = "dead"


@dataclass(frozen=True)
class Wake:
    wake_id: str
    run_id: str
    kind: str
    due_at: datetime
    status: WakeStatus = WakeStatus.PENDING
    attempts: int = 0
    lease_token: str | None = None
    lease_expires_at: datetime | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    cancelled_reason: str | None = None
    last_error: str | None = None


def wake_id_for(run_id: str, kind: str, discriminator: str = "") -> str:
    """Deterministic id.

    Registering the same logical wake twice produces the same id, so re-running a registration
    after a crash cannot create a second wake. This is the first of the two defences against a
    patient being paged about twice.
    """
    digest = hashlib.sha256(f"{run_id}|{kind}|{discriminator}".encode()).hexdigest()[:16]
    return f"wk_{digest}"


class WakeStore(ABC):
    @abstractmethod
    def put_if_absent(self, wake: Wake) -> Wake: ...

    @abstractmethod
    def get(self, wake_id: str) -> Wake | None: ...

    @abstractmethod
    def put(self, wake: Wake) -> None: ...

    @abstractmethod
    def due(self, now: datetime, limit: int) -> list[Wake]: ...

    @abstractmethod
    def try_claim(self, wake_id: str, token: str, now: datetime, expires: datetime) -> Wake | None:
        """Atomically claim a pending wake, or one whose previous claim has expired."""

    @abstractmethod
    def for_run(self, run_id: str) -> list[Wake]: ...


class MemoryWakeStore(WakeStore):
    def __init__(self) -> None:
        self._wakes: dict[str, Wake] = {}
        self._lock = threading.RLock()

    def put_if_absent(self, wake: Wake) -> Wake:
        with self._lock:
            existing = self._wakes.get(wake.wake_id)
            if existing is not None:
                return existing
            self._wakes[wake.wake_id] = wake
            return wake

    def get(self, wake_id: str) -> Wake | None:
        with self._lock:
            return self._wakes.get(wake_id)

    def put(self, wake: Wake) -> None:
        with self._lock:
            self._wakes[wake.wake_id] = wake

    def due(self, now: datetime, limit: int) -> list[Wake]:
        with self._lock:
            ready = [
                w
                for w in self._wakes.values()
                if w.due_at <= now
                and (
                    w.status is WakeStatus.PENDING
                    or (
                        w.status is WakeStatus.CLAIMED
                        and w.lease_expires_at is not None
                        and w.lease_expires_at <= now
                    )
                )
            ]
            return sorted(ready, key=lambda w: w.due_at)[:limit]

    def try_claim(self, wake_id: str, token: str, now: datetime, expires: datetime) -> Wake | None:
        with self._lock:
            wake = self._wakes.get(wake_id)
            if wake is None or wake.due_at > now:
                return None
            claimable = wake.status is WakeStatus.PENDING or (
                wake.status is WakeStatus.CLAIMED
                and wake.lease_expires_at is not None
                and wake.lease_expires_at <= now
            )
            if not claimable:
                return None
            claimed = replace(
                wake,
                status=WakeStatus.CLAIMED,
                attempts=wake.attempts + 1,
                lease_token=token,
                lease_expires_at=expires,
            )
            self._wakes[wake_id] = claimed
            return claimed

    def for_run(self, run_id: str) -> list[Wake]:
        with self._lock:
            return sorted(
                (w for w in self._wakes.values() if w.run_id == run_id), key=lambda w: w.due_at
            )


class WakeScheduler:
    def __init__(
        self,
        store: WakeStore,
        clock: Clock,
        lease_seconds: int = 90,
        max_attempts: int = 5,
    ) -> None:
        self._store = store
        self._clock = clock
        self._lease = timedelta(seconds=lease_seconds)
        self._max_attempts = max_attempts
        self.dead_letters: list[Wake] = []

    def sleep_until(
        self,
        run_id: str,
        kind: str,
        due_at: datetime,
        payload: dict[str, Any] | None = None,
        discriminator: str = "",
    ) -> Wake:
        """Register a wake. Idempotent: registering twice returns the original."""
        wake = Wake(
            wake_id=wake_id_for(run_id, kind, discriminator),
            run_id=run_id,
            kind=kind,
            due_at=due_at,
            payload=payload or {},
        )
        return self._store.put_if_absent(wake)

    def sleep_for(
        self,
        run_id: str,
        kind: str,
        delta: timedelta,
        payload: dict[str, Any] | None = None,
        discriminator: str = "",
    ) -> Wake:
        return self.sleep_until(run_id, kind, self._clock.now() + delta, payload, discriminator)

    def scan_due(
        self,
        limit: int = 50,
        predicate: Callable[[Wake], bool] | None = None,
    ) -> list[Wake]:
        """What Cloud Scheduler triggers. Returns wakes this worker successfully claimed."""
        now = self._clock.now()
        claimed: list[Wake] = []
        for candidate in self._store.due(now, limit):
            if predicate is not None and not predicate(candidate):
                continue
            token = f"tok_{now.timestamp()}_{candidate.wake_id}"
            won = self._store.try_claim(candidate.wake_id, token, now, now + self._lease)
            if won is None:
                continue  # another worker took it. Correct outcome, not an error.
            if won.attempts > self._max_attempts:
                dead = replace(won, status=WakeStatus.DEAD)
                self._store.put(dead)
                self.dead_letters.append(dead)
                continue
            claimed.append(won)
        return claimed

    def dispatch_due(
        self,
        handler,
        limit: int = 50,
        predicate: Callable[[Wake], bool] | None = None,
    ) -> list[Wake]:
        """Claim, handle, and complete due wakes without an unprovisioned queue.

        The handler must be idempotent by wake_id. A crash after its side effect but before
        `complete` may retry after the lease expires; deterministic action records make that
        retry an overwrite rather than a duplicate. Handler failures release the wake for the
        existing bounded retry/dead-letter path.
        """
        dispatched: list[Wake] = []
        for wake in self.scan_due(limit, predicate=predicate):
            try:
                handler(wake)
            except Exception as exc:  # noqa: BLE001 - persist the typed failure and continue
                self.fail(wake.wake_id, f"{type(exc).__name__}: {exc}")
                continue
            self.complete(wake.wake_id)
            dispatched.append(wake)
        return dispatched

    def dispatch_wake(self, wake_id: str, handler) -> Wake | None:
        """Dispatch one known wake without being starved by an unrelated due backlog.

        This is primarily useful for deterministic acceptance checks and domain workers that
        already hold a wake id. It preserves the same claim, retry, dead-letter and idempotency
        rules as the batch scanner.
        """
        now = self._clock.now()
        token = f"tok_{now.timestamp()}_{wake_id}"
        claimed = self._store.try_claim(wake_id, token, now, now + self._lease)
        if claimed is None:
            return None
        if claimed.attempts > self._max_attempts:
            dead = replace(claimed, status=WakeStatus.DEAD)
            self._store.put(dead)
            self.dead_letters.append(dead)
            return None
        try:
            handler(claimed)
        except Exception as exc:  # noqa: BLE001 - persist the typed failure
            self.fail(claimed.wake_id, f"{type(exc).__name__}: {exc}")
            return None
        self.complete(claimed.wake_id)
        return claimed

    def complete(self, wake_id: str) -> None:
        wake = self._store.get(wake_id)
        if wake is None:
            return
        self._store.put(
            replace(wake, status=WakeStatus.DONE, lease_token=None, lease_expires_at=None)
        )

    def fail(self, wake_id: str, error: str) -> None:
        """Release for retry, or dead letter if it has failed too often."""
        wake = self._store.get(wake_id)
        if wake is None:
            return
        if wake.attempts >= self._max_attempts:
            dead = replace(wake, status=WakeStatus.DEAD, last_error=error)
            self._store.put(dead)
            self.dead_letters.append(dead)
            return
        self._store.put(
            replace(
                wake,
                status=WakeStatus.PENDING,
                lease_token=None,
                lease_expires_at=None,
                last_error=error,
            )
        )

    def cancel_run(self, run_id: str, reason: str) -> int:
        """Cancel remaining wakes, for example when a patient is discharged.

        Cancelled wakes are marked, never deleted, so the audit trail shows what would have
        happened and why it did not.
        """
        cancelled = 0
        for wake in self._store.for_run(run_id):
            if wake.status in (WakeStatus.PENDING, WakeStatus.CLAIMED):
                self._store.put(
                    replace(wake, status=WakeStatus.CANCELLED, cancelled_reason=reason)
                )
                cancelled += 1
        return cancelled

    def pending_for(self, run_id: str) -> list[Wake]:
        return [w for w in self._store.for_run(run_id) if w.status is WakeStatus.PENDING]
