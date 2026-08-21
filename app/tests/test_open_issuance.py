"""Self-serve key issuance, and the ceiling that makes it defensible.

An invitation code cannot gate a beta that judges are supposed to evaluate: the people it excludes
are exactly the people meant to test it. Issuance is therefore open, and the abuse it invites --
one script filling the key store -- is bounded per address per day instead.

These tests pin both halves. Open issuance must actually work with no code, invite-gated mode must
still reject a wrong code, and the ceiling must be enforced, must not charge for rejected requests,
and must fail in the safe direction when the address is unknown or spoofed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from spine.api_access import ApiKeyAuthenticator, hash_api_key
from spine.api_key_store import MemoryApiKeyStore
from spine.developer_access import KeyIssuer, KeyRequest, build_developer_router
from spine.issuance_budget import (
    IssuanceBudget,
    MemoryCounterStore,
    caller_fingerprint,
)


NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
INVITE = "let-me-in-please"


class MemoryKeyStore:
    def __init__(self) -> None:
        self.records: dict[str, dict] = {}

    def get(self, digest: str):
        return self.records.get(digest)

    def issue(self, digest: str, **record) -> None:
        self.records[digest] = dict(record)

    def revoke(self, digest: str, revoked_at: datetime) -> bool:
        record = self.records.get(digest)
        if record is None:
            return False
        record["revoked_at"] = revoked_at
        return True


def make_issuer(*, open_issuance: bool, store: MemoryKeyStore | None = None) -> KeyIssuer:
    return KeyIssuer(
        store or MemoryKeyStore(),
        product="sixty-days",
        scope="sixty-days:use",
        prefix="sd_beta",
        invitation_hash="" if open_issuance else hash_api_key(INVITE),
        open_issuance=open_issuance,
    )


def make_client(issuer: KeyIssuer, budget: IssuanceBudget | None = None) -> TestClient:
    app = FastAPI()
    auth = ApiKeyAuthenticator(dynamic_lookup=issuer.store.get)
    app.include_router(
        build_developer_router(
            issuer,
            auth,
            product="Sixty Days",
            scope="sixty-days:use",
            issuance_budget=budget,
        )
    )
    return TestClient(app)


def key_payload(**overrides) -> dict:
    payload = {"tenant_id": "aid_group_demo", "label": "Aid group demo", "acknowledge_terms": True}
    payload.update(overrides)
    return payload


# --- Open issuance ---------------------------------------------------------------------


def test_a_judge_with_no_invitation_code_can_still_mint_a_key() -> None:
    """The whole point. If this fails, the API is untestable by the people evaluating it."""
    client = make_client(make_issuer(open_issuance=True))
    response = client.post("/developer/keys", json=key_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["api_key"].startswith("sd_beta_")
    assert body["tenant_id"] == "aid_group_demo"
    assert body["scope"] == "sixty-days:use"
    assert body["shown_once"] is True


def test_open_issuance_ignores_an_invitation_code_rather_than_rejecting_it() -> None:
    """A stale code pasted from old docs must not become a confusing failure."""
    client = make_client(make_issuer(open_issuance=True))
    response = client.post("/developer/keys", json=key_payload(invitation_code="anything-at-all"))
    assert response.status_code == 201


def test_the_config_route_advertises_open_issuance_and_the_real_cap() -> None:
    budget = IssuanceBudget(MemoryCounterStore(), daily_cap=400, per_caller_cap=50)
    client = make_client(make_issuer(open_issuance=True), budget)
    config = client.get("/developer/config").json()

    assert config["issuance"] == "open"
    assert config["keys_per_day"] == 50
    assert config["header"] == "X-API-Key"


def test_an_issued_key_actually_authenticates() -> None:
    """A key that cannot be used is worse than no key: it fails after the judge has moved on."""
    store = MemoryKeyStore()
    issuer = make_issuer(open_issuance=True, store=store)
    issued = issuer.issue(KeyRequest(**key_payload()))

    record = store.get(hash_api_key(issued["api_key"]))
    assert record is not None
    assert record["tenant_id"] == "aid_group_demo"
    assert record["scopes"] == ["sixty-days:use"]
    assert record["expires_at"] > record["issued_at"]


def test_the_tenant_cannot_be_smuggled_in_as_a_path_or_wildcard() -> None:
    client = make_client(make_issuer(open_issuance=True))
    for bad in ["../admin", "AID_GROUP", "a", "*", "aid group", ""]:
        response = client.post("/developer/keys", json=key_payload(tenant_id=bad))
        assert response.status_code == 422, bad


def test_the_terms_acknowledgement_cannot_be_declined_or_faked() -> None:
    client = make_client(make_issuer(open_issuance=True))
    # JSON 1 is deliberately not in this list: pydantic reads it as an affirmative True, and
    # a caller who sends 1 has acknowledged, not evaded.
    for bad in [False, "yes", None, 0]:
        response = client.post("/developer/keys", json=key_payload(acknowledge_terms=bad))
        assert response.status_code == 422, bad


# --- Invite-gated mode still works ------------------------------------------------------


def test_invite_gated_mode_still_rejects_a_wrong_code() -> None:
    client = make_client(make_issuer(open_issuance=False))
    response = client.post("/developer/keys", json=key_payload(invitation_code="wrong"))
    assert response.status_code == 401


def test_invite_gated_mode_rejects_a_missing_code_rather_than_crashing() -> None:
    """The field is optional in the schema now, so a bare request must fail closed, not 500."""
    client = make_client(make_issuer(open_issuance=False))
    response = client.post("/developer/keys", json=key_payload())
    assert response.status_code == 401


def test_invite_gated_mode_accepts_the_right_code() -> None:
    client = make_client(make_issuer(open_issuance=False))
    response = client.post("/developer/keys", json=key_payload(invitation_code=INVITE))
    assert response.status_code == 201


def test_issuance_disabled_entirely_is_still_possible() -> None:
    issuer = KeyIssuer(
        MemoryKeyStore(),
        product="sixty-days",
        scope="sixty-days:use",
        prefix="sd_beta",
        invitation_hash="",
        open_issuance=False,
    )
    assert issuer.enabled is False
    response = make_client(issuer).post("/developer/keys", json=key_payload())
    assert response.status_code == 503


# --- The ceiling -----------------------------------------------------------------------


def test_one_address_is_capped_and_told_why() -> None:
    budget = IssuanceBudget(MemoryCounterStore(), daily_cap=400, per_caller_cap=3)
    client = make_client(make_issuer(open_issuance=True), budget)

    for _ in range(3):
        assert client.post("/developer/keys", json=key_payload()).status_code == 201

    blocked = client.post("/developer/keys", json=key_payload())
    assert blocked.status_code == 429
    assert "allowance" in blocked.json()["detail"]


def test_a_rejected_request_does_not_spend_the_caller_s_allowance() -> None:
    """Otherwise a typo in the tenant field would quietly burn a judge's quota."""
    budget = IssuanceBudget(MemoryCounterStore(), daily_cap=400, per_caller_cap=2)
    client = make_client(make_issuer(open_issuance=True), budget)

    assert client.post("/developer/keys", json=key_payload(tenant_id="BAD")).status_code == 422
    assert client.post("/developer/keys", json=key_payload()).status_code == 201
    assert client.post("/developer/keys", json=key_payload()).status_code == 201
    assert client.post("/developer/keys", json=key_payload()).status_code == 429


