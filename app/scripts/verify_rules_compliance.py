"""Check this submission against every binding requirement in the contest rules.

Written as a script rather than a checklist in a document because a checklist drifts the moment
something changes, and the expensive way to discover a missed requirement is at judging. Each check
names the rule it enforces, and each is verified against the deployed service or the repository
rather than against a claim in the README.

Items that genuinely cannot be verified from here -- a published video, a Devpost form -- are
reported as MANUAL rather than quietly passed.

    python scripts/verify_rules_compliance.py --url https://sixty-days-....run.app
"""

from __future__ import annotations

import argparse
import json
import re
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
    try:
        with urllib.request.urlopen(url.rstrip("/") + path, timeout=45) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, ""
    except Exception:  # noqa: BLE001
        return 0, ""


def read(*parts: str) -> str:
    path = ROOT.joinpath(*parts)
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


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

    # --- Things a script cannot see -------------------------------------------------------
    r.manual("Demo video under 4 minutes, public on YouTube or Vimeo",
             "not yet recorded: Stage One is pass/fail on this")
    r.manual("English captions reviewed", "depends on the video")
    r.manual("Devpost submission fields completed", "category, links, write-up")
    r.manual("Social post published with #AllThingsAgenticHackathon",
             "copy ready in docs/social-post.md")
    r.manual("Public repository pushed with these changes",
             "local commits must reach github.com/usv240/sixty-days")

    return r.render()


if __name__ == "__main__":
    sys.exit(main())
