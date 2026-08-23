"""Accessibility checks that can be asserted rather than eyeballed.

Two things this proves, in both themes, from the actual token values in styles.css:

1. **Contrast.** WCAG 2.2 AA: 4.5:1 for body text, 3:1 for large text and UI boundaries.
2. **Glossary coverage.** Every info button resolves to a definition, and every definition is
   actually surfaced somewhere. An unused definition means a term went unexplained on the page.

    python scripts/check_a11y.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"

# Pairs that must pass, as (foreground token, background token, minimum ratio, what it is).
REQUIRED = [
    ("--text", "--bg", 4.5, "body text on page"),
    ("--text", "--surface", 4.5, "body text on cards"),
    ("--text-muted", "--bg", 4.5, "muted text on page"),
    ("--text-muted", "--surface", 4.5, "muted text on cards"),
    ("--accent", "--bg", 4.5, "links on page"),
    ("--accent-text", "--accent", 4.5, "primary button label"),
    ("--ok", "--ok-soft", 4.5, "susceptible cell"),
    ("--warn", "--warn-soft", 4.5, "intermediate cell"),
    ("--danger", "--danger-soft", 4.5, "resistant cell"),
    # WCAG 1.4.11 covers boundaries you need in order to understand the content. The grid rules
    # qualify: they are how you tell which drug a number belongs to. Purely decorative section
    # dividers (--border) are exempt and stay deliberately subtle.
    ("--border-strong", "--bg", 3.0, "grid and table rules"),
    ("--border-strong", "--surface", 3.0, "grid rules on cards"),
    ("--focus", "--bg", 3.0, "focus ring"),
    ("--code-text", "--code-bg", 4.5, "developer request code"),
]


def parse_blocks(css: str) -> dict[str, dict[str, str]]:
    """Return {theme: {token: hex}} for the light default and the explicit dark block."""
    themes: dict[str, dict[str, str]] = {}

    def tokens(block: str) -> dict[str, str]:
        return dict(re.findall(r"(--[a-z0-9-]+):\s*(#[0-9a-fA-F]{3,8})", block))

    root = re.search(r":root\s*\{(.*?)\}", css, re.S)
    if root:
        themes["light"] = tokens(root.group(1))

    dark = re.search(r':root\[data-theme="dark"\]\s*\{(.*?)\}', css, re.S)
    if dark:
        merged = dict(themes.get("light", {}))
        merged.update(tokens(dark.group(1)))
        themes["dark"] = merged

    return themes


def luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    channels = []
    for i in (0, 2, 4):
        c = int(h[i : i + 2], 16) / 255
        channels.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def main() -> int:
    css = (WEB / "styles.css").read_text(encoding="utf-8")
    themes = parse_blocks(css)
    failures: list[str] = []

    print("Contrast, WCAG 2.2 AA\n")
    for theme, tokens in themes.items():
        print(f"  {theme}")
        for fg, bg, minimum, label in REQUIRED:
            if fg not in tokens or bg not in tokens:
                failures.append(f"{theme}: missing token {fg} or {bg}")
                print(f"    MISSING  {fg} on {bg}")
                continue
            ratio = contrast(tokens[fg], tokens[bg])
            ok = ratio >= minimum
            if not ok:
                failures.append(f"{theme}: {label} {ratio:.2f} < {minimum}")
            print(f"    {'PASS' if ok else 'FAIL'}  {ratio:5.2f}  (min {minimum})  {label}")
        print()

    glossary_path = WEB / "glossary.json"
    print("Developer code cascade\n")
    nested_code = re.search(r"\.developer-code\s+code\s*\{(.*?)\}", css, re.S)
    nested_css = nested_code.group(1) if nested_code else ""
    cascade_ok = "background: transparent" in nested_css and "color: inherit" in nested_css
    if cascade_ok:
        print("    PASS  nested code inherits the high-contrast block foreground")
    else:
        failures.append("developer code cascade does not reset inline code styling")
        print("    FAIL  generic inline-code styling can override the request block")
    print()

    print("First-use navigation and developer journey\n")
    landing_path = next(
        (WEB / name for name in ("index.html", "sixty-days.html", "downstream.html")
         if (WEB / name).exists()),
        None,
    )
    landing = landing_path.read_text(encoding="utf-8") if landing_path else ""
    header_nav = re.search(r"<header.*?<nav[^>]*>(.*?)</nav>", landing, re.S)
    nav_links = re.findall(r"<a\s+[^>]*href=", header_nav.group(1) if header_nav else "")
    landing_ok = (
        header_nav is not None
        and len(nav_links) <= 5
        and 'href="/developer"' in header_nav.group(1)
        and 'href="/docs"' in header_nav.group(1)
        and 'href="/judges"' in header_nav.group(1)
        and 'id="api"' in landing
    )
    if landing_ok:
        print(f"    PASS  landing navigation has {len(nav_links)} focused links and an API section")
    else:
        failures.append("landing navigation is overloaded or missing a core user path")
        print("    FAIL  landing must expose demo, developer, docs, and judge paths in five links")

    developer = (WEB / "developer.html").read_text(encoding="utf-8")
    developer_js = (WEB / "developer.js").read_text(encoding="utf-8")
    required_journey = (
        'id="create-key"',
        'id="verify"',
        'id="workflow"',
        'id="active-api-key"',
        'data-copy-code=',
        'href="/docs"',
    )
    journey_ok = all(token in developer for token in required_journey)
    storage_ok = not any(
        token in developer_js for token in ("localStorage", "sessionStorage", "document.cookie")
    )
    if journey_ok and storage_ok:
        print("    PASS  create, verify, call, copy, and docs paths exist without browser credential storage")
    else:
        failures.append("developer quickstart is incomplete or stores credentials in the browser")
        print("    FAIL  developer journey or credential-storage boundary is incomplete")
    print()

    print("Compact laptop layout\n")
    compact_query = "@media (min-width: 700px) and (max-height: 900px)"
    compact_start = css.find(compact_query)
    compact_end = css.find("@media (min-width: 981px) and (max-height: 900px)", compact_start)
    compact_css = css[compact_start:compact_end] if compact_start >= 0 and compact_end > compact_start else ""
    compact_tokens = (
        "section { padding: 48px 0; }",
        ".hero { padding: 62px 0 52px; }",
        ".judge-hero { padding: 58px 0 48px; }",
        ".developer-hero { padding: 60px 0 46px; }",
        ".console-shell { padding: 14px; }",
    )
    compact_ok = all(token in compact_css for token in compact_tokens) and "display: none" not in compact_css
    if compact_ok:
        print("    PASS  short laptop viewports reduce travel without hiding content")
    else:
        failures.append("compact laptop layout is missing, incomplete, or hides content")
        print("    FAIL  short laptop viewports retain desktop spacing or hide content")
    print()
    print("Glossary coverage\n")
    if glossary_path.exists():
        glossary = json.loads(glossary_path.read_text(encoding="utf-8"))
    else:
        print("    PASS  this project does not use glossary info buttons")
        glossary = {}
    defined = {k for k in glossary if not k.startswith("_")}
    used: set[str] = set()
    for page in WEB.glob("*.html"):
        used |= set(re.findall(r'data-info="([a-z0-9-]+)"', page.read_text(encoding="utf-8")))

    for missing in sorted(used - defined):
        failures.append(f"info button with no definition: {missing}")
        print(f"    FAIL  button '{missing}' has no glossary entry")
    for unused in sorted(defined - used):
        failures.append(f"definition never surfaced: {unused}")
        print(f"    FAIL  '{unused}' defined but never shown to a user")
    if not (used - defined) and not (defined - used):
        print(f"    PASS  {len(defined)} terms, all defined and all surfaced")

    print()
    for entry in glossary.values():
        if isinstance(entry, dict):
            for field in ("title", "plain", "why", "source", "url"):
                if not entry.get(field):
                    failures.append(f"glossary entry missing {field}: {entry.get('title')}")
    if not any("glossary entry missing" in f for f in failures):
        print("    PASS  every entry has a plain definition, a why, and a source link")

    print()
    if failures:
        print(f"{len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("All accessibility checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
