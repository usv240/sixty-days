"""The worker path must not inherit the console's credential-free posture.

`/internal/scan-due` is the only route that advances durable state with no human in the loop.
Claiming a wake retires it, so an anonymous caller who can drive the scanner can permanently
silence a deadline safeguard. These tests pin that the route is closed in the cloud, closed
against tokens minted for other services, and open only on a developer's own machine.
"""

from __future__ import annotations

import pytest

from spine.scheduler_auth import (
    SchedulerIdentityError,
    scheduler_identity_configured,
    verify_scheduler_token,
)


AUDIENCE = "https://sixty-days-example.us-central1.run.app"
IDENTITY = "agent-wake-scheduler@agentic-fleet-2026.iam.gserviceaccount.com"


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCHEDULER_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("SCHEDULER_SERVICE_ACCOUNT", IDENTITY)


def _claims(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "email": IDENTITY,
        "email_verified": True,
        "iss": "https://accounts.google.com",
        "aud": AUDIENCE,
    }
    base.update(overrides)
    return base


def test_a_correctly_signed_scheduler_call_is_accepted(configured: None) -> None:
    seen: list[tuple[str, str]] = []

    def verifier(token: str, audience: str) -> dict[str, object]:
        seen.append((token, audience))
        return _claims()

    assert verify_scheduler_token("Bearer good-token", verifier) == {
        "mode": "google-oidc",
        "email": IDENTITY,
    }
    assert seen == [("good-token", AUDIENCE)]


def test_an_anonymous_call_is_rejected(configured: None) -> None:
    with pytest.raises(SchedulerIdentityError, match="missing scheduler bearer token"):
        verify_scheduler_token(None, lambda token, audience: _claims())


def test_a_non_bearer_header_is_rejected(configured: None) -> None:
    with pytest.raises(SchedulerIdentityError, match="missing scheduler bearer token"):
        verify_scheduler_token("Basic abc123", lambda token, audience: _claims())


def test_a_token_from_another_service_account_is_rejected(configured: None) -> None:
    def verifier(token: str, audience: str) -> dict[str, object]:
        return _claims(email="someone-else@example.iam.gserviceaccount.com")

    with pytest.raises(SchedulerIdentityError, match="identity rejected"):
        verify_scheduler_token("Bearer other-token", verifier)


def test_an_unverified_email_claim_is_rejected(configured: None) -> None:
    def verifier(token: str, audience: str) -> dict[str, object]:
        return _claims(email_verified=False)

    with pytest.raises(SchedulerIdentityError, match="not verified"):
        verify_scheduler_token("Bearer unverified", verifier)


def test_a_non_google_issuer_is_rejected(configured: None) -> None:
    def verifier(token: str, audience: str) -> dict[str, object]:
        return _claims(iss="https://evil.example.com")

    with pytest.raises(SchedulerIdentityError, match="issuer rejected"):
        verify_scheduler_token("Bearer wrong-issuer", verifier)


def test_a_verification_failure_becomes_a_rejection_not_a_crash(configured: None) -> None:
    def verifier(token: str, audience: str) -> dict[str, object]:
        raise ValueError("token has wrong audience")

    with pytest.raises(SchedulerIdentityError, match="token rejected"):
        verify_scheduler_token("Bearer wrong-audience", verifier)


def test_an_unconfigured_worker_on_cloud_run_refuses_to_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail closed. A misdeployed service must not run an unguarded worker by accident."""
    monkeypatch.delenv("SCHEDULER_AUDIENCE", raising=False)
    monkeypatch.delenv("SCHEDULER_SERVICE_ACCOUNT", raising=False)
    monkeypatch.setenv("K_SERVICE", "sixty-days")

    with pytest.raises(SchedulerIdentityError, match="not configured"):
        verify_scheduler_token("Bearer anything", lambda token, audience: _claims())


def test_local_development_runs_without_scheduler_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SCHEDULER_AUDIENCE", raising=False)
    monkeypatch.delenv("SCHEDULER_SERVICE_ACCOUNT", raising=False)
    monkeypatch.delenv("K_SERVICE", raising=False)

    assert verify_scheduler_token(None) == {"mode": "local-unauthenticated"}


def test_partial_configuration_is_treated_as_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Half a policy is not a policy. An audience without an identity must not look configured."""
    monkeypatch.setenv("SCHEDULER_AUDIENCE", AUDIENCE)
    monkeypatch.delenv("SCHEDULER_SERVICE_ACCOUNT", raising=False)
    monkeypatch.setenv("K_SERVICE", "sixty-days")

    assert scheduler_identity_configured() is False
    with pytest.raises(SchedulerIdentityError, match="not configured"):
        verify_scheduler_token("Bearer anything", lambda token, audience: _claims())
