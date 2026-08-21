"""Verify that a wake scan really came from this service's Cloud Scheduler job.

`/internal/scan-due` is the only route that advances durable state without a human in the loop.
The public console is deliberately credential-free so a judge can use it, but that choice must not
extend to the worker path: an anonymous caller who can drive the scanner can retire wakes, and a
retired wake never fires its safeguard again.

Cloud Scheduler signs each invocation with an OIDC token minted for a named service account and
scoped to a named audience. Both are checked here, together with the issuer, so a token that is
valid for some other service cannot be replayed against this one.

Configuration is deliberately fail-closed in the cloud and permissive locally:

* With `SCHEDULER_AUDIENCE` and `SCHEDULER_SERVICE_ACCOUNT` set, every call must carry a matching
  token.
* With them unset while running on Cloud Run, the service refuses to scan at all rather than run
  an unguarded worker against shared durable state by accident.
* With them unset off Cloud Run, the local test and replay path runs unauthenticated, because a
  developer's own machine is the trust boundary there.
"""

from __future__ import annotations

import os
from typing import Any, Callable


class SchedulerIdentityError(Exception):
    """The caller did not prove it is this service's scheduler."""


_GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


def _default_verifier(token: str, audience: str) -> dict[str, Any]:
    from google.auth.transport.requests import Request
    from google.oauth2 import id_token

    return id_token.verify_oauth2_token(token, Request(), audience=audience)


def scheduler_identity_configured() -> bool:
    return bool(
        os.getenv("SCHEDULER_AUDIENCE", "").strip()
        and os.getenv("SCHEDULER_SERVICE_ACCOUNT", "").strip()
    )


def verify_scheduler_token(
    authorization: str | None,
    verifier: Callable[[str, str], dict[str, Any]] | None = None,
) -> dict[str, str]:
    """Return the accepted caller identity, or raise `SchedulerIdentityError`."""
    audience = os.getenv("SCHEDULER_AUDIENCE", "").strip()
    expected_email = os.getenv("SCHEDULER_SERVICE_ACCOUNT", "").strip()

    if not audience or not expected_email:
        if os.getenv("K_SERVICE", "").strip():
            raise SchedulerIdentityError("scheduler identity is not configured")
        return {"mode": "local-unauthenticated"}

    if not authorization or not authorization.startswith("Bearer "):
        raise SchedulerIdentityError("missing scheduler bearer token")

    verify = verifier or _default_verifier
    try:
        claims = verify(authorization[len("Bearer ") :], audience)
    except SchedulerIdentityError:
        raise
    except Exception as exc:  # noqa: BLE001 - any verification failure is a rejection
        raise SchedulerIdentityError("scheduler token rejected") from exc

    if claims.get("email") != expected_email:
        raise SchedulerIdentityError("scheduler identity rejected")
    if claims.get("email_verified") is not True:
        raise SchedulerIdentityError("scheduler identity is not verified")
    if claims.get("iss") not in _GOOGLE_ISSUERS:
        raise SchedulerIdentityError("scheduler issuer rejected")

    return {"mode": "google-oidc", "email": expected_email}
