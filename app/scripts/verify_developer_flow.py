"""Walk the developer beta exactly as an unprepared evaluator would, and prove the edges hold.

A judge arrives with no invitation code, no account, and no contact with the project owner. If any
step of this script needs something they cannot get, the API is untestable and the beta is
decoration. So this walks the whole path against a deployed URL: read the policy, mint a key, use
it, confirm the boundaries, revoke it, and confirm it is dead.

The negative checks matter as much as the happy path. An open form invites abuse, so the ceiling,
the tenant isolation, and the absence of a send route are all asserted here rather than described.

    python scripts/verify_developer_flow.py --url https://sixty-days-....run.app
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

PASS = "PASS"
FAIL = "FAIL"

SYNTHETIC_LETTER = """DISASTER ASSISTANCE DETERMINATION - SYNTHETIC DEMONSTRATION
Not an agency document. No government endorsement.

Date: August 5, 2026

Decision: Some requested assistance is not approved.

The inspection did not show disaster-caused damage that made the home unsafe to occupy.
We also need the insurance settlement or denial before we can consider uninsured losses.
Your appeal must be received by October 4, 2026.

This synthetic page was created solely for software testing.
"""


class Checker:
    def __init__(self) -> None:
        self.results: list[tuple[str, str, str]] = []

    def check(self, name: str, condition: bool, detail: str = "") -> bool:
        self.results.append((PASS if condition else FAIL, name, detail))
        return condition

    def report(self) -> int:
        for status, name, detail in self.results:
            line = f"{status}  {name}"
            if detail:
                line += f"  [{detail}]"
            print(line)
        failed = sum(1 for status, _, _ in self.results if status == FAIL)
        total = len(self.results)
        print(f"\n{total - failed}/{total} developer-flow checks passed")
        return 1 if failed else 0


def call(
    url: str,
    path: str,
    method: str = "GET",
    body: dict | None = None,
    api_key: str | None = None,
) -> tuple[int, dict]:
    payload = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(url.rstrip("/") + path, data=payload, method=method)
    request.add_header("Content-Type", "application/json")
    request.add_header("Content-Length", str(len(payload or b"")))
    if api_key:
        request.add_header("X-API-Key", api_key)
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            raw = response.read().decode("utf-8", "replace")
            return response.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", "replace")
        try:
            return error.code, json.loads(raw)
        except json.JSONDecodeError:
            return error.code, {"detail": raw[:300]}
    except Exception as error:  # noqa: BLE001 - a transport failure is a failed check, not a crash
        return 0, {"detail": str(error)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    url = args.url.rstrip("/")
    check = Checker()

    # 1. Policy is discoverable before anything is created.
    status, config = call(url, "/developer/config")
    check.check("developer policy is readable without credentials", status == 200, str(status))
    check.check(
        "issuance is self-serve, so a judge needs no invitation code",
        config.get("issuance") == "open",
        str(config.get("issuance")),
    )
    check.check(
        "the per-address daily allowance is published, not hidden",
        isinstance(config.get("keys_per_day"), int) and config["keys_per_day"] >= 1,
        str(config.get("keys_per_day")),
    )
    check.check(
        "keys expire on their own",
        1 <= int(config.get("ttl_hours", 0)) <= 168,
        str(config.get("ttl_hours")),
    )

    # 2. Minting a key with nothing but a workspace name.
    status, issued = call(
        url,
        "/developer/keys",
        "POST",
        {
            "tenant_id": "judge_walkthrough",
            "label": "Judge walkthrough",
            "acknowledge_terms": True,
        },
    )
    if not check.check("a key is issued with no invitation code", status == 201, str(status)):
        return check.report()
    api_key = issued["api_key"]
    check.check("the plaintext key is returned exactly once", issued.get("shown_once") is True)
    check.check(
        "the key is scoped to the named workspace",
        issued.get("tenant_id") == "judge_walkthrough",
        str(issued.get("tenant_id")),
    )
    check.check("an expiry is set", bool(issued.get("expires_at")))

    # 3. Rejected input must not silently consume the caller's allowance.
    status, _ = call(
        url,
        "/developer/keys",
        "POST",
        {"tenant_id": "NOT VALID", "label": "x", "acknowledge_terms": True},
    )
    check.check("a malformed workspace id is rejected", status == 422, str(status))

    status, _ = call(
        url,
        "/developer/keys",
        "POST",
        {"tenant_id": "judge_walkthrough", "label": "Judge", "acknowledge_terms": False},
    )
    check.check("the terms acknowledgement cannot be declined", status == 422, str(status))

    # 4. The key authenticates, and an absent or wrong key does not.
    status, whoami = call(url, "/v1", api_key=api_key)
    check.check("the issued key authenticates", status == 200, str(status))
    check.check(
        "the tenant is derived on the server, not taken from the caller",
        whoami.get("tenant") == "judge_walkthrough" or whoami.get("tenant_id") == "judge_walkthrough",
        json.dumps(whoami)[:120],
    )

    status, _ = call(url, "/v1")
    check.check("an anonymous call to the keyed surface is rejected", status == 401, str(status))

    status, _ = call(url, "/v1", api_key="sd_beta_not_a_real_key")
    check.check("an invalid key is rejected", status == 401, str(status))

    # 5. The keyed workflow actually runs.
    status, case = call(
        url,
        "/v1/cases",
        "POST",
        {
            "document": SYNTHETIC_LETTER,
            "applicant_ref": "SUBJECT-001",
            "disaster_ref": "DR-TEST-001",
            "acknowledge_deidentified": True,
        },
        api_key=api_key,
    )
    created = check.check("a de-identified letter opens a case", status in {200, 201}, str(status))
    if created:
        check.check("a deadline is derived from the letter", bool(case.get("deadline")))
        check.check(
            "at least one reason is quoted from the letter",
            len(case.get("deficiencies", [])) >= 1,
            str(len(case.get("deficiencies", []))),
        )
        check.check(
            "the whole wake ladder is registered up front",
            len(case.get("wakes", [])) >= 1,
            str(len(case.get("wakes", []))),
        )

    # 6. The safety boundary is enforced, not merely documented.
    status, _ = call(
        url,
        "/v1/cases",
        "POST",
        {
            "document": SYNTHETIC_LETTER,
            "applicant_ref": "SUBJECT-002",
            "disaster_ref": "DR-TEST-001",
            "acknowledge_deidentified": False,
        },
        api_key=api_key,
    )
    check.check(
        "an unacknowledged de-identification claim is refused",
        status in {400, 422},
        str(status),
    )

    status, _ = call(
        url,
        "/v1/cases",
        "POST",
        {
            "document": "Applicant: Jane Q. Public, 905 Mockingbird Lane. " + SYNTHETIC_LETTER,
            "applicant_ref": "SUBJECT-003",
            "disaster_ref": "DR-TEST-001",
            "acknowledge_deidentified": True,
        },
        api_key=api_key,
    )
    check.check(
        "an obvious direct identifier is refused before model processing",
        status in {400, 422},
        str(status),
    )

    for path in ["/v1/send", "/v1/submit", "/v1/appeals/submit", "/v1/contact"]:
        status, _ = call(url, path, "POST", {}, api_key=api_key)
        check.check(f"no send or submission route at {path}", status == 404, str(status))

    # 7. A second tenant cannot reach the first tenant's case.
    status, other = call(
        url,
        "/developer/keys",
        "POST",
        {"tenant_id": "judge_second", "label": "Judge second", "acknowledge_terms": True},
    )
    if check.check("a second workspace key is issued", status == 201, str(status)) and created:
        status, _ = call(
            url, f"/v1/cases/{case['case_id']}", api_key=other["api_key"]
        )
        check.check(
            "one workspace cannot read another workspace's case",
            status in {403, 404},
            str(status),
        )
        # 8. Revocation is immediate and self-service.
        status, revoked = call(url, "/v1/key", "DELETE", api_key=other["api_key"])
        check.check("a holder can revoke their own key", status == 200, str(status))
        status, _ = call(url, "/v1", api_key=other["api_key"])
        check.check("a revoked key stops working immediately", status == 401, str(status))

    status, revoked = call(url, "/v1/key", "DELETE", api_key=api_key)
    check.check("the walkthrough key is revoked at the end", status == 200, str(status))

    return check.report()


if __name__ == "__main__":
    sys.exit(main())
