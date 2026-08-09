"""Live smoke test against the real Firestore instance.

Proves the Firestore-backed stores behave like the in-memory ones the unit tests exercise.
Costs nothing: Firestore's free tier covers far more than this uses.

Run:
    python scripts/smoke_firestore.py
"""

from __future__ import annotations

import os
import sys
from datetime import timedelta

from google.cloud import firestore

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spine.clock import SimulatedClock  # noqa: E402
from spine.firestore_stores import (  # noqa: E402
    FirestoreClockStateStore,
    FirestoreStateStore,
    FirestoreWakeStore,
)
from spine.state import Runner, RunStatus, StepDef  # noqa: E402
from spine.wake import WakeScheduler  # noqa: E402

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "agentic-fleet-2026")


def main() -> int:
    client = firestore.Client(project=PROJECT)
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, ok, detail))
        print(f"  {'PASS' if ok else 'FAIL'}  {name}{'  ' + detail if detail else ''}")

    print(f"Firestore smoke test against project {PROJECT}\n")

    # 0. Clear anything a previous crashed run left behind.
    #
    # scan_due() is deliberately global: a worker scans every due wake, not just its own. That is
    # correct in production and it is why a leftover wake from an earlier run would fire here.
    # The test therefore isolates itself, and also scopes its assertions to this run below.
    stale = 0
    for doc in client.collection("wakes").stream():
        doc.reference.delete()
        stale += 1
    for doc in client.collection("runs").stream():
        for step in doc.reference.collection("steps").stream():
            step.reference.delete()
        doc.reference.delete()
        stale += 1
    client.document("sim/clock").delete()
    if stale:
        print(f"  cleared {stale} stale documents from a previous run\n")

    # 1. Shared simulated clock
    clock = SimulatedClock(FirestoreClockStateStore(client))
    start = clock.now()
    clock.advance(timedelta(days=60))
    moved = (clock.now() - start).days
    check("simulated clock persists a 60 day advance", moved == 60, f"moved {moved} days")

    # A second instance, as a second Cloud Run container would see it
    other_instance = SimulatedClock(FirestoreClockStateStore(client))
    drift = abs((other_instance.now() - clock.now()).total_seconds())
    check("all instances agree on the time", drift < 2, f"drift {drift:.2f}s")

    # 2. Runs, steps, checkpointing
    state = FirestoreStateStore(client)
    runner = Runner(state, clock, owner="smoke-worker")
    run_id = runner.start("spine-smoke", "exit-test-rehearsal", {"note": "smoke"})
    check("run created", state.get_run(run_id) is not None, run_id)

    executed: list[str] = []
    steps = [
        StepDef("intake", lambda key, prior: executed.append(key) or "isolates"),
        StepDef("curator", lambda key, prior: executed.append(key) or "antibiogram"),
    ]
    run = runner.execute(run_id, steps)
    check("run completed", run.status is RunStatus.DONE, run.status.value)
    check("both steps recorded", len(state.steps(run_id)) == 2)
    check("idempotency keys are run scoped", all(k.startswith(run_id) for k in executed))

    # 3. Lease exclusivity across workers
    contender = Runner(state, clock, owner="other-worker")
    runner.claim(run_id)
    try:
        contender.claim(run_id)
        check("second worker blocked by lease", False, "it was allowed in")
    except Exception:
        check("second worker blocked by lease", True)

    # 4. Wakes
    wakes = WakeScheduler(FirestoreWakeStore(client), clock)
    wakes.sleep_for(run_id, "deescalation_review", timedelta(hours=48))
    wakes.sleep_for(run_id, "readmission_check", timedelta(days=39))
    check("ladder registered", len(wakes.pending_for(run_id)) == 2)

    duplicate = wakes.sleep_for(run_id, "deescalation_review", timedelta(hours=48))
    check(
        "re-registration is idempotent",
        len(wakes.pending_for(run_id)) == 2,
        duplicate.wake_id,
    )

    def mine(fired_wakes):
        """scan_due is global by design. Assertions here are about this run only."""
        return [w for w in fired_wakes if w.run_id == run_id]

    early = mine(wakes.scan_due())
    check("nothing fires early", early == [], str([w.kind for w in early]))

    clock.advance(timedelta(hours=52))
    fired = mine(wakes.scan_due())
    check(
        "hour 48 wake fires on its own",
        [w.kind for w in fired] == ["deescalation_review"],
        str([w.kind for w in fired]),
    )
    for w in fired:
        wakes.complete(w.wake_id)

    clock.advance(timedelta(days=40))
    later = mine(wakes.scan_due())
    check(
        "day 39 wake fires weeks later",
        [w.kind for w in later] == ["readmission_check"],
        str([w.kind for w in later]),
    )
    for w in later:
        wakes.complete(w.wake_id)

    again = mine(wakes.scan_due())
    check("completed wakes do not fire twice", again == [], str([w.kind for w in again]))

    # 5. Cleanup so repeated runs stay cheap
    for w in FirestoreWakeStore(client).for_run(run_id):
        client.collection("wakes").document(w.wake_id).delete()
    for s in state.steps(run_id):
        client.collection("runs").document(run_id).collection("steps").document(
            str(s.seq)
        ).delete()
    client.collection("runs").document(run_id).delete()
    client.document("sim/clock").delete()
    print("\n  cleaned up test documents")

    failed = [name for name, ok, _ in checks if not ok]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
