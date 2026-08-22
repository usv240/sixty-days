"""Knowing when to stop is the part that makes this a loop rather than a ladder.

Registering eight reminders up front is easy. The hard question is what happens after: does the
agent keep watching the routes it changed, and does it ever decide it is finished?

Getting this wrong is not symmetric. Stopping too early abandons someone mid-appeal with the clock
still running. Stopping too late means a survivor who already gathered everything keeps being told
what is missing, until the product becomes one more thing shouting at them.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sixty_days.lifecycle import State, evaluate
from sixty_days.wake_actions import DeadlineActionExecutor
from spine.wake import Wake


TODAY = date(2026, 9, 1)
DEADLINE = date(2026, 10, 4)


# --- The decision to stop ---------------------------------------------------------------


def test_a_case_with_work_left_stays_active() -> None:
    outcome = evaluate(("deed", "photo_wide"), ("deed",), today=TODAY, deadline=DEADLINE)
    assert outcome.state is State.ACTIVE
    assert outcome.terminal is False
    assert outcome.outstanding == ("photo_wide",)


def test_gathering_everything_the_letter_asked_for_resolves_the_case() -> None:
    outcome = evaluate(
        ("deed", "photo_wide"), ("deed", "photo_wide"), today=TODAY, deadline=DEADLINE
    )
    assert outcome.state is State.RESOLVED
    assert outcome.terminal is True
    assert "Nothing further is scheduled" in outcome.reason


def test_resolved_never_claims_the_appeal_will_succeed() -> None:
    """The one sentence this module must not be allowed to imply."""
    outcome = evaluate(("deed",), ("deed",), today=TODAY, deadline=DEADLINE)
    lowered = outcome.reason.lower()
    for forbidden in ["approved", "eligible", "will succeed", "accepted", "won"]:
        assert forbidden not in lowered


def test_a_requirement_with_no_route_left_stops_being_chased() -> None:
    """Persistence against something with no route left is not persistence."""
    outcome = evaluate(
        ("deed", "insurance_denial"),
        ("deed",),
        today=TODAY,
        deadline=DEADLINE,
        exhausted_keys=("insurance_denial",),
    )
    assert outcome.state is State.EXHAUSTED
    assert outcome.terminal is True
    assert "no route left" in outcome.reason


def test_a_closed_window_stops_the_reminders() -> None:
    outcome = evaluate(("deed",), (), today=date(2026, 10, 5), deadline=DEADLINE)
    assert outcome.state is State.DEADLINE_PASSED
    assert "stay available to you" in outcome.reason


def test_the_last_day_of_the_window_is_still_active() -> None:
    """Off by one here would abandon someone on the day they could still act."""
    outcome = evaluate(("deed",), (), today=DEADLINE, deadline=DEADLINE)
    assert outcome.state is State.ACTIVE
    assert outcome.days_left == 0


def test_a_case_with_no_requirements_yet_is_not_declared_finished() -> None:
    outcome = evaluate((), (), today=TODAY, deadline=DEADLINE)
    assert outcome.state is State.ACTIVE


def test_duplicate_requirements_do_not_break_the_count() -> None:
    outcome = evaluate(("deed", "deed"), ("deed",), today=TODAY, deadline=DEADLINE)
    assert outcome.state is State.RESOLVED


# --- The agent acting on that decision --------------------------------------------------


class Keeper:
    def __init__(self) -> None:
        self.chased: list[str] = []
        self.closed: list[str] = []
        self.spared: list[str] = []

    def chase_third_party(self, case, requirement_key, requested_on):
        self.chased.append(requirement_key)
        return object()

    def close(self, case, reason, except_wake_id=""):
        self.closed.append(reason)
        self.spared.append(except_wake_id)
        return 4


class Cases:
    def __init__(self, case):
        self.case = case
        self.actions: list[dict] = []
        self.requests: list[dict] = []

    def get(self, case_id):
        return self.case

    def record_due_action(self, case_id, action):
        self.actions.append(action)

    def record_prepared_request(self, case_id, prepared):
        self.requests.append(prepared)

    def record_packet(self, case_id, status, missing):
        pass


def a_case(**overrides) -> dict:
    case = {
        "case_id": "case_1",
        "run_id": "run_1",
        "letter_date": "2026-08-05",
        "deadline": DEADLINE.isoformat(),
        "requirements": [{"key": "repair_record"}, {"key": "photo_wide"}],
        "evidence": [],
        "due_actions": [],
    }
    case.update(overrides)
    return case


def chase(requirement: str) -> Wake:
    return Wake(
        wake_id="wk", run_id="run_1", kind=f"chase:{requirement}",
        due_at=datetime.now(timezone.utc),
        payload={"case_id": "case_1", "requirement": requirement},
    )


def nudge() -> Wake:
    return Wake(
        wake_id="wk_n", run_id="run_1", kind="nudge",
        due_at=datetime.now(timezone.utc), payload={"case_id": "case_1"},
    )


def test_a_finished_case_cancels_its_remaining_reminders_by_itself() -> None:
    """The whole point of closing the loop: it stops without being told to."""
    keeper = Keeper()
    case = a_case(evidence=[
        {"requirement_key": "repair_record", "decision": "ready_for_review"},
        {"requirement_key": "photo_wide", "decision": "ready_for_review"},
    ])
    cases = Cases(case)

    result = DeadlineActionExecutor(
        cases, now=lambda: datetime(2026, 9, 1, tzinfo=timezone.utc), keeper=keeper
    ).execute(nudge())

    assert result["lifecycle"]["state"] == "resolved"
    assert result["lifecycle"]["cancelled_reminders"] == 4
    assert keeper.closed, "the case should have closed itself"


def test_an_unfinished_case_keeps_working_and_cancels_nothing() -> None:
    keeper = Keeper()
    cases = Cases(a_case())

    result = DeadlineActionExecutor(
        cases, now=lambda: datetime(2026, 9, 1, tzinfo=timezone.utc), keeper=keeper
    ).execute(nudge())

    assert result["lifecycle"]["state"] == "active"
    assert keeper.closed == []


def test_a_changed_route_gets_its_own_follow_up_check() -> None:
    """Rerouting once and then not watching the new route is the bug this prevents."""
    keeper = Keeper()
    cases = Cases(a_case(requirements=[{"key": "occupancy"}, {"key": "deed"}]))

    result = DeadlineActionExecutor(
        cases, now=lambda: datetime(2026, 8, 20, tzinfo=timezone.utc), keeper=keeper
    ).execute(chase("occupancy"))

    if result["replan"]["changed"] and result["replan"]["needs_request"]:
        assert result["follow_up_scheduled"] is True
        assert keeper.chased == [result["replan"]["alternative_key"]]


def test_a_route_the_applicant_controls_needs_no_follow_up_on_anyone_else() -> None:
    keeper = Keeper()
    cases = Cases(a_case())

    result = DeadlineActionExecutor(
        cases, now=lambda: datetime(2026, 9, 1, tzinfo=timezone.utc), keeper=keeper
    ).execute(chase("repair_record"))

    assert result["replan"]["alternative_key"] == "photo_wide"
    assert result["follow_up_scheduled"] is False
    assert keeper.chased == []


def test_a_requirement_handed_to_legal_aid_stops_holding_the_case_open() -> None:
    """Otherwise a case with one unobtainable record never finishes and never stops nagging."""
    keeper = Keeper()
    case = a_case(
        requirements=[{"key": "deed"}, {"key": "insurance_denial"}],
        evidence=[{"requirement_key": "deed", "decision": "ready_for_review"}],
        due_actions=[{"replan": {"handoff": "legal_aid", "failed_key": "insurance_denial"}}],
    )
    cases = Cases(case)

    result = DeadlineActionExecutor(
        cases, now=lambda: datetime(2026, 9, 1, tzinfo=timezone.utc), keeper=keeper
    ).execute(nudge())

    assert result["lifecycle"]["state"] == "exhausted"
    assert keeper.closed


def test_without_a_keeper_the_executor_still_works_and_simply_does_not_cancel() -> None:
    """Local tests and the replay path construct it bare; that must stay valid."""
    cases = Cases(a_case())
    result = DeadlineActionExecutor(cases).execute(nudge())
    assert result["action"] == "evidence_reminder_due"
    assert result["lifecycle"]["state"] == "active"


def test_closing_a_case_never_claims_an_external_side_effect() -> None:
    keeper = Keeper()
    case = a_case(evidence=[
        {"requirement_key": "repair_record", "decision": "ready_for_review"},
        {"requirement_key": "photo_wide", "decision": "ready_for_review"},
    ])
    result = DeadlineActionExecutor(
        Cases(case), now=lambda: datetime(2026, 9, 1, tzinfo=timezone.utc), keeper=keeper
    ).execute(nudge())
    assert result["external_side_effect"] is False


def test_closing_never_cancels_the_wake_that_is_running() -> None:
    """cancel_run sweeps CLAIMED wakes too, and the running one is CLAIMED.

    Without excluding it the dispatcher would immediately overwrite the cancellation with DONE, and
    the count shown to the applicant would claim one more cancelled reminder than there ever was.
    """
    keeper = Keeper()
    case = a_case(evidence=[
        {"requirement_key": "repair_record", "decision": "ready_for_review"},
        {"requirement_key": "photo_wide", "decision": "ready_for_review"},
    ])
    wake = nudge()

    DeadlineActionExecutor(
        Cases(case), now=lambda: datetime(2026, 9, 1, tzinfo=timezone.utc), keeper=keeper
    ).execute(wake)

    assert keeper.spared == [wake.wake_id]


def test_a_case_exhausted_by_this_very_wake_closes_now_not_next_time() -> None:
    """The stored case is written after this action, so convergence must fold the action in.

    Otherwise a case that runs out of routes on its final reminder is never noticed at all: there
    is no next wake to notice it.
    """
    keeper = Keeper()
    case = a_case(
        requirements=[{"key": "deed"}, {"key": "insurance_denial"}],
        evidence=[{"requirement_key": "deed", "decision": "ready_for_review"}],
        due_actions=[],
    )

    result = DeadlineActionExecutor(
        Cases(case), now=lambda: datetime(2026, 9, 1, tzinfo=timezone.utc), keeper=keeper
    ).execute(chase("insurance_denial"))

    assert result["replan"]["handoff"] == "legal_aid"
    assert result["lifecycle"]["state"] == "exhausted"
    assert keeper.closed, "the case should have closed on this wake, not the next one"
