import json

from scripts.make_letter_fixtures import LETTERS
from scripts.record_letters import grade
from sixty_days.reader import LetterReader, LetterReplayClient


def test_every_fixture_is_explicitly_synthetic_and_unbranded():
    for fixture in LETTERS.values():
        text = fixture["text"]
        assert "SYNTHETIC DEMONSTRATION" in text
        assert "No government endorsement" in text
        assert "seal" not in text.casefold()
        assert "logo" not in text.casefold()


def test_fixture_truth_contains_every_required_grading_field():
    for fixture in LETTERS.values():
        assert fixture["letter_date"]
        assert fixture["determination"] in {"denied", "partial", "approved"}
        assert fixture["stated_deadline"]
        assert fixture["deficiencies"]


def test_grader_reports_five_of_five_for_an_exact_extraction():
    fixture = LETTERS["ownership"]
    raw = {
        "transcription": fixture["text"],
        "letter_date": fixture["letter_date"],
        "determination": fixture["determination"],
        "stated_deadline": fixture["stated_deadline"],
        "deficiencies": [
            {
                "kind": item["kind"],
                "plain_language": "Plain explanation.",
                "quoted_text": item["quote"],
            }
            for item in fixture["deficiencies"]
        ],
    }
    result = LetterReader(LetterReplayClient({"default": raw})).parse(
        "ownership", image=b"jpeg"
    )
    scored = grade("ownership", result, fixture)
    assert scored["correct"] == scored["total"] == 5
    assert all(scored["fields"].values())


def test_fixture_dictionary_is_json_serializable():
    json.dumps(LETTERS)
