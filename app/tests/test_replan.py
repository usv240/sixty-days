"""Rerouting is a decision the agent makes alone, so it has to be wrong in safe directions.

A reminder that says "consider a different document" cannot hurt anyone. An agent that actually
changes the plan can: it could drop a requirement the letter asked for, invent an alternative the
guidance does not support, or keep waiting on a silent insurer until the deadline passes.

These tests pin the three rules that make the autonomy defensible. The letter's requirement is never
changed, only the route to it. Routes the applicant controls win when time is short, because the
failure being handled is that someone else is not replying. And with no real alternative it refuses
and hands over, rather than producing a confident wrong answer.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sixty_days.letters import REQUIREMENTS, Deficiency, Source
from sixty_days.replan import (
    THIRD_PARTY_TURNAROUND_DAYS,
    alternatives_for,
    decide,
)
from sixty_days.wake_actions import DeadlineActionExecutor
from spine.wake import Wake


def keys_for(deficiency: Deficiency) -> list[str]:
    return [r.key for r in REQUIREMENTS[deficiency]]


# --- The decision ----------------------------------------------------------------------


def test_a_silent_contractor_is_rerouted_to_something_the_applicant_controls() -> None:
    """The damage requirement can be met by a contractor record or by the applicant's own photo."""
    decision = decide("repair_record", days_left=40)

    assert decision.changed is True
    assert decision.alternative_key == "photo_wide"
    assert decision.alternative_source == Source.APPLICANT_ONLY.value
    assert "gone unanswered" in decision.reason


def test_the_requirement_from_the_letter_is_never_changed_only_the_route() -> None:
    decision = decide("repair_record", days_left=40)
    assert decision.deficiency == Deficiency.DAMAGE_EVIDENCE.value
    assert decision.alternative_key in keys_for(Deficiency.DAMAGE_EVIDENCE)


def test_with_little_time_left_it_refuses_to_wait_on_another_organisation() -> None:
    """The judgement that makes this more than a lookup: time changes the right answer."""
    roomy = decide("repair_record", days_left=40)
    tight = decide("repair_record", days_left=5)

    assert roomy.changed and tight.changed
    assert tight.alternative_source == Source.APPLICANT_ONLY.value
    assert f"{tight.days_left} days remain" in tight.reason
    assert "too few to rely on another organisation" in tight.reason


def test_the_turnaround_threshold_is_a_boundary_not_a_vibe() -> None:
    inside = decide("repair_record", days_left=THIRD_PARTY_TURNAROUND_DAYS)
    outside = decide("repair_record", days_left=THIRD_PARTY_TURNAROUND_DAYS + 1)
    assert "too few to rely on" in inside.reason
    assert "gone unanswered" in outside.reason


def test_a_requirement_with_no_alternative_hands_over_instead_of_guessing() -> None:
    """The insurer's own decision letter has no substitute. Inventing one would be worse."""
    decision = decide("insurance_denial", days_left=30)

    assert decision.changed is False
    assert decision.handoff == "legal_aid"
    assert "no other route" in decision.reason
    assert decision.alternative_key == ""


def test_evidence_that_already_arrived_does_not_trigger_a_reroute() -> None:
    decision = decide("repair_record", days_left=30, satisfied_keys=("repair_record",))
    assert decision.changed is False
    assert "already arrived" in decision.reason


def test_an_alternative_that_is_already_satisfied_needs_no_new_request() -> None:
    decision = decide("repair_record", days_left=30, satisfied_keys=("photo_wide",))
    assert decision.changed is False
    assert decision.needs_request is False
    assert "No new request is needed" in decision.reason


def test_an_unknown_requirement_is_reported_rather_than_rerouted() -> None:
    decision = decide("not_a_real_requirement", days_left=30)
    assert decision.changed is False
    assert "not in the routed plan" in decision.reason


def test_alternatives_prefer_the_applicant_then_public_records_then_third_parties() -> None:
    options = alternatives_for("repair_record")
    sources = [o.source for o in options]
    assert sources == sorted(sources, key=lambda s: [
        Source.APPLICANT_ONLY, Source.PUBLIC_RECORD, Source.THIRD_PARTY, Source.LEGAL_AID
    ].index(s))
    assert "repair_record" not in [o.key for o in options]


# --- The action it takes ---------------------------------------------------------------


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


def chase_wake(requirement: str) -> Wake:
    return Wake(
        wake_id="wk_test",
        run_id="run_test",
        kind=f"chase:{requirement}",
        due_at=datetime.now(timezone.utc),
        payload={"case_id": "case_1", "requirement": requirement},
    )


def case_with_deadline(days_ahead: int) -> dict:
    due = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).date()
    return {"case_id": "case_1", "deadline": due.isoformat(), "evidence": []}


