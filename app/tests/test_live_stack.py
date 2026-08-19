from pathlib import Path


WEB = Path(__file__).resolve().parents[1] / "web"


def test_live_stack_is_available_on_every_custom_public_page() -> None:
    for name in ("sixty-days.html", "developer.html", "sixty-days-judges.html"):
        html = (WEB / name).read_text(encoding="utf-8")
        assert "/static/live-stack.js" in html, name


def test_live_stack_publishes_only_verified_services() -> None:
    script = (WEB / "live-stack.js").read_text(encoding="utf-8")
    css = (WEB / "styles.css").read_text(encoding="utf-8")
    for service in ("Gemini 3.5 Flash", "Cloud Run", "Firestore", "Cloud Scheduler", "Cloud Trace", "Secret Manager", "Gemma 4", "Veo 3.1 Fast"):
        assert service in script
    for unclaimed in ("Agent Registry", "Agent Runtime", "Model Armor", "Memory Bank"):
        assert unclaimed not in script
    assert "Technology used; no endorsement implied." in script
    assert "sponsor" not in script.lower()
    assert ".live-stack:focus-within" in css

