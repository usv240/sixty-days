"""Render the reviewable synthetic packet used for PDF visual QA."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sixty_days.evidence import EvidenceChecker  # noqa: E402
from sixty_days.letters import plan_requirements  # noqa: E402
from sixty_days.packet import PacketBuilder, PacketRenderer  # noqa: E402
from sixty_days.reader import LetterReader, LetterReplayClient  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    name = "damage_and_insurance"
    extraction = json.loads(
        (ROOT / "fixtures" / "letter_recordings" / f"{name}.json").read_text(encoding="utf-8")
    )
    result = LetterReader(LetterReplayClient({"default": extraction})).parse(
        f"letter_{name}",
        document=(ROOT / "fixtures" / "letter_scans" / f"{name}.txt").read_text(
            encoding="utf-8"
        ),
    )
    requirements = plan_requirements(result.letter.deficiencies)
    fixture = "damage_wide_good"
    evidence_response = json.loads(
        (ROOT / "fixtures" / "evidence_recordings" / f"{fixture}.json").read_text(
            encoding="utf-8"
        )
    )
    evidence = EvidenceChecker().check("photo_wide", f"evidence_{fixture}", evidence_response)
    case = {
        "case_id": "case_synthetic_pdf_qa",
        "applicant_ref": "DEMO-APPLICANT",
        "deadline": result.letter.deadline.isoformat(),
        "deficiencies": [
            {
                "kind": item.kind.value,
                "plain_language": item.plain_language,
                "quoted_text": item.quote.text,
            }
            for item in result.letter.deficiencies
        ],
        "requirements": [
            {"key": item.key, "title": item.title, "source": item.source.value}
            for item in requirements
        ],
        "evidence": [{**evidence.as_dict(), "fixture": fixture}],
    }
    packet = PacketBuilder().build(
        case,
        "The applicant will add their own explanation and review every attachment before sending.",
    )
    output = ROOT / "output" / "pdf" / "sixty-days-draft-sample.pdf"
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = PacketRenderer().render(
        packet,
        {evidence.artifact_id: ROOT / "fixtures" / "evidence_scans" / f"{fixture}.png"},
    )
    output.write_bytes(raw)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
