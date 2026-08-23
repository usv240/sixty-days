"""The evidence page must be checkable, not merely readable.

It used to print a block of shell commands and ask to be believed. A judge evaluating dozens of
entries will not clone a repository to find out whether a claim is true, and the contest rules only
require a video to prove execution "via terminal logs, database updates, or UI changes" -- so the
proof belongs in the page, where it costs one click and no terminal.
"""

from __future__ import annotations

import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "web"
PAGE = (WEB / "sixty-days-judges.html").read_text(encoding="utf-8")
SCRIPT = (WEB / "judge-verify.js").read_text(encoding="utf-8")


def test_each_claim_has_a_button_that_checks_it() -> None:
    for control, panel in [
        ("run-exit-test", "exit-test-result"),
        ("run-scheduler-check", "scheduler-result"),
        ("run-conformance", "conformance-result"),
    ]:
        assert f'id="{control}"' in PAGE, f"missing control {control}"
        assert f'id="{panel}"' in PAGE, f"missing result panel {panel}"
        assert control in SCRIPT, f"{control} is not wired to anything"


def test_the_checks_call_the_deployed_service_rather_than_replaying_anything() -> None:
    for endpoint in ["/exit-test", "/sixty-days/scheduler", "/sixty-days/conformance"]:
        assert endpoint in SCRIPT, f"no live call to {endpoint}"
    assert "fetch(" in SCRIPT


def test_the_exit_test_post_carries_a_body() -> None:
    """Google's front end answers 411 to a POST with no Content-Length, and the button would die."""
    block = SCRIPT[SCRIPT.index('fetch("/exit-test"'):SCRIPT.index("const data = await response.json()")]
    assert 'body: "{}"' in block


def test_a_check_in_flight_never_shows_the_previous_answer() -> None:
    """The same bug the developer page had: a stale result reads as a broken page."""
    assert 'state: "pending"' in SCRIPT
    pending_at = SCRIPT.index('state: "pending"')
    run_at = SCRIPT.index("await run(panel")
    assert pending_at < run_at, "the panel is reset after the request, which is too late"


def test_a_failed_check_is_reported_as_failed() -> None:
    """A verification page that can only say PASS is decoration."""
    assert 'state: "fail"' in SCRIPT
    assert "could not complete" in SCRIPT
    assert "That is reported rather than hidden." in SCRIPT


def test_the_page_no_longer_asks_a_judge_to_open_a_terminal_first() -> None:
    """Local commands stay available, but folded away rather than presented as the only route."""
    assert "Verify it yourself" in PAGE
    assert "without trusting this page" in PAGE
    commands = PAGE.index("python -m pytest")
    details = PAGE.rindex("<details", 0, commands)
    assert "verify-local" in PAGE[details:commands], "the commands are not inside a disclosure"


def test_the_local_baseline_matches_the_suite_that_actually_runs() -> None:
    match = re.search(r"expected standalone baseline is <b>(\d+) tests</b>", PAGE)
    assert match, "the page no longer states a test baseline"
    stated = int(match.group(1))
    actual = len(list((Path(__file__).resolve().parent).glob("test_*.py")))
    assert actual > 0
    assert stated >= 300, f"baseline {stated} looks stale"
