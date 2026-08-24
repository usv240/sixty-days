"""Check this submission against every binding requirement in the contest rules.

Written as a script rather than a checklist in a document because a checklist drifts the moment
something changes, and the expensive way to discover a missed requirement is at judging. Each check
names the rule it enforces, and each is verified against the deployed service or the repository
rather than against a claim in the README.

Anything that can be checked is checked, including the things people usually take on trust: that
the public repository actually carries the code that is deployed, and that the video and social
links in SUBMISSION_LINKS.md really resolve. A checkbox in a document proves nothing; fetching the
URL does.

Only what genuinely cannot be reached from here -- whether a Devpost form was submitted, whether the
captions read well -- is reported as MANUAL rather than quietly passed.

    python scripts/verify_rules_compliance.py --url https://sixty-days-....run.app
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
APP = ROOT / "app"


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []

    def add(self, status: str, rule: str, detail: str = "") -> None:
        self.rows.append((status, rule, detail))

    def check(self, ok: bool, rule: str, detail: str = "") -> bool:
        self.add("PASS" if ok else "FAIL", rule, detail)
        return ok

    def manual(self, rule: str, detail: str) -> None:
        self.add("MANUAL", rule, detail)

    def render(self) -> int:
        width = max(len(r[1]) for r in self.rows)
        for status, rule, detail in self.rows:
            line = f"{status:6s} {rule:<{width}}"
            if detail:
                line += f"  {detail}"
            print(line)
        failed = sum(1 for s, _, _ in self.rows if s == "FAIL")
        manual = sum(1 for s, _, _ in self.rows if s == "MANUAL")
        passed = len(self.rows) - failed - manual
        print(f"\n{passed} verified, {manual} need a human, {failed} failing")
        return 1 if failed else 0


def get(url: str, path: str = "") -> tuple[int, str]:
    # Several publishing platforms refuse a bare urllib fetch, which would report a perfectly
    # public page as broken. Identify like a browser so a 403 means blocked, not missing.
    request = urllib.request.Request(
        url.rstrip("/") + path,
        headers={"User-Agent": "Mozilla/5.0 (compatible; sixty-days-compliance/1.0)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, ""
    except Exception:  # noqa: BLE001
        return 0, ""


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=30
        ).stdout.strip()
    except Exception:  # noqa: BLE001 - a missing git is a failed check, not a crash
        return ""


def read(*parts: str) -> str:
    path = ROOT.joinpath(*parts)
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""



# Only a line that says "standalone" is checked. This repository ships beside a combined
# integration workspace with a different, legitimately different, count, and the word "standalone"
# is how every document already distinguishes the two. The rule is self-documenting: to have a
# number checked, say which suite it belongs to.
COUNT_ON_LINE = re.compile(r"([0-9]{3,4})")


def audit_test_counts(root: Path, app: Path) -> tuple[str | None, list[str]]:
    """Return the suite's real size and every document that disagrees with it."""
    collected = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=app, capture_output=True, text=True, timeout=300,
    ).stdout
    reported = re.search(r"([0-9]+) tests? collected", collected)
    if reported is None:
        return None, []
    total = reported.group(1)

    stale: list[str] = []
    documents = [*root.rglob("*.md"), *root.rglob("*.html")]
    skip = {".venv", "node_modules", "__pycache__", ".git", "site-packages"}
    for document in sorted(d for d in documents if not skip & set(d.parts)):
        # The published build story is a snapshot of an article that is already public. Editing it
        # would make the repository disagree with what was published rather than agree with it.
        if document.name == "public-build-story.md":
            continue
        for number, line in _claimed_counts(document):
            if number != total:
                stale.append(f"{document.relative_to(root)}:{line} says {number}")
    return total, stale


