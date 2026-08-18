from datetime import timedelta
import json

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from spine.api_access import ApiKeyAuthenticator, ApiPrincipal, hash_api_key
from spine.api_key_store import MemoryApiKeyStore
from spine.developer_access import KeyIssuer, build_developer_router


def app_for(auth: ApiKeyAuthenticator) -> TestClient:
    app = FastAPI()

    @app.get("/v1/whoami")
    def whoami(principal: ApiPrincipal = Depends(auth)):
        return {"tenant_id": principal.tenant_id, "key_id": principal.key_id}

    return TestClient(app)


def test_key_resolves_server_controlled_tenant_and_openapi_security_scheme():
    auth = ApiKeyAuthenticator.from_plaintext({
        "dt_test_secret": {"tenant_id": "aid_one", "label": "Aid one", "scopes": ["sixty-days:use"]}
    })
    api = app_for(auth)
    response = api.get("/v1/whoami", headers={"X-API-Key": "dt_test_secret"})
    assert response.status_code == 200
    assert response.json()["tenant_id"] == "aid_one"
    assert "BetaApiKey" in api.get("/openapi.json").json()["components"]["securitySchemes"]


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "wrong"}])
def test_missing_or_wrong_key_is_unauthorized(headers):
    auth = ApiKeyAuthenticator.from_plaintext({
        "right": {"tenant_id": "tenant_one", "label": "One", "scopes": ["*"]}
    })
    assert app_for(auth).get("/v1/whoami", headers=headers).status_code == 401


def test_unprovisioned_beta_api_fails_closed():
    assert app_for(ApiKeyAuthenticator()).get("/v1/whoami").status_code == 503


def test_environment_contains_hashes_not_plaintext(monkeypatch):
    digest = hash_api_key("never-store-this")
    monkeypatch.setenv("BETA_API_KEY_HASHES", json.dumps({
        digest: {"tenant_id": "tenant_one", "label": "One", "scopes": ["*"]}
    }))
    auth = ApiKeyAuthenticator.from_environment()
    assert app_for(auth).get("/v1/whoami", headers={"X-API-Key": "never-store-this"}).status_code == 200


def developer_app(store, issuer):
    auth = ApiKeyAuthenticator(dynamic_lookup=store.get)
    app = FastAPI()
    app.include_router(build_developer_router(
        issuer, auth, product="Sixty Days", scope="sixty-days:use"
    ))

    @app.get("/v1/whoami")
    def whoami(principal: ApiPrincipal = Depends(auth)):
        return {"tenant_id": principal.tenant_id}

    return TestClient(app)


def test_invited_developer_can_issue_use_and_revoke_a_temporary_key():
    store = MemoryApiKeyStore("sixty-days")
    issuer = KeyIssuer(
        store,
        product="sixty-days",
        scope="sixty-days:use",
        prefix="sd_beta",
        invitation_hash=hash_api_key("invite-once"),
    )
    api = developer_app(store, issuer)
    issued = api.post("/developer/keys", json={
        "invitation_code": "invite-once",
        "tenant_id": "aid_two",
        "label": "Aid two",
        "acknowledge_terms": True,
    })
    assert issued.status_code == 201
    key = issued.json()["api_key"]
    assert key not in str(store.records)
    assert api.get("/v1/whoami", headers={"X-API-Key": key}).json()["tenant_id"] == "aid_two"
    assert api.delete("/v1/key", headers={"X-API-Key": key}).status_code == 200
    assert api.get("/v1/whoami", headers={"X-API-Key": key}).status_code == 401


def test_invalid_invitation_cannot_issue_a_key():
    store = MemoryApiKeyStore("sixty-days")
    issuer = KeyIssuer(
        store,
        product="sixty-days",
        scope="sixty-days:use",
        prefix="sd_beta",
        invitation_hash=hash_api_key("correct"),
    )
    api = developer_app(store, issuer)
    response = api.post("/developer/keys", json={
        "invitation_code": "wrong",
        "tenant_id": "aid_two",
        "label": "Aid two",
        "acknowledge_terms": True,
    })
    assert response.status_code == 401
    assert store.records == {}


def test_expired_dynamic_key_is_rejected():
    store = MemoryApiKeyStore("sixty-days")
    key = "sd_beta_expired"
    store.issue(
        hash_api_key(key),
        tenant_id="aid_two",
        label="Aid two",
        scopes=["sixty-days:use"],
        issued_at=store.now - timedelta(hours=2),
        expires_at=store.now - timedelta(hours=1),
    )
    assert app_for(ApiKeyAuthenticator(dynamic_lookup=store.get)).get(
        "/v1/whoami", headers={"X-API-Key": key}
    ).status_code == 401


def test_dynamic_lookup_failure_fails_closed():
    def broken(_digest):
        raise RuntimeError("database unavailable")

    with pytest.raises(HTTPException) as failure:
        ApiKeyAuthenticator(dynamic_lookup=broken)("key")
    assert failure.value.status_code == 503
