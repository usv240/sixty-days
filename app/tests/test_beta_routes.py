import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from service.beta_routes import build_beta_router
from service.sixty_days_routes import build_sixty_days_router
from sixty_days.reader import LetterReader, LetterReplayClient
from spine.api_access import ApiKeyAuthenticator
from spine.clock import ClockState, MemoryClockStateStore, SimulatedClock
from spine.wake import MemoryWakeStore, WakeScheduler
from spine.redact import NameReviewer, RedactionError


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


SAFE_LETTER = """DE-IDENTIFIED DETERMINATION LETTER
Date: August 1, 2026
Decision: Assistance is not approved at this time.
We are unable to verify ownership of the damaged dwelling.
Your appeal must be received by September 30, 2026.
"""


def client() -> TestClient:
    root = Path(__file__).resolve().parent.parent
    recording = json.loads(
        (root / "fixtures" / "letter_recordings" / "ownership.json").read_text()
    )
    firestore = FakeFirestore()
    clock = SimulatedClock(
        MemoryClockStateStore(
            ClockState(frozen_at=datetime(2026, 8, 8, 9, tzinfo=timezone.utc))
        )
    )
    scheduler = WakeScheduler(MemoryWakeStore(), clock)
    runner = FakeRunner()
    auth = ApiKeyAuthenticator.from_plaintext({
        "aid-one-key": {
            "tenant_id": "aid_one",
            "label": "Aid one",
            "scopes": ["sixty-days:use"],
        },
        "aid-two-key": {
            "tenant_id": "aid_two",
            "label": "Aid two",
            "scopes": ["sixty-days:use"],
        },
    })
    app = FastAPI()
    app.include_router(build_sixty_days_router(firestore, clock, lambda: scheduler, lambda: runner))
    app.include_router(build_beta_router(
        firestore,
        clock,
        lambda: scheduler,
        lambda: runner,
        auth,
        reader_factory=lambda: LetterReader(LetterReplayClient({"default": recording})),
    ))
    return TestClient(app)


def open_case(api: TestClient, key: str = "aid-one-key"):
    return api.post(
        "/v1/cases",
        headers={"X-API-Key": key},
        json={
            "document": SAFE_LETTER,
            "applicant_ref": "SUBJECT-001",
            "disaster_ref": "DR-TEST-001",
            "acknowledge_deidentified": True,
        },
    )


def test_beta_opens_grounded_case_without_persisting_raw_letter():
    api = client()
    opened = open_case(api)
    assert opened.status_code == 201
    assert opened.json()["raw_document_persisted"] is False
    stored = api.get(
        f"/v1/cases/{opened.json()['case_id']}", headers={"X-API-Key": "aid-one-key"}
    ).json()
    assert "document" not in stored
    assert "raw" not in stored
    assert "transcription" not in stored


def test_obvious_identifier_is_rejected_before_model_processing():
    api = client()
    response = api.post(
        "/v1/cases",
        headers={"X-API-Key": "aid-one-key"},
        json={
            "document": SAFE_LETTER + "\nApplicant: MARY-JANE OKONKWO",
            "applicant_ref": "SUBJECT-001",
            "disaster_ref": "DR-TEST-001",
            "acknowledge_deidentified": True,
        },
    )
    assert response.status_code == 422
    assert "PERSON" in response.json()["detail"]


def test_case_is_invisible_to_another_api_key_tenant():
    api = client()
    opened = open_case(api).json()
    assert api.get(
        f"/v1/cases/{opened['case_id']}", headers={"X-API-Key": "aid-two-key"}
    ).status_code == 404
    assert api.get("/v1/cases", headers={"X-API-Key": "aid-two-key"}).json() == {
        "cases": []
    }
    assert api.get(f"/sixty-days/cases/{opened['case_id']}").status_code == 404
    assert all(
        item["case_id"] != opened["case_id"]
        for item in api.get("/sixty-days/cases").json()["cases"]
    )


def test_acknowledgement_and_pseudonymous_reference_are_mandatory():
    api = client()
    response = api.post(
        "/v1/cases",
        headers={"X-API-Key": "aid-one-key"},
        json={
            "document": SAFE_LETTER,
            "applicant_ref": "Mara Rivera",
            "disaster_ref": "DR-TEST-001",
            "acknowledge_deidentified": False,
        },
    )
    assert response.status_code == 422

class BrokenReviewer(NameReviewer):
    def find_names(self, text: str) -> list[str]:
        raise RedactionError("reviewer unavailable")


def test_privacy_reviewer_outage_fails_closed_as_service_unavailable():
    root = Path(__file__).resolve().parent.parent
    recording = json.loads(
        (root / "fixtures" / "letter_recordings" / "ownership.json").read_text()
    )
    firestore = FakeFirestore()
    clock = SimulatedClock(
        MemoryClockStateStore(
            ClockState(frozen_at=datetime(2026, 8, 8, 9, tzinfo=timezone.utc))
        )
    )
    scheduler = WakeScheduler(MemoryWakeStore(), clock)
    auth = ApiKeyAuthenticator.from_plaintext({
        "aid-one-key": {
            "tenant_id": "aid_one",
            "label": "Aid one",
            "scopes": ["sixty-days:use"],
        }
    })
    app = FastAPI()
    app.include_router(build_beta_router(
        firestore,
        clock,
        lambda: scheduler,
        lambda: FakeRunner(),
        auth,
        reader_factory=lambda: LetterReader(
            LetterReplayClient({"default": recording}), reviewer=BrokenReviewer()
        ),
    ))
    response = TestClient(app).post(
        "/v1/cases",
        headers={"X-API-Key": "aid-one-key"},
        json={
            "document": SAFE_LETTER,
            "applicant_ref": "SUBJECT-001",
            "disaster_ref": "DR-TEST-001",
            "acknowledge_deidentified": True,
        },
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Privacy review unavailable; the document was not processed."

