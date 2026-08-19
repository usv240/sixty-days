from datetime import timedelta

import pytest

from spine.clock import MemoryClockStateStore, SimulatedClock
from spine.state import (
    LeaseLost,
    MemoryStateStore,
    Runner,
    RunStatus,
    StepDef,
    StepStatus,
)


@pytest.fixture
def clock():
    return SimulatedClock(MemoryClockStateStore())


@pytest.fixture
def store():
    return MemoryStateStore()


def test_run_executes_all_steps_in_order(store, clock):
    seen = []
    steps = [
        StepDef("intake", lambda key, prior: seen.append("intake") or "isolates"),
        StepDef("curator", lambda key, prior: seen.append("curator") or "antibiogram"),
        StepDef("drafter", lambda key, prior: seen.append("drafter") or "recommendation"),
    ]
    runner = Runner(store, clock, owner="worker-a")
    run_id = runner.start("test-application", "course-review")
    run = runner.execute(run_id, steps)

    assert seen == ["intake", "curator", "drafter"]
    assert run.status is RunStatus.DONE
    assert run.last_completed_seq == 2
    assert [s.status for s in store.steps(run_id)] == [StepStatus.DONE] * 3


def test_step_receives_prior_outputs(store, clock):
    steps = [
        StepDef("a", lambda key, prior: 1),
        StepDef("b", lambda key, prior: prior[0] + 1),
        StepDef("c", lambda key, prior: prior[1] + 1),
    ]
    runner = Runner(store, clock, owner="worker-a")
    run_id = runner.start("test-application", "chain")
    runner.execute(run_id, steps)
    assert store.steps(run_id)[-1].output == 3


def test_resume_after_crash_does_not_repeat_completed_work(store, clock):
    """The core resumability guarantee. Kill the worker mid run, restart, finish the job."""
    calls = {"intake": 0, "curator": 0, "drafter": 0}

    def counted(name, *, boom=False):
        def fn(key, prior):
            calls[name] += 1
            if boom:
                raise RuntimeError("container killed")
            return name

        return fn

    crashing = [
        StepDef("intake", counted("intake")),
        StepDef("curator", counted("curator")),
        StepDef("drafter", counted("drafter", boom=True)),
    ]

    runner = Runner(store, clock, owner="worker-a")
    run_id = runner.start("test-application", "course-review")

    with pytest.raises(RuntimeError, match="container killed"):
        runner.execute(run_id, crashing)

    assert calls == {"intake": 1, "curator": 1, "drafter": 1}
    assert store.get_run(run_id).status is RunStatus.FAILED
    assert store.get_run(run_id).last_completed_seq == 1

    healthy = [
        StepDef("intake", counted("intake")),
        StepDef("curator", counted("curator")),
        StepDef("drafter", counted("drafter")),
    ]
    resumed = Runner(store, clock, owner="worker-b")
    run = resumed.execute(run_id, healthy)

    # intake and curator are NOT re-executed. Only the failed step runs again.
    assert calls == {"intake": 1, "curator": 1, "drafter": 2}
    assert run.status is RunStatus.DONE


def test_idempotency_key_is_stable_across_replays(store, clock):
    """Rules.md line 838: a resumable agent must not order two laptops."""
    keys = []

    def record(key, prior):
        keys.append(key)
        if len(keys) == 1:
            raise RuntimeError("crash on first attempt")
        return "ok"

    steps = [StepDef("notify", record)]
    runner = Runner(store, clock, owner="worker-a")
    run_id = runner.start("alternate-test-application", "notify")

    with pytest.raises(RuntimeError):
        runner.execute(run_id, steps)
    runner.execute(run_id, steps)

    assert len(keys) == 2
    assert keys[0] == keys[1], "a replay must present the same key so the tool can deduplicate"
    assert keys[0] == f"{run_id}:0"


def test_side_effect_deduplicates_on_the_key(store, clock):
    """End to end proof: the pharmacist is paged once, not twice."""
    pages_sent: set[str] = set()
    attempts = {"n": 0}

    def page_pharmacist(key, prior):
        attempts["n"] += 1
        if key in pages_sent:
            return "already paged"
        if attempts["n"] == 1:
            raise RuntimeError("crash after deciding, before recording")
        pages_sent.add(key)
        return "paged"

    steps = [StepDef("router", page_pharmacist)]
    runner = Runner(store, clock, owner="worker-a")
    run_id = runner.start("test-application", "page")

    with pytest.raises(RuntimeError):
        runner.execute(run_id, steps)
    runner.execute(run_id, steps)

    assert len(pages_sent) == 1


def test_second_worker_cannot_claim_a_held_run(store, clock):
    runner_a = Runner(store, clock, owner="worker-a")
    run_id = runner_a.start("test-application", "course-review")
    runner_a.claim(run_id)

    runner_b = Runner(store, clock, owner="worker-b")
    with pytest.raises(LeaseLost):
        runner_b.claim(run_id)


def test_expired_lease_becomes_claimable_again(store, clock):
    """A crashed worker must not wedge a run forever."""
    runner_a = Runner(store, clock, owner="worker-a", lease_seconds=90)
    run_id = runner_a.start("test-application", "course-review")
    runner_a.claim(run_id)

    clock.advance(timedelta(seconds=91))

    runner_b = Runner(store, clock, owner="worker-b")
    claimed = runner_b.claim(run_id)
    assert claimed.lease_owner == "worker-b"


def test_same_worker_can_reclaim_its_own_lease(store, clock):
    runner = Runner(store, clock, owner="worker-a")
    run_id = runner.start("test-application", "course-review")
    runner.claim(run_id)
    assert runner.claim(run_id).lease_owner == "worker-a"


def test_execute_is_a_noop_on_a_finished_run(store, clock):
    calls = {"n": 0}

    def bump(key, prior):
        calls["n"] += 1
        return calls["n"]

    steps = [StepDef("a", bump)]
    runner = Runner(store, clock, owner="worker-a")
    run_id = runner.start("test-application", "once")
    runner.execute(run_id, steps)
    runner.execute(run_id, steps)
    assert calls["n"] == 1


def test_pause_records_a_reason_and_releases_the_lease(store, clock):
    """Used when the Verifier circuit breaks and a human is required."""
    runner = Runner(store, clock, owner="worker-a")
    run_id = runner.start("test-application", "course-review")
    runner.claim(run_id)
    paused = runner.pause(run_id, "claim rejected three times, escalating")

    assert paused.status is RunStatus.PAUSED
    assert "three times" in paused.pause_reason
    assert paused.lease_owner is None


def test_lease_expiry_mid_run_is_detected(store, clock):
    """A worker that has lost its lease must stop rather than write stale results."""

    def slow(key, prior):
        clock.advance(timedelta(seconds=200))
        return "slow"

    steps = [StepDef("a", slow), StepDef("b", lambda key, prior: "b")]
    runner = Runner(store, clock, owner="worker-a", lease_seconds=90)
    run_id = runner.start("test-application", "slow")

    with pytest.raises(LeaseLost, match="expired mid run"):
        runner.execute(run_id, steps)