def test_the_due_wake_changes_the_route_rather_than_leaving_a_note() -> None:
    """The whole point: waking up produces a changed plan, not a sentence about changing one."""
    cases = Cases(case_with_deadline(40))
    result = DeadlineActionExecutor(cases).execute(chase_wake("repair_record"))

    assert result["action"] == "evidence_route_changed"
    assert result["replan"]["alternative_key"] == "photo_wide"
    assert cases.actions and cases.actions[0]["action"] == "evidence_route_changed"


def test_a_reroute_that_needs_a_new_request_drafts_it_without_sending() -> None:
    """The applicant wakes up to a written request, not to a task."""
    cases = Cases(case_with_deadline(40))
    result = DeadlineActionExecutor(cases).execute(chase_wake("occupancy"))

    if result["replan"]["needs_request"]:
        assert result["drafted_request"] is True
        assert cases.requests, "a request should have been drafted"
        drafted = cases.requests[0]
        assert drafted["status"] == "prepared_for_applicant"
        assert drafted["delivery"] == "applicant_sends"
        assert "Nothing was sent" in drafted["safety"]


def test_no_reroute_still_records_a_visible_action_and_contacts_nobody() -> None:
    cases = Cases(case_with_deadline(30))
    result = DeadlineActionExecutor(cases).execute(chase_wake("insurance_denial"))

    assert result["action"] == "third_party_reply_check_due"
    assert result["replan"]["handoff"] == "legal_aid"
    assert result["external_side_effect"] is False
    assert cases.requests == []


def test_the_deadline_drives_the_decision_the_agent_makes_unattended() -> None:
    roomy = DeadlineActionExecutor(Cases(case_with_deadline(45))).execute(chase_wake("repair_record"))
    tight = DeadlineActionExecutor(Cases(case_with_deadline(4))).execute(chase_wake("repair_record"))

    assert "gone unanswered" in roomy["detail"]
    assert "too few to rely on another organisation" in tight["detail"]


def test_a_case_with_no_deadline_still_reroutes_without_crashing() -> None:
    cases = Cases({"case_id": "case_1", "evidence": []})
    result = DeadlineActionExecutor(cases).execute(chase_wake("repair_record"))
    assert result["action"] == "evidence_route_changed"
    assert result["replan"]["days_left"] is None


def test_accepted_evidence_in_the_case_stops_a_pointless_reroute() -> None:
    case = case_with_deadline(30)
    case["evidence"] = [{"requirement_key": "repair_record", "decision": "ready_for_review"}]
    result = DeadlineActionExecutor(Cases(case)).execute(chase_wake("repair_record"))

    assert result["action"] == "third_party_reply_check_due"
    assert "already arrived" in result["detail"]


def test_rerouting_never_claims_an_external_side_effect() -> None:
    for requirement in ["repair_record", "occupancy", "insurance_denial"]:
        cases = Cases(case_with_deadline(35))
        result = DeadlineActionExecutor(cases).execute(chase_wake(requirement))
        assert result["external_side_effect"] is False
        for drafted in cases.requests:
            assert drafted["delivery"] == "applicant_sends"


def test_the_clock_that_owns_the_wake_decides_how_much_time_is_left() -> None:
    """The demo runs on a simulated clock; judging real time here would be wrong by weeks.

    A case advanced to day 55 of a 60-day window has five days left, and the agent must reason
    about that rather than about the wall clock, or it will happily start another third-party
    request that cannot possibly return in time.
    """
    from datetime import date

    case = {"case_id": "case_1", "deadline": "2026-10-04", "evidence": []}

    early = DeadlineActionExecutor(
        Cases(case), now=lambda: datetime(2026, 8, 10, tzinfo=timezone.utc)
    ).execute(chase_wake("repair_record"))
    late = DeadlineActionExecutor(
        Cases(case), now=lambda: datetime(2026, 9, 30, tzinfo=timezone.utc)
    ).execute(chase_wake("repair_record"))

    assert early["replan"]["days_left"] == (date(2026, 10, 4) - date(2026, 8, 10)).days
    assert late["replan"]["days_left"] == 4
    assert "too few to rely on another organisation" in late["detail"]
    assert "gone unanswered" in early["detail"]


def test_a_plain_datetime_works_as_well_as_a_clock_function() -> None:
    executor = DeadlineActionExecutor(
        Cases({"case_id": "case_1", "deadline": "2026-10-04", "evidence": []}),
        now=datetime(2026, 10, 1, tzinfo=timezone.utc),
    )
    result = executor.execute(chase_wake("repair_record"))
    assert result["replan"]["days_left"] == 3
