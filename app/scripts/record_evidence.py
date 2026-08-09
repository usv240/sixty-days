"""Record and grade Gemini screening of clearly synthetic evidence images.

    python scripts/record_evidence.py
    python scripts/record_evidence.py damage_wide_good
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sixty_days.evidence import (  # noqa: E402
    EvidenceChecker,
    EvidenceVertexClient,
    REQUIRED_CHECKS,
)

SCANS = Path(__file__).resolve().parent.parent / "fixtures" / "evidence_scans"
RECORDINGS = Path(__file__).resolve().parent.parent / "fixtures" / "evidence_recordings"
PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "agentic-fleet-2026")
LOCATION = os.environ.get("MODEL_LOCATION", "global")
MODEL = os.environ.get("EVIDENCE_MODEL", "gemini-3.5-flash")


def grade(name: str, response: dict, truth: dict) -> dict:
    expected = truth["checks"]
    got = response.get("checks", {})
    fields = {key: got.get(key) is value for key, value in expected.items()}
    result = EvidenceChecker().check(truth["requirement_key"], name, response)
    return {
        "fixture": name,
        "fields": fields,
        "correct": sum(fields.values()),
        "total": len(fields),
        "decision": result.decision.value,
    }


def main() -> int:
    wanted = set(sys.argv[1:])
    images = sorted(SCANS.glob("*.png"))
    if wanted:
        images = [path for path in images if path.stem in wanted]
    if not images:
        print("No synthetic evidence fixtures found.")
        return 1

    RECORDINGS.mkdir(parents=True, exist_ok=True)
    client = EvidenceVertexClient(PROJECT, LOCATION, MODEL)
    report = []
    print(f"Live Gemini calls: model={MODEL} project={PROJECT} location={LOCATION}")
    for image_path in images:
        truth = json.loads(
            (SCANS / f"{image_path.stem}.truth.json").read_text(encoding="utf-8")
        )
        requested = REQUIRED_CHECKS[truth["requirement_key"]]
        try:
            response = client.inspect(image_path.read_bytes(), requested)
        except Exception as exc:
            report.append({"fixture": image_path.stem, "error": str(exc)})
            print(f"{image_path.name}: FAILED: {exc}")
            continue
        recorded = {**response, "model": MODEL, "recorded": True}
        (RECORDINGS / f"{image_path.stem}.json").write_text(
            json.dumps(recorded, indent=2), encoding="utf-8"
        )
        scored = grade(image_path.stem, recorded, truth)
        report.append(scored)
        print(
            f"{image_path.name}: {scored['correct']}/{scored['total']} "
            f"decision={scored['decision']}"
        )

    (RECORDINGS / "_accuracy_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    scored = [row for row in report if "error" not in row]
    correct = sum(row["correct"] for row in scored)
    total = sum(row["total"] for row in scored)
    failures = [row for row in scored if row["correct"] != row["total"]]
    print(f"Measured check accuracy: {correct}/{total}; imperfect fixtures: {len(failures)}")
    return 0 if len(scored) == len(images) and not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
