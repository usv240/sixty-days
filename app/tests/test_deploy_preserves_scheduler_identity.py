"""A redeploy must never disarm the worker.

`verify_scheduler_token` is fail-closed on Cloud Run: with `SCHEDULER_AUDIENCE` unset *or empty*,
every call to `/internal/scan-due` is rejected. `gcloud run deploy --update-env-vars` is additive,
so an omitted variable keeps its deployed value -- but a variable passed as an empty string is
written, and writing an empty audience is indistinguishable from never having configured one.

The symptom is the worst kind: nothing fails at deploy time, the service returns 200 on every
public route, and the only evidence is a scheduler badge that goes stale several minutes later.
"""

import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
DEPLOY = (APP / "deploy.sh").read_text(encoding="utf-8")


def test_the_audience_is_never_passed_as_a_possibly_empty_value() -> None:
    assert "SCHEDULER_AUDIENCE=${SCHEDULER_AUDIENCE:-}" not in DEPLOY, (
        "this writes an empty audience whenever the caller has not exported one, "
        "which fails every scan closed"
    )


def test_the_audience_is_only_named_when_it_has_a_value() -> None:
    guarded = re.search(
        r'if \[\[ -n "\$\{SCHEDULER_AUDIENCE:-\}" \]\]; then\s*\n'
        r'\s*ENV_VARS="\$\{ENV_VARS\},SCHEDULER_AUDIENCE=\$\{SCHEDULER_AUDIENCE\}"',
        DEPLOY,
    )
    assert guarded, "the audience must be appended to the env list only inside a non-empty guard"


def test_the_audience_is_not_guessed_from_the_service_url() -> None:
    # Cloud Run answers on two hostnames. The OIDC audience must be the exact one the scheduler job
    # was provisioned against, so deriving it from a lookup fails the same silent way as clearing it.
    assert "SCHEDULER_AUDIENCE=${URL}" not in DEPLOY.split("Finish wiring")[0].replace(
        'SCHEDULER_AUDIENCE=${URL} bash deploy.sh', ""
    )


def test_the_service_still_fails_closed_when_it_is_unconfigured() -> None:
    # The deploy fix is a belt; this is the braces. If the audience is ever empty on Cloud Run the
    # scanner must refuse rather than run an unauthenticated worker against durable state.
    auth = (APP / "spine" / "scheduler_auth.py").read_text(encoding="utf-8")
    assert 'if not audience or not expected_email:' in auth
    assert 'raise SchedulerIdentityError("scheduler identity is not configured")' in auth
