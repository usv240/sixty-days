"""Model Armor may make this stricter. It must never make it more permissive.

The deterministic layer -- pattern redaction, instruction quarantine, and the Verifier -- is what
the rest of this suite pins, and it holds without a network. Model Armor is added in front of it as
a managed classifier that catches shapes a pattern set will not anticipate.

That means the failure mode to guard against is not "Model Armor missed something". It is "Model
Armor was unavailable and the code treated silence as approval". These tests exist for that.
"""

from __future__ import annotations

from spine.model_armor import ArmorVerdict, ModelArmorScreen


def sanitize_response(**states: str) -> dict:
    filters = {name: {"result": {"matchState": state}} for name, state in states.items()}
    match = "MATCH_FOUND" if "MATCH_FOUND" in states.values() else "NO_MATCH_FOUND"
    return {"sanitizationResult": {"filterMatchState": match, "filterResults": filters}}


def test_a_prompt_injection_is_blocked() -> None:
    verdict = ModelArmorScreen.interpret(
        sanitize_response(pi_and_jailbreak="MATCH_FOUND", malicious_uris="NO_MATCH_FOUND")
    )
    assert verdict.available is True
    assert verdict.blocked is True
    assert "prompt-injection" in verdict.detail


def test_ordinary_letter_text_passes() -> None:
    verdict = ModelArmorScreen.interpret(
        sanitize_response(pi_and_jailbreak="NO_MATCH_FOUND", malicious_uris="NO_MATCH_FOUND")
    )
    assert verdict.available is True
    assert verdict.blocked is False


def test_a_sensitive_data_finding_alone_does_not_reject_the_letter() -> None:
    """Identifiers are already removed deterministically; a second opinion must not veto a read."""
    verdict = ModelArmorScreen.interpret(
        sanitize_response(sdp="MATCH_FOUND", pi_and_jailbreak="NO_MATCH_FOUND")
    )
    assert verdict.blocked is False
    assert verdict.filters["sdp"] == "MATCH_FOUND"


def test_an_unconfigured_screen_is_reported_as_unavailable_not_as_a_pass() -> None:
    """The distinction that matters: 'we did not check' must never read as 'we checked, it's fine'."""
    screen = ModelArmorScreen(project_id="p", template="")
    verdict = screen.screen("anything at all")

    assert screen.enabled is False
    assert verdict.available is False
    assert verdict.blocked is False
    assert verdict.detail == "not configured"


def test_a_network_failure_is_reported_as_unavailable_not_as_a_pass() -> None:
    screen = ModelArmorScreen(
        project_id="p", location="nowhere", template="t", timeout_seconds=0.01
    )
    verdict = screen.screen("Decision: Some requested assistance is not approved.")

    assert verdict.available is False
    assert verdict.blocked is False
    assert "unavailable" in verdict.detail


def test_a_malformed_response_does_not_become_a_silent_approval() -> None:
    verdict = ModelArmorScreen.interpret({})
    assert verdict.blocked is False
    assert verdict.match_state == "UNKNOWN"


def test_the_screen_never_blocks_on_its_own_absence() -> None:
    """Unavailability hands the decision back rather than rejecting an applicant's letter."""
    for body in [{}, {"sanitizationResult": {}}, {"sanitizationResult": {"filterResults": {}}}]:
        assert ModelArmorScreen.interpret(body).blocked is False


def test_the_endpoint_is_regional_and_names_the_configured_template() -> None:
    screen = ModelArmorScreen(
        project_id="agentic-fleet-2026", location="us-central1", template="sixty-days-letter-input"
    )
    assert screen.enabled is True
    assert screen.endpoint == (
        "https://modelarmor.us-central1.rep.googleapis.com/v1/"
        "projects/agentic-fleet-2026/locations/us-central1/"
        "templates/sixty-days-letter-input:sanitizeUserPrompt"
    )


def test_the_verdict_serialises_for_the_health_surface() -> None:
    payload = ArmorVerdict(available=True, blocked=False, match_state="NO_MATCH_FOUND").as_dict()
    assert payload["available"] is True
    assert payload["blocked"] is False


def test_empty_text_is_not_sent_to_the_screen() -> None:
    screen = ModelArmorScreen(project_id="p", location="us-central1", template="t")
    verdict = screen.screen("   ")
    assert verdict.available is False
    assert verdict.detail == "nothing to screen"