def test_the_global_ceiling_stops_a_distributed_script() -> None:
    """The per-address cap alone is walkable by anyone with more than one address."""
    budget = IssuanceBudget(MemoryCounterStore(), daily_cap=2, per_caller_cap=50)
    for index in range(2):
        assert budget.check(NOW, f"caller_{index}").allowed is True
        budget.consume(NOW, f"caller_{index}")

    decision = budget.check(NOW, "caller_fresh")
    assert decision.allowed is False
    assert "ceiling" in decision.reason


def test_the_allowance_resets_the_next_day() -> None:
    budget = IssuanceBudget(MemoryCounterStore(), daily_cap=400, per_caller_cap=1)
    budget.consume(NOW, "caller")
    assert budget.check(NOW, "caller").allowed is False
    assert budget.check(NOW + timedelta(days=1), "caller").allowed is True


def test_two_addresses_do_not_share_one_allowance() -> None:
    budget = IssuanceBudget(MemoryCounterStore(), daily_cap=400, per_caller_cap=1)
    budget.consume(NOW, "caller_a")
    assert budget.check(NOW, "caller_a").allowed is False
    assert budget.check(NOW, "caller_b").allowed is True


# --- Address fingerprinting -------------------------------------------------------------


def test_the_forwarded_address_is_preferred_and_never_stored_in_the_clear() -> None:
    fingerprint = caller_fingerprint("203.0.113.9, 10.0.0.1", "10.0.0.1")
    assert fingerprint != "203.0.113.9"
    assert len(fingerprint) == 16
    assert fingerprint == caller_fingerprint("203.0.113.9", "")


