"""Firestore implementations of the spine's store interfaces.

The in-memory stores in clock.py, state.py and wake.py exist so the logic can be tested without a
network. These are the same interfaces backed by Firestore, so what ships is what was tested.

The only genuinely subtle part is claiming. Cloud Run can run many instances and overlapping
Cloud Scheduler calls can reach for the same wake at the same moment. Both `try_claim` methods
below run inside a Firestore transaction, which makes the check and the write a single atomic
step. Without that, two workers could execute the same due action.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone
from typing import Any

from google.cloud import firestore

from spine.clock import ClockState, ClockStateStore
from spine.state import Run, RunStatus, StateStore, Step, StepStatus
from spine.wake import Wake, WakeStatus, WakeStore

CLOCK_COLLECTION = "sim"


def _as_utc(value: Any) -> Any:
    """Firestore returns timezone aware datetimes. Normalise defensively."""
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _clean(data: dict[str, Any]) -> dict[str, Any]:
    return {k: _as_utc(v) for k, v in data.items()}


class FirestoreClockStateStore(ClockStateStore):
    """Simulation state shared by every instance of one public project.

    Without a shared store each instance would have its own idea of the time, and a wake would
    fire on one instance and not another. Different submissions must not share a demo clock:
    advancing one evaluation session must never move another session's timeline.
    """

    def __init__(self, client: firestore.Client, namespace: str = "shared") -> None:
        safe = namespace.strip().lower()
        if not safe or not safe.replace("-", "").replace("_", "").isalnum():
            raise ValueError("clock namespace must contain only letters, numbers, hyphens or underscores")
        self._ref = client.collection(CLOCK_COLLECTION).document(f"clock-{safe}")

    def read(self) -> ClockState:
        snapshot = self._ref.get()
        if not snapshot.exists:
            return ClockState()
        data = _clean(snapshot.to_dict() or {})
        return ClockState(
            offset_seconds=float(data.get("offset_seconds", 0.0)),
            frozen_at=data.get("frozen_at"),
        )

    def write(self, state: ClockState) -> None:
        self._ref.set(
            {"offset_seconds": state.offset_seconds, "frozen_at": state.frozen_at},
            merge=False,
        )


class FirestoreStateStore(StateStore):
    def __init__(self, client: firestore.Client, runs_collection: str = "runs") -> None:
        self._client = client
        self._runs = client.collection(runs_collection)

    def _run_ref(self, run_id: str):
        return self._runs.document(run_id)

    def create_run(self, run: Run) -> None:
        ref = self._run_ref(run.run_id)
        if ref.get().exists:
            raise ValueError(f"run {run.run_id} already exists")
        ref.set(_run_to_doc(run))

    def get_run(self, run_id: str) -> Run | None:
        snapshot = self._run_ref(run_id).get()
        if not snapshot.exists:
            return None
        return _doc_to_run(run_id, snapshot.to_dict() or {})

    def put_run(self, run: Run) -> None:
        self._run_ref(run.run_id).set(_run_to_doc(run))

    def try_claim(self, run_id: str, owner: str, now: datetime, expires_at: datetime) -> Run | None:
        ref = self._run_ref(run_id)
        transaction = self._client.transaction()

        @firestore.transactional
        def claim(txn) -> Run | None:
            snapshot = ref.get(transaction=txn)
            if not snapshot.exists:
                return None
            run = _doc_to_run(run_id, snapshot.to_dict() or {})
            held = (
                run.lease_owner is not None
                and run.lease_expires_at is not None
                and run.lease_expires_at > now
                and run.lease_owner != owner
            )
            if held:
                return None
            claimed = replace(
                run,
                status=RunStatus.RUNNING,
                lease_owner=owner,
                lease_expires_at=expires_at,
                updated_at=now,
            )
            txn.set(ref, _run_to_doc(claimed))
            return claimed

        return claim(transaction)

    def append_step(self, step: Step) -> None:
        self._run_ref(step.run_id).collection("steps").document(str(step.seq)).set(
            _step_to_doc(step)
        )

    def put_step(self, step: Step) -> None:
        self.append_step(step)

    def steps(self, run_id: str) -> list[Step]:
        docs = self._run_ref(run_id).collection("steps").stream()
        steps = [_doc_to_step(run_id, d.to_dict() or {}) for d in docs]
        return sorted(steps, key=lambda s: s.seq)


class FirestoreWakeStore(WakeStore):
    def __init__(self, client: firestore.Client, collection: str = "wakes") -> None:
        self._client = client
        self._wakes = client.collection(collection)

    def put_if_absent(self, wake: Wake) -> Wake:
        ref = self._wakes.document(wake.wake_id)
        transaction = self._client.transaction()

        @firestore.transactional
        def create(txn) -> Wake:
            snapshot = ref.get(transaction=txn)
            if snapshot.exists:
                return _doc_to_wake(wake.wake_id, snapshot.to_dict() or {})
            txn.set(ref, _wake_to_doc(wake))
            return wake

        return create(transaction)

    def get(self, wake_id: str) -> Wake | None:
        snapshot = self._wakes.document(wake_id).get()
        if not snapshot.exists:
            return None
        return _doc_to_wake(wake_id, snapshot.to_dict() or {})

    def put(self, wake: Wake) -> None:
        self._wakes.document(wake.wake_id).set(_wake_to_doc(wake))

    def due(self, now: datetime, limit: int) -> list[Wake]:
        # Two queries rather than one OR, because Firestore cannot express
        # "pending, or claimed with an expired lease" in a single indexed query cheaply.
        pending = (
            self._wakes.where(filter=firestore.FieldFilter("due_at", "<=", now))
            .where(filter=firestore.FieldFilter("status", "==", WakeStatus.PENDING.value))
            .limit(limit)
            .stream()
        )
        stale = (
            self._wakes.where(filter=firestore.FieldFilter("lease_expires_at", "<=", now))
            .where(filter=firestore.FieldFilter("status", "==", WakeStatus.CLAIMED.value))
            .limit(limit)
            .stream()
        )
        wakes = [_doc_to_wake(d.id, d.to_dict() or {}) for d in pending]
        wakes += [
            w
            for w in (_doc_to_wake(d.id, d.to_dict() or {}) for d in stale)
            if w.due_at <= now
        ]
        return sorted(wakes, key=lambda w: w.due_at)[:limit]

    def try_claim(self, wake_id: str, token: str, now: datetime, expires: datetime) -> Wake | None:
        ref = self._wakes.document(wake_id)
        transaction = self._client.transaction()

        @firestore.transactional
        def claim(txn) -> Wake | None:
            snapshot = ref.get(transaction=txn)
            if not snapshot.exists:
                return None
            wake = _doc_to_wake(wake_id, snapshot.to_dict() or {})
            if wake.due_at > now:
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
            txn.set(ref, _wake_to_doc(claimed))
            return claimed

        return claim(transaction)

    def for_run(self, run_id: str) -> list[Wake]:
        docs = self._wakes.where(filter=firestore.FieldFilter("run_id", "==", run_id)).stream()
        wakes = [_doc_to_wake(d.id, d.to_dict() or {}) for d in docs]
        return sorted(wakes, key=lambda w: w.due_at)


# Serialisation. Kept explicit rather than generic so a schema change is a visible diff.


def _run_to_doc(run: Run) -> dict[str, Any]:
    doc = asdict(run)
    doc["status"] = run.status.value
    doc.pop("run_id")
    return doc


def _doc_to_run(run_id: str, doc: dict[str, Any]) -> Run:
    doc = _clean(doc)
    return Run(
        run_id=run_id,
        project_id=doc["project_id"],
        kind=doc["kind"],
        status=RunStatus(doc["status"]),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
        input=doc.get("input") or {},
        last_completed_seq=int(doc.get("last_completed_seq", -1)),
        lease_owner=doc.get("lease_owner"),
        lease_expires_at=doc.get("lease_expires_at"),
        pause_reason=doc.get("pause_reason"),
    )


def _step_to_doc(step: Step) -> dict[str, Any]:
    doc = asdict(step)
    doc["status"] = step.status.value
    return doc


def _doc_to_step(run_id: str, doc: dict[str, Any]) -> Step:
    doc = _clean(doc)
    return Step(
        run_id=run_id,
        seq=int(doc["seq"]),
        agent=doc["agent"],
        status=StepStatus(doc["status"]),
        started_at=doc["started_at"],
        ended_at=doc.get("ended_at"),
        output=doc.get("output"),
        error=doc.get("error"),
        trace_id=doc.get("trace_id"),
    )


def _wake_to_doc(wake: Wake) -> dict[str, Any]:
    doc = asdict(wake)
    doc["status"] = wake.status.value
    doc.pop("wake_id")
    return doc


def _doc_to_wake(wake_id: str, doc: dict[str, Any]) -> Wake:
    doc = _clean(doc)
    return Wake(
        wake_id=wake_id,
        run_id=doc["run_id"],
        kind=doc["kind"],
        due_at=doc["due_at"],
        status=WakeStatus(doc["status"]),
        attempts=int(doc.get("attempts", 0)),
        lease_token=doc.get("lease_token"),
        lease_expires_at=doc.get("lease_expires_at"),
        payload=doc.get("payload") or {},
        cancelled_reason=doc.get("cancelled_reason"),
        last_error=doc.get("last_error"),
    )
