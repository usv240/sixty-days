"""The request printed on the developer page must be the request the API accepts.

This exists because it was not. The page documented `subject_ref` and `letter_text`; the API takes
`applicant_ref` and `document`. Anyone who copied the example got a 422, which is the worst possible
first impression of an API: it says the documentation and the service were never checked against
each other.

Prose drifts from code silently. A test does not.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from service.beta_routes import OpenBetaCaseRequest

WEB = Path(__file__).resolve().parents[1] / "web"
PAGE = (WEB / "developer.html").read_text(encoding="utf-8")
SCRIPT = (WEB / "developer.js").read_text(encoding="utf-8")


def documented_body() -> dict:
    """Pull the JSON body out of the curl example exactly as a reader would copy it."""
    match = re.search(r"-d '(\{.*?\})'</code>", PAGE, re.S)
    assert match, "the workflow example no longer contains a JSON body"
    raw = match.group(1)
    # The page escapes newlines for the shell; undo that to get the JSON a shell would send.
    return json.loads(raw.replace("\\\\n", "\\n"))


def test_the_documented_request_satisfies_the_real_contract() -> None:
    """The check that would have caught the shipped 422."""
    request = OpenBetaCaseRequest(**documented_body())

    assert request.applicant_ref.startswith("SUBJECT-")
    assert request.disaster_ref.startswith("DR-")
    assert request.acknowledge_deidentified is True
    assert len(request.document) >= 40


def test_the_documented_request_uses_no_field_the_api_would_reject() -> None:
    """Unknown fields are forbidden now, so a stale example fails loudly rather than silently."""
    body = documented_body()
    assert set(body) == {"applicant_ref", "disaster_ref", "acknowledge_deidentified", "document"}


def test_a_stale_field_name_would_now_fail_this_suite() -> None:
    """Proof the test has teeth: the exact body the page used to ship is rejected."""
    with pytest.raises(ValidationError):
        OpenBetaCaseRequest(
            subject_ref="SUBJECT-101",
            disaster_ref="DR-101",
            acknowledge_deidentified=True,
            letter_text="DECISION LETTER\nDate: August 1, 2026\nDecision: Ineligible.",
        )


def test_the_runnable_body_matches_the_printed_body() -> None:
    """Run it here must send what the page printed, or the demonstration proves nothing."""
    printed = documented_body()

    assert '"applicant_ref": "SUBJECT-101"' in PAGE or "applicant_ref" in printed
    for field in printed:
        assert field in SCRIPT, f"the runner does not send {field}"
    assert "/v1/cases" in SCRIPT
    assert printed["applicant_ref"] in SCRIPT
    assert printed["disaster_ref"] in SCRIPT


def test_the_key_is_masked_on_screen_but_copied_in_full() -> None:
    """The page tells people to keep the key out of screenshots, so it must not print one."""
    assert "maskKey" in SCRIPT
    assert "realRequest(target)" in SCRIPT, "copy must hand over the runnable request"
    assert 'replaceAll("YOUR_API_KEY", maskKey(apiKey))' in SCRIPT


def test_every_failure_a_judge_can_hit_is_explained_in_words() -> None:
    """A raw status code is not an explanation, and these are the ones they will actually meet."""
    for status in ["401", "429", "422", "503"]:
        assert status in SCRIPT, f"no explanation branch for HTTP {status}"
    assert "No API key is loaded" in SCRIPT
    assert "never reached the service" in SCRIPT


def test_the_page_still_refuses_to_claim_anything_was_sent() -> None:
    assert "Nothing was sent to anyone" in SCRIPT


def test_the_panel_clears_the_moment_a_run_starts() -> None:
    """The reported bug: a stale error stayed on screen for the whole nine-second call.

    Pressing Run with no key showed "No API key is loaded". Loading a key and pressing Run again
    left that message sitting there while the request was genuinely in flight, so the page looked
    broken at exactly the moment it was working.
    """
    assert "pending: true" in SCRIPT
    assert "waiting for the service" in SCRIPT
    # The pending state must be written before the fetch, not after it resolves.
    pending_at = SCRIPT.index("pending: true")
    fetch_at = SCRIPT.index("await fetch(request.path")
    assert pending_at < fetch_at, "the panel is cleared after the request, which is too late"


def test_the_response_is_summarised_before_the_raw_json() -> None:
    """A judge should not have to parse JSON in their head to see what the agent did."""
    assert "renderSummary" in SCRIPT
    assert "Reminders set by the agent" in SCRIPT
    assert "Reasons quoted from the letter" in SCRIPT
    assert "Show the raw JSON response" in SCRIPT, "the original must stay one click away"


def test_the_summary_reports_the_safety_facts_not_only_the_happy_ones() -> None:
    """Summarising is only honest if it surfaces the boundary as prominently as the result."""
    for fact in ["Model Armor", "quarantined", "Raw letter stored"]:
        assert fact in SCRIPT, f"the summary hides {fact}"


def test_a_stale_result_panel_is_cleared_when_the_key_changes() -> None:
    """A panel describes a request made with one key. After the key changes it answers nothing.

    Leaving "No API key is loaded" visible underneath a freshly generated key is the same confusion
    as leaving it visible during a running request, just slower to notice.
    """
    block = SCRIPT[SCRIPT.index("const setActiveKey"):SCRIPT.index("const copy =")]
    assert "#connection-response" in block
    assert "#workflow-response" in block
    assert "panel.hidden = true" in block
