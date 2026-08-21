"""One real Gemini call a judge can trigger, graded against truth on the spot.

Everything else the public console does replays a committed recording. That is the right default:
it makes judging repeatable, it costs nothing, and the recordings are graded against adjacent truth
so the accuracy claim is auditable rather than asserted.

It also, fairly, invites the question this module exists to answer: *is the model actually there?*
A recording cannot prove a live integration, and "trust the fixtures" is exactly the kind of
unfalsifiable claim this project refuses to make elsewhere.

So this route sends the same synthetic letter image to Gemini 3.5 Flash on Vertex AI, right now,
with no credential in front of it, and grades the response against the committed truth file using
the identical fields the recorded run was scored on. The score can therefore be compared directly
with the published 20/20, and a bad live result is reported as a bad live result rather than
hidden.

The cost of an open route that spends money is bounded elsewhere, by a durable per-visitor and
global daily cap. This module does the work; it does not decide whether it is allowed to run.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sixty_days.reader import LetterExtractionError, LetterReader


@dataclass(frozen=True)
class LiveCheckResult:
    fixture: str
    model: str
    correct: int
    total: int
    fields: dict[str, bool]
    elapsed_ms: int
    redacted_identifiers: int
    dropped_by_guard: int
    expected_kinds: list[str]
    extracted_kinds: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "fixture": self.fixture,
            "model": self.model,
            "correct": self.correct,
            "total": self.total,
            "fields": self.fields,
            "elapsed_ms": self.elapsed_ms,
            "redacted_identifiers": self.redacted_identifiers,
            "dropped_by_guard": self.dropped_by_guard,
            "expected_kinds": self.expected_kinds,
            "extracted_kinds": self.extracted_kinds,
            "replayed": False,
            "note": (
                "A live Vertex AI call on a synthetic letter, graded against the committed truth "
                "file by the same fields as the recorded run. No case is created and nothing is "
                "stored."
            ),
        }


def grade_against_truth(result: Any, truth: dict[str, Any]) -> dict[str, bool]:
    """The scoring used by scripts/record_letters.py, so live and recorded runs are comparable.

    Scoring a live call more leniently than the published run would make the published number
    meaningless, so the field set here is deliberately identical.
    """
    letter = result.letter
    got_kinds = [item.kind.value for item in letter.deficiencies]
    truth_kinds = [item["kind"] for item in truth["deficiencies"]]
    return {
        "letter_date": letter.letter_date.isoformat() == truth["letter_date"],
        "determination": letter.determination.value == truth["determination"],
        "stated_deadline": (
            letter.stated_deadline.isoformat() if letter.stated_deadline else None
        )
        == truth["stated_deadline"],
        "deficiency_kinds": got_kinds == truth_kinds,
        "all_quotes_grounded": all(
            item.quote.appears_in(result.source_text) for item in letter.deficiencies
        ),
    }


def run_live_check(
    client: Any,
    scans_dir: Path,
    fixture: str = "damage_and_insurance",
    model: str = "gemini-3.5-flash",
) -> LiveCheckResult:
    """Read one synthetic letter image with a live model call and score the answer.

    The image is passed as bytes with no accompanying transcript on purpose. Handing the model the
    text alongside the picture would let a correct answer come from copying rather than reading,
    which would make the score meaningless as evidence.
    """
    image_path = scans_dir / f"{fixture}.jpg"
    truth_path = scans_dir / f"{fixture}.truth.json"
    if not image_path.exists() or not truth_path.exists():
        raise LetterExtractionError(f"no synthetic fixture named {fixture!r}")

    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    reader = LetterReader(client)

    started = time.monotonic()
    result = reader.parse(f"live_{fixture}", image=image_path.read_bytes())
    elapsed_ms = int((time.monotonic() - started) * 1000)

    fields = grade_against_truth(result, truth)
    return LiveCheckResult(
        fixture=fixture,
        model=model,
        correct=sum(fields.values()),
        total=len(fields),
        fields=fields,
        elapsed_ms=elapsed_ms,
        redacted_identifiers=result.redacted_count,
        dropped_by_guard=len(result.dropped),
        expected_kinds=[item["kind"] for item in truth["deficiencies"]],
        extracted_kinds=[item.kind.value for item in result.letter.deficiencies],
    )
