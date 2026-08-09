import hashlib
import json
from pathlib import Path


APP = Path(__file__).resolve().parents[1]
WEB = APP / "web"
MEDIA = WEB / "media"


def _manifest() -> dict:
    return json.loads((MEDIA / "bonus-media-provenance.json").read_text(encoding="utf-8"))


def test_bonus_media_is_real_recorded_google_output_with_integrity_hashes():
    manifest = _manifest()
    assert manifest["provider"] == "Google Vertex AI"
    assert manifest["project"] == "Sixty Days"
    assert manifest["image"]["model"] == "gemini-3.1-flash-image"
    assert manifest["video"]["model"] == "veo-3.1-fast-generate-001"
    for kind, magic in (("image", b"\x89PNG"), ("video", None)):
        record = manifest[kind]
        asset = MEDIA / record["asset"]
        payload = asset.read_bytes()
        assert len(payload) == record["bytes"] > 100_000
        assert hashlib.sha256(payload).hexdigest() == record["sha256"]
        if magic:
            assert payload.startswith(magic)
        else:
            assert b"ftyp" in payload[:64]


def test_bonus_media_is_optional_labelled_and_never_enters_a_case():
    html = (WEB / "sixty-days.html").read_text(encoding="utf-8")
    assert "Gemini 3.1 Flash Image" in html
    assert "Veo 3.1 Fast" in html
    assert "Onboarding only; never case evidence" in html
    assert "/static/media/bonus-media-provenance.json" in html
    assert "controls muted playsinline" in html
    assert "autoplay" not in html
    assert "never treated as" in html
    assert "never becomes case evidence" in (
        WEB / "sixty-days-judges.html"
    ).read_text(encoding="utf-8")


def test_bonus_media_recording_is_reproducible_and_contains_no_case_identifiers():
    script = (APP / "scripts" / "record_bonus_media.py").read_text(encoding="utf-8")
    assert 'IMAGE_MODEL", "gemini-3.1-flash-image"' in script
    assert 'VIDEO_MODEL", "veo-3.1-fast-generate-001"' in script
    for forbidden in ("demo-7319", "devon carter", "appeal approved", "fema will accept"):
        assert forbidden not in script.casefold()
    assert "sha256" in script
    demo = (APP / "scripts" / "sixty_days_demo_flow.py").read_text(encoding="utf-8")
    assert "/static/media/bonus-media-provenance.json" in demo
    assert "hashlib.sha256" in demo
    assert 'person_generation="dont_allow"' in script