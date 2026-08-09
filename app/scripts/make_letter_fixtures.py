"""Generate synthetic, degraded determination-letter photographs with machine-readable truth.

No agency seal, logo, form number, or real applicant data appears in these fixtures. They imitate
the document class needed to test multimodal reading without implying agency endorsement.

    python scripts/make_letter_fixtures.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parent.parent / "fixtures" / "letter_scans"

LETTERS = {
    "ownership": {
        "text": """DISASTER ASSISTANCE DETERMINATION — SYNTHETIC DEMONSTRATION
Not an agency document. No government endorsement.

Applicant: MARA RIVERA
Damaged dwelling: 1847 RIVER BEND ROAD, EXAMPLE PARISH
Registration: DEMO-4821
Date: August 1, 2026

Decision: Assistance is not approved at this time.

We are unable to verify ownership of the damaged dwelling.
You may ask us to review this decision. Your appeal must be received by September 30, 2026.
Include documents that support the specific issue described above.

This synthetic page was created solely for software testing.
""",
        "letter_date": "2026-08-01",
        "determination": "denied",
        "stated_deadline": "2026-09-30",
        "deficiencies": [{"kind": "ownership", "quote": "unable to verify ownership of the damaged dwelling"}],
    },
    "occupancy": {
        "text": """DISASTER ASSISTANCE DETERMINATION — SYNTHETIC DEMONSTRATION
Not an agency document. No government endorsement.

Applicant: DEVON CARTER
Damaged dwelling: 72 PINE LANDING, SAMPLE COUNTY
Registration: DEMO-7319
Date: August 3, 2026

Decision: Assistance is not approved at this time.

The information provided did not establish that the damaged home was your primary residence.
An appeal must be received no later than October 2, 2026.
Send only material that addresses the reason printed in this letter.

This synthetic page was created solely for software testing.
""",
        "letter_date": "2026-08-03",
        "determination": "denied",
        "stated_deadline": "2026-10-02",
        "deficiencies": [{"kind": "occupancy", "quote": "did not establish that the damaged home was your primary residence"}],
    },
    "damage_and_insurance": {
        "text": """DISASTER ASSISTANCE DETERMINATION — SYNTHETIC DEMONSTRATION
Not an agency document. No government endorsement.

Applicant: ELISE NGUYEN
Damaged dwelling: 905 MOCKINGBIRD LANE, TEST COUNTY
Registration: DEMO-1158
Date: August 5, 2026

Decision: Some requested assistance is not approved.

The inspection did not show disaster-caused damage that made the home unsafe to occupy.
We also need the insurance settlement or denial before we can consider uninsured losses.
Your appeal must be received by October 4, 2026.

This synthetic page was created solely for software testing.
""",
        "letter_date": "2026-08-05",
        "determination": "partial",
        "stated_deadline": "2026-10-04",
        "deficiencies": [
            {"kind": "damage_evidence", "quote": "inspection did not show disaster-caused damage"},
            {"kind": "insurance", "quote": "need the insurance settlement or denial"},
        ],
    },
    "short_window": {
        "text": """DISASTER ASSISTANCE DETERMINATION — SYNTHETIC DEMONSTRATION
Not an agency document. No government endorsement.

Applicant: JORDAN PATEL
Damaged dwelling: 44 EXAMPLE AVENUE, PRACTICE COUNTY
Registration: DEMO-9044
Date: August 8, 2026

Decision: Assistance is not approved at this time.

We could not confirm the identity associated with this application.
The date printed for receipt of an appeal is September 22, 2026.

This synthetic page was created solely for software testing.
""",
        "letter_date": "2026-08-08",
        "determination": "denied",
        "stated_deadline": "2026-09-22",
        "deficiencies": [{"kind": "identity", "quote": "could not confirm the identity associated with this application"}],
    },
}


def find_font(size: int) -> ImageFont.FreeTypeFont:
    for candidate in (
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def render(text: str, seed: int) -> Image.Image:
    random.seed(seed)
    width, height = 1240, 1600
    page = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(page)
    font = find_font(24)
    y = 90
    for line in text.splitlines():
        draw.text((90, y), line, fill=random.randint(12, 42), font=font)
        y += 39

    gradient = Image.new("L", (width, height))
    gdraw = ImageDraw.Draw(gradient)
    for x in range(0, width, 4):
        gdraw.rectangle([x, 0, x + 4, height], fill=int(255 - 28 * (x / width)))
    page = ImageChops.multiply(page, gradient)
    speckle = Image.effect_noise((width, height), 20).point(lambda p: 255 if p > 239 else 0)
    page = ImageChops.subtract(page, speckle.point(lambda p: 75 if p else 0))
    page = page.rotate(random.uniform(-1.0, 1.0), resample=Image.BICUBIC, fillcolor=243)
    page = page.filter(ImageFilter.GaussianBlur(0.35))
    page = ImageEnhance.Contrast(page).enhance(1.1)
    return page.convert("RGB")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for index, (name, fixture) in enumerate(LETTERS.items()):
        image_path = OUT / f"{name}.jpg"
        render(fixture["text"], seed=41 + index).save(image_path, "JPEG", quality=64)
        (OUT / f"{name}.txt").write_text(fixture["text"], encoding="utf-8")
        truth = {key: value for key, value in fixture.items() if key != "text"}
        (OUT / f"{name}.truth.json").write_text(
            json.dumps(truth, indent=2), encoding="utf-8"
        )
        print(f"{image_path.name:28s} {image_path.stat().st_size // 1024:4d} KB")
    print(f"{len(LETTERS)} synthetic, unbranded letter fixtures written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
