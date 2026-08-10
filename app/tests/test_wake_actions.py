from datetime import datetime, timezone

from sixty_days.wake_actions import DeadlineActionExecutor
from spine.wake import Wake


CASE = {
    "case_id": "case_demo",
    "applicant_ref": "DEMO-1",
    "disaster_ref": "DR-DEMO",
    "deadline": "2026-10-04",
    "deficiencies": [
        {
            "kind": "occupancy",
            "plain_language": "Occupancy could not be verified.",
            "quoted_text": "We could not verify that the home was your primary residence.",
        }
    ],
    "requirements": [
        {
            "key": "occupancy",
            "title": "Proof of occupancy",
            "plain_description": "A document showing occupancy.",
            "source": "third_party",
            "routed_to": "utility provider",
            "cures": "occupancy",
            "status": "pending",
        }
    ],
}


class Cases:
    def __init__(self):
        self.case = dict(CASE)
        self.packet = None
        self.actions = []

    def get(self, case_id):
        return self.case if case_id == "case_demo" else None

    def record_packet(self, case_id, status, missing):
        self.packet = {"case_id": case_id, "status": status, "missing": missing}

    def record_due_action(self, case_id, action):
        self.actions = [item for item in self.actions if item["wake_id"] != action["wake_id"]]
        self.actions.append(action)


def wake(kind, **payload):
    return Wake(
        wake_id=f"wk_{kind}",
        run_id="run_demo",
        kind=kind,
        due_at=datetime(2026, 9, 26, 9, tzinfo=timezone.utc),
        payload={"case_id": "case_demo", **payload},
    )


def test_day_52_wake_builds_and_records_partial_packet():
    cases = Cases()
    result = DeadlineActionExecutor(cases).execute(wake("build_partial"))

    assert result["action"] == "partial_packet_built"
    assert cases.packet["status"] == "partial_draft"
    assert cases.packet["missing"]
    assert cases.actions[0]["external_side_effect"] is False


def test_no_reply_wake_creates_replan_action_without_contacting_anyone():
    cases = Cases()
    result = DeadlineActionExecutor(cases).execute(
        wake("chase:occupancy", requirement="occupancy")
    )

    assert result["action"] == "third_party_reply_check_due"
    assert result["requirement"] == "occupancy"
    assert result["external_side_effect"] is False


def test_retry_replaces_the_same_visible_action_instead_of_duplicating_it():
    cases = Cases()
    executor = DeadlineActionExecutor(cases)
    due = wake("final_alert")

    executor.execute(due)
    executor.execute(due)

    assert len(cases.actions) == 1
    assert cases.actions[0]["action"] == "final_deadline_alert_due"
