from datetime import datetime, timezone
from io import BytesIO

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfReader

from service.sixty_days_routes import build_sixty_days_router
from spine.clock import ClockState, MemoryClockStateStore, SimulatedClock
from spine.wake import MemoryWakeStore, WakeScheduler


class Snapshot:
    def __init__(self, document):
        self._document = document
        self.id = document.id
        self.reference = document

    @property
    def exists(self):
        return self._document.data is not None

    def to_dict(self):
        return dict(self._document.data or {})


class Document:
    def __init__(self, doc_id):
        self.id = doc_id
        self.data = None

    def set(self, data):
        self.data = dict(data)

    def get(self):
        return Snapshot(self)


class Collection:
    def __init__(self):
        self.documents = {}

    def document(self, doc_id):
        return self.documents.setdefault(doc_id, Document(doc_id))

    def stream(self):
        return [Snapshot(doc) for doc in self.documents.values() if doc.data is not None]


class FakeFirestore:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, Collection())


class FakeRunner:
    def __init__(self):
        self.count = 0

    def start(self, project, kind, input_data):
        self.count += 1
        return f"run_{self.count:08d}"


def client():
    app = FastAPI()
    clock = SimulatedClock(
        MemoryClockStateStore(
            ClockState(frozen_at=datetime(2026, 8, 8, 9, tzinfo=timezone.utc))
        )
    )
    scheduler = WakeScheduler(MemoryWakeStore(), clock)
    runner = FakeRunner()
    app.include_router(
        build_sixty_days_router(FakeFirestore(), clock, lambda: scheduler, lambda: runner)
    )
    return TestClient(app)


def test_fixture_catalogue_reports_the_measured_live_calls():
    response = client().get("/sixty-days/fixtures")
    assert response.status_code == 200
    assert response.json()["measured"] == {"correct": 20, "total": 20, "recorded_calls": 4}
    assert len(response.json()["fixtures"]) == 4


