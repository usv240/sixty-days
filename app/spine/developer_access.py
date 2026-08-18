"""Invite-gated issuance of short-lived, scoped developer API keys."""

from __future__ import annotations

import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Protocol

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, SecretStr

from spine.api_access import ApiKeyAuthenticator, ApiPrincipal, hash_api_key, require_scope


class ApiKeyStore(Protocol):
    def get(self, digest: str) -> dict[str, Any] | None: ...
    def issue(self, digest: str, **record: Any) -> None: ...
    def revoke(self, digest: str, revoked_at: datetime) -> bool: ...


class KeyRequest(BaseModel):
    invitation_code: SecretStr
    tenant_id: str = Field(min_length=2, max_length=48, pattern=r"^[a-z0-9][a-z0-9_-]+$")
    label: str = Field(min_length=2, max_length=80)
    acknowledge_terms: Literal[True]


class KeyIssuer:
    def __init__(
        self,
        store: ApiKeyStore,
        *,
        product: str,
        scope: str,
        prefix: str,
        invitation_hash: str = "",
        ttl_hours: int = 168,
    ) -> None:
        self.store = store
        self.product = product
        self.scope = scope
        self.prefix = prefix
        self.invitation_hash = invitation_hash.strip().lower()
        if self.invitation_hash and (
            len(self.invitation_hash) != 64
            or any(char not in "0123456789abcdef" for char in self.invitation_hash)
        ):
            raise RuntimeError("BETA_ENROLLMENT_CODE_HASH must be a lowercase SHA-256 digest")
        if not 1 <= ttl_hours <= 168:
            raise RuntimeError("BETA_DEVELOPER_KEY_TTL_HOURS must be between 1 and 168")
        self.ttl = timedelta(hours=ttl_hours)

    @classmethod
    def from_environment(
        cls, store: ApiKeyStore, *, product: str, scope: str, prefix: str
    ) -> "KeyIssuer":
        raw_ttl = os.environ.get("BETA_DEVELOPER_KEY_TTL_HOURS", "168")
        try:
            ttl = int(raw_ttl)
        except ValueError as exc:
            raise RuntimeError("BETA_DEVELOPER_KEY_TTL_HOURS must be an integer") from exc
        return cls(
            store,
            product=product,
            scope=scope,
            prefix=prefix,
            invitation_hash=os.environ.get("BETA_ENROLLMENT_CODE_HASH", ""),
            ttl_hours=ttl,
        )

    @property
    def enabled(self) -> bool:
        return bool(self.invitation_hash)

    def issue(self, request: KeyRequest) -> dict[str, Any]:
        if not self.enabled:
            raise HTTPException(status_code=503, detail="Developer key issuance is not enabled.")
        supplied = hash_api_key(request.invitation_code.get_secret_value().strip())
        if not hmac.compare_digest(supplied, self.invitation_hash):
            raise HTTPException(status_code=401, detail="The invitation code is invalid.")
        issued_at = datetime.now(timezone.utc)
        expires_at = issued_at + self.ttl
        api_key = f"{self.prefix}_{secrets.token_urlsafe(32)}"
        digest = hash_api_key(api_key)
        self.store.issue(
            digest,
            tenant_id=request.tenant_id,
            label=request.label.strip(),
            scopes=[self.scope],
            issued_at=issued_at,
            expires_at=expires_at,
        )
        return {
            "api_key": api_key,
            "key_id": digest[:12],
            "tenant_id": request.tenant_id,
            "scope": self.scope,
            "issued_at": issued_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "shown_once": True,
        }


def build_developer_router(
    issuer: KeyIssuer,
    auth: ApiKeyAuthenticator,
    *,
    product: str,
    scope: str,
) -> APIRouter:
    router = APIRouter(tags=["developer-access"])

    @router.get("/developer/config")
    def config() -> dict[str, Any]:
        return {
            "product": product,
            "issuance": "invite_only" if issuer.enabled else "disabled",
            "ttl_hours": int(issuer.ttl.total_seconds() // 3600),
            "scope": scope,
            "header": "X-API-Key",
            "docs": "/docs",
        }

    @router.post("/developer/keys", status_code=201)
    def issue_key(request: KeyRequest) -> dict[str, Any]:
        return issuer.issue(request)

    @router.delete("/v1/key")
    def revoke_key(principal: ApiPrincipal = Depends(auth)) -> dict[str, Any]:
        require_scope(principal, scope)
        revoked = issuer.store.revoke(principal.key_digest, datetime.now(timezone.utc))
        if not revoked:
            raise HTTPException(
                status_code=409,
                detail="This operator-managed key must be revoked by the project owner.",
            )
        return {"revoked": True, "key_id": principal.key_id}

    return router
