from pathlib import Path


WEB = Path(__file__).resolve().parent.parent / "web"


def test_console_has_keyboard_reachable_controls_and_live_status():
    html = (WEB / "sixty-days.html").read_text(encoding="utf-8")
    for element_id in (
        "fixture", "btn-open", "evidence-fixture", "btn-screen",
        "request-requirement", "btn-prepare", "applicant-statement",
        "btn-packet", "btn-pdf", "btn-day3", "btn-day52", "btn-day58",
    ):
        assert f'id="{element_id}"' in html
    assert 'aria-live="polite"' in html
    assert 'href="#main"' in html
    for section_id in ("problem", "workflow", "console", "limits", "architecture", "faq"):
        assert f'id="{section_id}"' in html
    assert 'class="workflow-progress"' in html
    assert "Guided preset:" in html
    assert "without deleting stored audit records" in html
    assert "github.com/usv240/sixty-days" in html


def test_console_states_the_safety_boundary_plainly():
    html = (WEB / "sixty-days.html").read_text(encoding="utf-8")
    normalized = " ".join(html.split())
    assert "not legal advice" in normalized
    assert "no submission endpoint" in normalized
    assert "Synthetic" in html
    assert "No government agency endorses" in html
    assert "application and disaster numbers on every" in normalized
    assert "verifying-home-ownership-or-occupancy" in html
    assert "fema_insurance_qrg_20241010.pdf" in html


def test_console_script_does_not_call_a_destructive_case_reset():
    script = (WEB / "sixty-days.js").read_text(encoding="utf-8")
    assert "/sixty-days/reset" not in script
    assert "/sixty-days/demo/anchor" in script
    assert "damage_close_bad" in script
    assert "damage_wide_good" in script
    assert "No stored case or audit record is deleted." in script
    assert "innerHTML" not in script
    assert "/send" not in script
    assert "/submit" not in script


def test_console_uses_the_measured_catalogue_not_a_hard_coded_score():
    script = (WEB / "sixty-days.js").read_text(encoding="utf-8")
    assert "data.measured.correct" in script
    assert "data.measured.total" in script
    assert "/sixty-days/evidence/fixtures" in script


def test_console_has_no_mojibake_and_distinguishes_review_from_acceptance():
    html = (WEB / "sixty-days.html").read_text(encoding="utf-8")
    script = (WEB / "sixty-days.js").read_text(encoding="utf-8")
    judges = (WEB / "sixty-days-judges.html").read_text(encoding="utf-8")
    for evidence in (
        "Evaluation map",
        "Mandatory technology",
        "Deployment proof",
        "Findings and learnings",
        "Deliberate non-capabilities",
        "338 tests",
        "sixty-days-109051079423.us-central1.run.app",
        "github.com/usv240/sixty-days",
        "Research-to-design trace",
        "unsupported signed statement",
        "every page footer",
        "parallel rehearsal exposed a shared simulation clock",
        "If you have sixty seconds",
        "Gemini 3.1 Flash Image",
        "Veo 3.1 Fast",
    ):
        assert evidence in judges
    assert "Service:</b> <code>spine</code>" not in judges
    assert "demo-prefixed packet references" in html
    assert "Ã¢" not in html + script
    assert "ready for applicant review" in html
    assert 'never “FEMA will accept this.”' in html


def test_the_wordmark_returns_home_from_every_page():
    """The first thing anyone tries when lost, and it worked on only one of the three pages."""
    for name in ["sixty-days.html", "sixty-days-judges.html", "developer.html"]:
        html = (WEB / name).read_text(encoding="utf-8")
        assert '<a class="brand" href="/"' in html, f"{name}: the wordmark is not a link home"
        assert 'aria-label="Sixty Days home"' in html, f"{name}: the link has no accessible name"