def test_open_case_decodes_reasons_routes_evidence_and_registers_wakes():
    response = client().post(
        "/sixty-days/cases", json={"fixture": "ownership", "applicant_ref": "demo-1"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["deficiencies"][0]["kind"] == "ownership"
    assert body["requirements"][0]["routed_to"] == "county recorder"
    assert len(body["wakes"]) == 8
    assert body["redacted"] >= 1


def test_short_window_preserves_partial_packet_and_final_alert():
    body = client().post("/sixty-days/cases", json={"fixture": "short_window"}).json()
    wakes = {wake["kind"]: wake for wake in body["wakes"]}
    assert wakes["build_partial"]["day"] == 37
    assert wakes["final_alert"]["day"] == 43
    assert body["deadline_conflict"]


def test_case_is_persisted_without_raw_transcription():
    test_client = client()
    opened = test_client.post("/sixty-days/cases", json={"fixture": "ownership"}).json()
    stored = test_client.get(f"/sixty-days/cases/{opened['case_id']}").json()
    assert stored["status"] == "gathering"
    assert "transcription" not in stored
    assert "raw" not in stored


def test_bad_fixture_name_is_rejected_not_sanitized_to_another_file():
    response = client().get("/sixty-days/fixtures/ownership%2E%2E")
    assert response.status_code == 400


def test_third_party_chase_is_registered_and_capped_at_deadline():
    test_client = client()
    opened = test_client.post("/sixty-days/cases", json={"fixture": "occupancy"}).json()
    response = test_client.post(
        f"/sixty-days/cases/{opened['case_id']}/chase",
        json={"requirement_key": "occupancy", "requested_on": "2026-09-20"},
    )
    assert response.status_code == 200
    assert response.json()["due_at"].startswith(opened["deadline"])


def test_recorded_evidence_catalogue_reports_measured_checks():
    body = client().get("/sixty-days/evidence/fixtures").json()
    assert body["fixtures"] == ["damage_close_bad", "damage_wide_good"]
    assert body["measured"] == {"correct": 6, "total": 6, "recorded_calls": 2}


def test_evidence_screening_is_actionable_and_persists_no_raw_image():
    test_client = client()
    opened = test_client.post(
        "/sixty-days/cases", json={"fixture": "damage_and_insurance"}
    ).json()
    retake = test_client.post(
        f"/sixty-days/cases/{opened['case_id']}/evidence/check",
        json={"fixture": "damage_close_bad", "requirement_key": "photo_wide"},
    ).json()
    assert retake["decision"] == "retake"
    assert "Step back" in retake["guidance"]
    ready = test_client.post(
        f"/sixty-days/cases/{opened['case_id']}/evidence/check",
        json={"fixture": "damage_wide_good", "requirement_key": "photo_wide"},
    ).json()
    assert ready["decision"] == "ready_for_review"
    assert "accept" in ready["safety"]
    stored = test_client.get(f"/sixty-days/cases/{opened['case_id']}").json()
    assert stored["evidence"][0]["checks"]["damage_visible"] is True
    assert "image" not in stored["evidence"][0]
    assert "transcription" not in stored["evidence"][0]


def test_prepare_and_track_request_does_not_send_it():
    test_client = client()
    opened = test_client.post("/sixty-days/cases", json={"fixture": "occupancy"}).json()
    response = test_client.post(
        f"/sixty-days/cases/{opened['case_id']}/requests/prepare",
        json={"requirement_key": "occupancy", "requested_on": "2026-08-10"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["delivery"] == "applicant_sends"
    assert body["status"] == "prepared_for_applicant"
    assert "Nothing was sent" in body["safety"]
    assert body["tracking"]["wake_id"]


def test_applicant_only_item_cannot_enter_third_party_request_flow():
    test_client = client()
    opened = test_client.post(
        "/sixty-days/cases", json={"fixture": "damage_and_insurance"}
    ).json()
    response = test_client.post(
        f"/sixty-days/cases/{opened['case_id']}/requests/prepare",
        json={"requirement_key": "photo_wide", "requested_on": "2026-08-10"},
    )
    assert response.status_code == 422


def test_partial_packet_pdf_is_grounded_draft_and_does_not_persist_statement():
    test_client = client()
    opened = test_client.post(
        "/sixty-days/cases", json={"fixture": "damage_and_insurance"}
    ).json()
    test_client.post(
        f"/sixty-days/cases/{opened['case_id']}/evidence/check",
        json={"fixture": "damage_wide_good", "requirement_key": "photo_wide"},
    )
    response = test_client.post(
        f"/sixty-days/cases/{opened['case_id']}/packet.pdf",
        json={"applicant_statement": "Please review my photographs and records."},
    )
    assert response.status_code == 200
    assert response.headers["x-submission-status"] == "not-submitted"
    text = "\n".join(
        page.extract_text() or "" for page in PdfReader(BytesIO(response.content)).pages
    )
    assert "DRAFT APPEAL PACKET" in text
    assert " ".join(opened["deficiencies"][0]["quoted_text"].split()) in " ".join(text.split())
    assert "Items still missing" in text
    stored = test_client.get(f"/sixty-days/cases/{opened['case_id']}").json()
    assert stored["packet"]["applicant_statement_persisted"] is False
    assert "Please review my photographs" not in str(stored)


def test_router_exposes_no_bulk_delete_or_submission_endpoint():
    test_client = client()
    schema = test_client.get("/openapi.json").json()
    paths = schema["paths"]
    assert not any(
        forbidden in path
        for path in paths
        for forbidden in ("reset", "submit", "send")
    )


def test_conformance_is_machine_checkable():
    body = client().get("/sixty-days/conformance").json()
    assert len(body["rules"]) == 6
    assert all(row["source"].startswith("https://www.fema.gov/") for row in body["rules"])
    assert all(row["implementation"] and row["test"] for row in body["rules"])