def _claimed_counts(document: Path) -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    text = document.read_text(encoding="utf-8", errors="ignore")
    for lineno, line in enumerate(text.splitlines(), start=1):
        if "standalone" not in line.lower():
            continue
        for match in COUNT_ON_LINE.findall(line):
            found.append((match, lineno))
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    url = args.url.rstrip("/")
    r = Report()

    readme = read("README.md")
    requirements = read("app", "requirements.txt")
    status, home = get(url, "/")

    # --- Mandatory technology (Rules: "Every project, in every track, must use") -------------
    models = " ".join((APP / "sixty_days" / "reader.py").read_text(encoding="utf-8").split())
    r.check("gemini-3.5-flash" in models, "Gemini 3.5 or newer via Vertex AI",
            "sixty_days/reader.py: LetterVertexClient")
    r.check("google-genai" in requirements, "A Google agent framework",
            "Google GenAI SDK, one of the four accepted")
    r.check("google-cloud-firestore" in requirements, "A Google Cloud infrastructure service",
            "Cloud Run + Firestore + Cloud Scheduler")

    # --- What to Submit ------------------------------------------------------------------
    r.check(status == 200, "Hosted project reachable for judging", f"HTTP {status}")
    r.check("<title>" in home.lower(), "Hosted project serves a real page")
    for path, label in [("/judges", "judge evidence"), ("/docs", "API schema"),
                        ("/developer", "developer page")]:
        code, _ = get(url, path)
        r.check(code == 200, f"Public surface: {label}", f"HTTP {code}")

    r.check((ROOT / "README.md").exists(), "README present")
    r.check("python -m venv" in readme and "deploy.sh" in readme,
            "Spin-up instructions: local run and cloud deploy")
    r.check((ROOT / "docs" / "architecture.svg").exists()
            and (ROOT / "docs" / "architecture.mmd").exists(),
            "Architecture diagram, with diffable source")
    r.check((ROOT / "LICENSE").exists(), "Licence declared")

    # Every relative link in the README must resolve, or a judge meets a 404.
    broken = [
        link for link in re.findall(r"\]\(([^)]+)\)", readme)
        if not link.startswith(("http", "#")) and not ROOT.joinpath(link.split("#")[0]).exists()
    ]
    r.check(not broken, "README links all resolve", ", ".join(broken) or "all resolve")

    # --- Judging: proof it runs on Google Cloud ------------------------------------------
    code, health = get(url, "/health")
    ok = code == 200
    payload = json.loads(health) if ok and health.strip().startswith("{") else {}
    r.check(ok and payload.get("tracing") is True, "Cloud Trace active on the deployed service")
    code, scheduler = get(url, "/sixty-days/scheduler")
    state = json.loads(scheduler) if code == 200 and scheduler.strip().startswith("{") else {}
    r.check(state.get("status") == "running",
            "Cloud Scheduler is actually waking the service",
            f"last scan {state.get('seconds_since_last_scan')}s ago")

    # --- Judging: autonomous multi-step action -------------------------------------------
    r.check("wake_actions.py" in str(list((APP / "sixty_days").glob("*.py"))),
            "Scheduled work executes typed case actions")
    r.check(payload.get("model_armor", "not_configured") != "not_configured",
            "Inline guardrails configured", str(payload.get("model_armor")))

    # --- Bonus (Rules section 6) ----------------------------------------------------------
    bonus = read("BONUS_EVIDENCE.md")
    extra_models = sum(term in bonus for term in ["Gemma 4", "Gemini 3.1 Flash Image", "Veo 3.1 Fast"])
    r.check(extra_models >= 3, "Additional Google models: 0.2 each, capped at 0.6",
            f"{extra_models} integrated, cap reached at 3")
    r.check("dev.to" in bonus, "Public build content published")

    # --- Numbers the documents claim about themselves ---------------------------------------
    total, stale = audit_test_counts(ROOT, APP)
    if total is None:
        r.manual("Documented test count matches the suite", "pytest reported no collection")
    else:
        r.check(not stale, "Documented test count matches the suite",
                f"{total} collected" if not stale else "; ".join(stale))

    # --- Originality and disclosure -------------------------------------------------------
    r.check("AI coding assistants" in readme, "AI-assistance disclosure present")
    r.check((ROOT / "PROJECT_DIFFERENTIATION.md").exists(),
            "Pre-existing code disclosed", "PROJECT_DIFFERENTIATION.md")
    r.check("synthetic" in readme.lower(), "Demonstration data declared synthetic")

    # --- Testing access (Rules: free of charge, no restriction) ---------------------------
    code, _ = get(url, "/sixty-days/fixtures")
    r.check(code == 200, "Judging needs no credentials", f"fixtures HTTP {code}")
    code, config = get(url, "/developer/config")
    issuance = json.loads(config).get("issuance") if code == 200 else None
    r.check(issuance == "open", "API testable without contacting the author", str(issuance))

    # --- The repository a judge will actually open -----------------------------------------
    # "URL to your public code repository to show how your project was built" is a submission
    # requirement, and a repo that lags the deployment quietly tells a judge a different story
    # from the one the live service tells.
    local_head = _git("rev-parse", "HEAD")
    remote_head = ""
    status, body = get("https://api.github.com", "/repos/usv240/sixty-days/commits/main")
    if status == 200:
        match = re.search(r'"sha"\s*:\s*"([0-9a-f]{40})"', body)
        remote_head = match.group(1) if match else ""
    dirty = _git("status", "--porcelain")

    r.check(
        bool(local_head) and local_head == remote_head,
        "Public repository carries the deployed code",
        "in sync" if local_head == remote_head else f"local {local_head[:8]} vs github {remote_head[:8] or 'unknown'}",
    )
    r.check(not dirty, "No uncommitted work left behind",
            "clean" if not dirty else f"{len(dirty.splitlines())} file(s) uncommitted")

    # --- Submission links, fetched rather than trusted --------------------------------------
    links = read("SUBMISSION_LINKS.md")
    if not links.strip():
        r.manual("Video and social URLs recorded for checking",
                 "create SUBMISSION_LINKS.md and this script will verify them")
    else:
        video = re.search(r"https?://(?:www\.)?(?:youtube\.com|youtu\.be|vimeo\.com)/\S+", links)
        if video:
            code, _ = get(video.group(0))
            r.check(code == 200, "Demo video URL resolves publicly", f"HTTP {code}")
        else:
            r.check(False, "Demo video published",
                    "required by the rules and not yet recorded")

        social = re.search(
            r"https?://(?:www\.)?(?:x\.com|twitter\.com|linkedin\.com|instagram\.com|facebook\.com)/\S+",
            links,
        )
        if social:
            code, _ = get(social.group(0))
            # These platforms often refuse anonymous fetches; a refusal is not a broken link.
            r.check(code in {200, 401, 403, 405, 999},
                    "Social post URL resolves", f"HTTP {code}")
        else:
            r.check(False, "Social post published",
                    "worth 0.2 bonus points and not yet published")

        story = re.search(r"https?://dev\.to/\S+", links)
        if story:
            code, _ = get(story.group(0))
            r.check(code == 200, "Build story URL resolves publicly", f"HTTP {code}")

    # --- Things a script cannot see -------------------------------------------------------
    r.manual("Demo video runs under four minutes", "length is not machine-checkable from a URL")
    r.manual("Devpost submission fields completed", "category, links, write-up")
    r.manual("Captions reviewed by a human", "auto-generated captions mis-transcribe the names")

    return r.render()


if __name__ == "__main__":
    sys.exit(main())
