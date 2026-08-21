"""The live-call proof has to be worth trusting, which means it must be able to fail.

A button that always reports success proves nothing. These tests pin that the live route scores by
exactly the fields the published recorded run was scored on, that a wrong answer is reported as
wrong, that the image is sent without an accompanying transcript, and that the spend ceiling is
charged only when a call actually happened.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sixty_days.live_check import grade_against_truth, run_live_check
from sixty_days.reader import LetterExtractionError, LetterReplayClient
from spine.issuance_budget import IssuanceBudget, MemoryCounterStore


SCANS = Path(__file__).resolve().parents[1] / "fixtures" / "letter_scans"
RECORDINGS = Path(__file__).resolve().parents[1] / "fixtures" / "letter_recordings"
FIXTURE = "damage_and_insurance"
NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


def recorded_client(**mutations) -> LetterReplayClient:
    """Replay the committed response, optionally corrupted, standing in for the live model."""
    response = json.loads((RECORDINGS / f"{FIXTURE}.json").read_text(encoding="utf-8"))
    response.update(mutations)
    return LetterReplayClient({"default": response})


def test_a_correct_reading_scores_full_marks() -> None:
    result = run_live_check(recorded_client(), SCANS, FIXTURE)

    assert result.correct == result.total == 5
    assert result.fixture == FIXTURE
    assert result.model == "gemini-3.5-flash"
    assert result.elapsed_ms >= 0
    assert result.as_dict()["replayed"] is False


def test_a_wrong_date_is_reported_as_wrong_rather_than_smoothed_over() -> None:
    """The whole value of this route is that it can come back red."""
    result = run_live_check(recorded_client(letter_date="2026-01-01"), SCANS, FIXTURE)

    assert result.fields["letter_date"] is False
    assert result.correct < result.total


def test_the_live_score_uses_the_same_fields_as_the_published_run() -> None:
    """Scoring a live call more leniently would make the published 20/20 meaningless."""
    from scripts import record_letters

    class Result:
        pass

    reader_result = _read(recorded_client())
    truth = json.loads((SCANS / f"{FIXTURE}.truth.json").read_text(encoding="utf-8"))

    live_fields = grade_against_truth(reader_result, truth)
    published = record_letters.grade(FIXTURE, reader_result, truth)

    assert set(live_fields) == set(published["fields"])
    assert live_fields == published["fields"]


def test_an_unknown_fixture_is_refused_rather_than_invented() -> None:
    with pytest.raises(LetterExtractionError):
        run_live_check(recorded_client(), SCANS, "no_such_letter")


def test_the_image_is_sent_without_a_transcript_to_copy_from() -> None:
    """A correct answer read off supplied text would not be evidence that the model can read."""
    seen: dict[str, object] = {}

    class Spy(LetterReplayClient):
        def extract(self, system, document, schema, image=None):
            seen["document"] = document
            seen["image_bytes"] = len(image or b"")
            return super().extract(system, document, schema, image=image)

    response = json.loads((RECORDINGS / f"{FIXTURE}.json").read_text(encoding="utf-8"))
    run_live_check(Spy({"default": response}), SCANS, FIXTURE)

    assert seen["image_bytes"] > 0
    assert not str(seen["document"]).strip()


def test_the_result_never_leaks_the_letter_text_it_read() -> None:
    payload = run_live_check(recorded_client(), SCANS, FIXTURE).as_dict()
    blob = json.dumps(payload).lower()

    for identifier in ["elise", "nguyen", "mockingbird", "demo-1159"]:
        assert identifier not in blob


# --- The spend ceiling ------------------------------------------------------------------


def test_a_visitor_gets_a_small_allowance_and_is_told_when_it_is_gone() -> None:
    budget = IssuanceBudget(
        MemoryCounterStore(), daily_cap=60, per_caller_cap=2,
        caller_denied="You have used this demo's live-call allowance for today.",
    )
    assert budget.check(NOW, "visitor").allowed is True
    budget.consume(NOW, "visitor")
    budget.consume(NOW, "visitor")

    decision = budget.check(NOW, "visitor")
    assert decision.allowed is False
    assert "allowance" in decision.reason


def test_the_shared_ceiling_bounds_total_spend_across_visitors() -> None:
    budget = IssuanceBudget(MemoryCounterStore(), daily_cap=2, per_caller_cap=10)
    budget.consume(NOW, "a")
    budget.consume(NOW, "b")

    assert budget.check(NOW, "c").allowed is False


def test_a_denied_call_is_never_charged() -> None:
    """Otherwise a visitor who hits the wall pushes the day further into denial."""
    store = MemoryCounterStore()
    budget = IssuanceBudget(store, daily_cap=60, per_caller_cap=1)
    budget.consume(NOW, "visitor")
    before = dict(store.values)

    assert budget.check(NOW, "visitor").allowed is False
    assert store.values == before


def _read(client):
    from sixty_days.reader import LetterReader

    return LetterReader(client).parse(f"live_{FIXTURE}", image=(SCANS / f"{FIXTURE}.jpg").read_bytes())
