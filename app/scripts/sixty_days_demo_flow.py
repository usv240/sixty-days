"""Executable rehearsal for the Sixty Days demo against local or deployed service.

    python scripts/sixty_days_demo_flow.py --url https://SERVICE.run.app
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.error
import urllib.request


class API:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")

    def call(self, method: str, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            self.base + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(f"{method} {path}: HTTP {exc.code}: {detail}") from exc

    def call_bytes(
        self, method: str, path: str, body: dict | None = None
    ) -> tuple[bytes, dict[str, str]]:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            self.base + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read(), dict(response.headers.items())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(f"{method} {path}: HTTP {exc.code}: {detail}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    args = parser.parse_args()
    api = API(args.url)

    media = api.call("GET", "/static/media/bonus-media-provenance.json")
    for record in (media["image"], media["video"]):
        payload, _ = api.call_bytes("GET", f"/static/media/{record['asset']}")
        if len(payload) != record["bytes"] or hashlib.sha256(payload).hexdigest() != record["sha256"]:
            raise RuntimeError(f"bonus media integrity failed: {record['asset']}")
    print("PASS  recorded Google onboarding media is public and hash-matched")

    checks = []

    def check(label: str, condition: bool, detail: str = "") -> None:
        checks.append(condition)
        print(f"{'PASS' if condition else 'FAIL'}  {label}{': ' + detail if detail else ''}")

    health = api.call("GET", "/health")
    check("service healthy", health.get("ok") is True)
    check("simulation is explicitly enabled", health.get("sim_mode") is True)

    fixtures = api.call("GET", "/sixty-days/fixtures")
    check("four genuine recorded fixtures", fixtures["measured"]["recorded_calls"] == 4)
    check("measured extraction is 20/20", fixtures["measured"] == {
        "correct": 20, "total": 20, "recorded_calls": 4
    })

    evidence_fixtures = api.call("GET", "/sixty-days/evidence/fixtures")
    check("two genuine recorded evidence fixtures",
          evidence_fixtures["measured"]["recorded_calls"] == 2)
    check("measured visual checks are 6/6", evidence_fixtures["measured"] == {
        "correct": 6, "total": 6, "recorded_calls": 2
    })

    api.call("POST", "/sixty-days/demo/anchor", {"fixture": "short_window"})
    opened = api.call("POST", "/sixty-days/cases", {
        "fixture": "short_window", "applicant_ref": "DEMO-short-window"
    })
    check("letter reason is grounded", len(opened["deficiencies"]) == 1 and not opened["dropped"])
    check("identity evidence routes only to applicant", opened["requirements"][0]["source"] == "applicant_only")
    check("whole contact ladder registered", len(opened["wakes"]) == 8)
    by_kind = {wake["kind"]: wake for wake in opened["wakes"]}
    check("earlier deadline moves partial packet earlier", by_kind["build_partial"]["day"] == 37)
    check("final warning remains two days before deadline", by_kind["final_alert"]["day"] == 43)

    stored = api.call("GET", f"/sixty-days/cases/{opened['case_id']}")
    check("structured case persisted without raw transcript", "raw" not in stored and "transcription" not in stored)

    api.call("POST", "/sixty-days/demo/anchor", {"fixture": "damage_and_insurance"})
    damage = api.call("POST", "/sixty-days/cases", {
        "fixture": "damage_and_insurance", "applicant_ref": "DEMO-damage"
    })
    bad = api.call(
        "POST",
        f"/sixty-days/cases/{damage['case_id']}/evidence/check",
        {"fixture": "damage_close_bad", "requirement_key": "photo_wide"},
    )
    check("bad evidence gets an actionable retake", bad["decision"] == "retake"
          and "Step back" in bad["guidance"])
    good = api.call(
        "POST",
        f"/sixty-days/cases/{damage['case_id']}/evidence/check",
        {"fixture": "damage_wide_good", "requirement_key": "photo_wide"},
    )
    check("good framing is ready only for applicant review",
          good["decision"] == "ready_for_review" and "accept" in good["safety"])

    prepared = api.call(
        "POST",
        f"/sixty-days/cases/{damage['case_id']}/requests/prepare",
        {"requirement_key": "insurance_denial", "requested_on": "2026-08-10"},
    )
    check("insurer request is prepared but not sent",
          prepared["delivery"] == "applicant_sends"
          and prepared["status"] == "prepared_for_applicant"
          and "Nothing was sent" in prepared["safety"])
    check("prepared request has a no-reply wake", bool(prepared["tracking"]["wake_id"]))

    packet = api.call(
        "POST",
        f"/sixty-days/cases/{damage['case_id']}/packet",
        {"applicant_statement": "Please review my photographs and insurance records."},
    )
    check("packet uses both exact letter reasons",
          len(packet["verified_statements"]) == 2
          and all(item["quoted_text"] in "\n".join(packet["verified_statements"])
                  for item in damage["deficiencies"]))
    check("partial packet lists what is still missing",
          packet["status"] == "partial_draft" and len(packet["missing"]) >= 1)

    pdf, headers = api.call_bytes(
        "POST",
        f"/sixty-days/cases/{damage['case_id']}/packet.pdf",
        {"applicant_statement": "Please review my photographs and insurance records."},
    )
    check("draft PDF renders", pdf.startswith(b"%PDF") and len(pdf) > 1000)
    check("PDF response explicitly says not submitted",
          (headers.get("X-Submission-Status") or headers.get("x-submission-status"))
          == "not-submitted")

    damage_stored = api.call("GET", f"/sixty-days/cases/{damage['case_id']}")
    check("stored evidence omits image bytes and applicant narrative",
          all(
              "image" not in item and "raw" not in item and "transcription" not in item
              for item in damage_stored.get("evidence", [])
          )
          and "Please review my photographs" not in str(damage_stored))

    conformance = api.call("GET", "/sixty-days/conformance")
    check("conformance rows cite code and tests", all(row.get("implementation") and row.get("test") for row in conformance["rules"]))

    schema = api.call("GET", "/openapi.json")
    check("no send, submission, or bulk-reset endpoint", not any(
        "submit" in path or "send" in path or "sixty-days/reset" in path
        for path in schema["paths"]
    ))

    passed = sum(checks)
    print(f"\n{passed}/{len(checks)} Sixty Days demo checks passed against {args.url}")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
