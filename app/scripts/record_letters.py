"""Call Gemini 3.5 Flash on letter photographs, record responses, and grade every field.

    python scripts/record_letters.py
    python scripts/record_letters.py ownership
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sixty_days.reader import LetterExtractionError, LetterReader, LetterVertexClient  # noqa: E402

SCANS = Path(__file__).resolve().parent.parent / "fixtures" / "letter_scans"
RECORDINGS = Path(__file__).resolve().parent.parent / "fixtures" / "letter_recordings"
PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "agentic-fleet-2026")
LOCATION = os.environ.get("MODEL_LOCATION", "global")
MODEL = os.environ.get("LETTER_MODEL", "gemini-3.5-flash")


def grade(name: str, result, truth: dict) -> dict:
    letter = result.letter
    got_kinds = [item.kind.value for item in letter.deficiencies]
    truth_kinds = [item["kind"] for item in truth["deficiencies"]]
    quote_checks = [item.quote.appears_in(result.source_text) for item in letter.deficiencies]
    fields = {
        "letter_date": letter.letter_date.isoformat() == truth["letter_date"],
        "determination": letter.determination.value == truth["determination"],
        "stated_deadline": (
            letter.stated_deadline.isoformat() if letter.stated_deadline else None
        ) == truth["stated_deadline"],
        "deficiency_kinds": got_kinds == truth_kinds,
        "all_quotes_grounded": all(quote_checks),
    }
    return {
        "fixture": name,
        "fields": fields,
        "correct": sum(fields.values()),
        "total": len(fields),
        "expected_kinds": truth_kinds,
        "extracted_kinds": got_kinds,
        "dropped_by_guard": result.dropped,
        "redacted_identifiers": result.redacted_count,
    }


def main() -> int:
    wanted = set(sys.argv[1:])
    images = sorted(SCANS.glob("*.jpg"))
    if wanted:
        images = [path for path in images if path.stem in wanted]
    if not images:
        print("No letter fixtures found. Run scripts/make_letter_fixtures.py first.")
        return 1

    RECORDINGS.mkdir(parents=True, exist_ok=True)
    print(f"Live Gemini calls: model={MODEL} project={PROJECT} location={LOCATION}")
    print(f"{len(images)} image(s); this path incurs real model usage.\n")
    reader = LetterReader(LetterVertexClient(PROJECT, LOCATION, MODEL))
    report = []
    for image_path in images:
        print(image_path.name)
        try:
            result = reader.parse(image_path.stem, image=image_path.read_bytes())
        except LetterExtractionError as exc:
            report.append({"fixture": image_path.stem, "error": str(exc)})
            print(f"  FAILED: {exc}")
            continue
        (RECORDINGS / f"{image_path.stem}.json").write_text(
            json.dumps(result.raw, indent=2), encoding="utf-8"
        )
        truth = json.loads(
            (SCANS / f"{image_path.stem}.truth.json").read_text(encoding="utf-8")
        )
        scored = grade(image_path.stem, result, truth)
        report.append(scored)
        print(f"  correct: {scored['correct']}/{scored['total']}")
        print(f"  reasons: {scored['extracted_kinds']}")
        print(f"  redacted identifiers: {scored['redacted_identifiers']}")

    (RECORDINGS / "_accuracy_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    scored = [row for row in report if "error" not in row]
    correct = sum(row["correct"] for row in scored)
    total = sum(row["total"] for row in scored)
    failures = [row for row in scored if row["correct"] != row["total"]]
    print(f"\nMeasured field accuracy: {correct}/{total}; imperfect fixtures: {len(failures)}")
    print(f"Recordings and report written to {RECORDINGS}")
    return 0 if len(scored) == len(images) and not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