def test_a_missing_address_still_produces_one_stable_bucket() -> None:
    """Unknown callers must share a bucket rather than each getting a fresh allowance."""
    assert caller_fingerprint("", "") == caller_fingerprint("", "")
    assert caller_fingerprint("", "") == caller_fingerprint("   ", "  ")


def test_different_addresses_land_in_different_buckets() -> None:
    assert caller_fingerprint("203.0.113.9", "") != caller_fingerprint("198.51.100.4", "")


def test_a_blank_forwarded_header_falls_back_to_the_socket_address() -> None:
    assert caller_fingerprint("", "198.51.100.4") == caller_fingerprint("198.51.100.4", "")


# --- Revocation -------------------------------------------------------------------------


def test_a_self_issued_key_can_be_revoked_by_its_holder() -> None:
    store = MemoryKeyStore()
    issuer = make_issuer(open_issuance=True, store=store)
    client = make_client(issuer)
    api_key = client.post("/developer/keys", json=key_payload()).json()["api_key"]

    revoked = client.delete("/v1/key", headers={"X-API-Key": api_key})
    assert revoked.status_code == 200
    assert revoked.json()["revoked"] is True


def test_revocation_requires_a_key_and_rejects_an_unknown_one() -> None:
    client = make_client(make_issuer(open_issuance=True))
    assert client.delete("/v1/key").status_code in {401, 403, 422}
    assert client.delete("/v1/key", headers={"X-API-Key": "sd_beta_nope"}).status_code in {401, 403}


def test_a_self_issued_key_stops_working_once_it_expires() -> None:
    """Expiry is enforced by the store, so a self-issued key must be subject to it too."""
    store = MemoryApiKeyStore("sixty-days")
    issuer = KeyIssuer(
        store,
        product="sixty-days",
        scope="sixty-days:use",
        prefix="sd_beta",
        open_issuance=True,
        ttl_hours=1,
    )
    issued = issuer.issue(KeyRequest(**key_payload()))
    digest = hash_api_key(issued["api_key"])
    assert store.get(digest) is not None

    store.now = store.now + timedelta(hours=2)
    assert store.get(digest) is None


def test_a_revoked_self_issued_key_stops_working_immediately() -> None:
    store = MemoryApiKeyStore("sixty-days")
    issuer = KeyIssuer(
        store,
        product="sixty-days",
        scope="sixty-days:use",
        prefix="sd_beta",
        open_issuance=True,
    )
    issued = issuer.issue(KeyRequest(**key_payload()))
    digest = hash_api_key(issued["api_key"])

    assert store.revoke(digest, datetime.now(timezone.utc)) is True
    assert store.get(digest) is None


def test_the_ttl_is_bounded_so_a_beta_key_cannot_be_permanent() -> None:
    with pytest.raises(RuntimeError):
        KeyIssuer(
            MemoryKeyStore(),
            product="sixty-days",
            scope="sixty-days:use",
            prefix="sd_beta",
            open_issuance=True,
            ttl_hours=10_000,
        )


def test_an_unknown_field_is_refused_rather_than_silently_dropped() -> None:
    """A caller who sends "tenant" believing it selects privilege must be told it did nothing.

    The server always derives the tenant and the scopes. Ignoring the field is safe, but it looks
    identical to accepting it, and the caller walks away believing they hold a key they do not.
    """
    client = make_client(make_issuer(open_issuance=True))

    for smuggled in [{"tenant": "someone_else"}, {"scopes": ["admin"]}, {"expires_at": "2099-01-01"}]:
        response = client.post("/developer/keys", json=key_payload(**smuggled))
        assert response.status_code == 422, smuggled
