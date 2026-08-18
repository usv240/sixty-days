"""Small, auditable API-key boundary for the optional integration API.

The public judge workflow stays credential-free. Only routes under ``/v1`` use this
boundary. Keys are never configured in source: Cloud Run receives a JSON object whose
keys are SHA-256 digests and whose values describe the tenant allowed to use that key.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader


API_KEY_HEADER = APIKeyHeader(
    name="X-API-Key",
    scheme_name="BetaApiKey",
    auto_error=False,
    description="A workspace-scoped beta key. It is shown once when provisioned.",
)
_TENANT = re.compile(r"^[a-z0-9][a-z0-9_-]{1,47}$")


@dataclass(frozen=True)
class ApiPrincipal:
    tenant_id: str
    label: str
    scopes: frozenset[str]
    key_id: str
    key_digest: str


def hash_api_key(api_key: str) -> str:
    """Return the only representation of a key that may enter configuration or logs."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


class ApiKeyAuthenticator:
    """Resolve a presented key to a server-controlled tenant and scope set."""

    def __init__(
        self,
        entries: dict[str, dict[str, Any]] | None = None,
        dynamic_lookup: Callable[[str], dict[str, Any] | None] | None = None,
    ) -> None:
        self._entries = self._validate(entries or {})
        self._dynamic_lookup = dynamic_lookup

    @classmethod
    def from_environment(
        cls,
        name: str = "BETA_API_KEY_HASHES",
        dynamic_lookup: Callable[[str], dict[str, Any] | None] | None = None,
    ) -> "ApiKeyAuthenticator":
        raw = os.environ.get(name, "").strip()
        if not raw:
            return cls(dynamic_lookup=dynamic_lookup)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{name} must be valid JSON") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError(f"{name} must be a JSON object")
        return cls(parsed, dynamic_lookup=dynamic_lookup)

    @classmethod
    def from_plaintext(
        cls, entries: dict[str, dict[str, Any]]
    ) -> "ApiKeyAuthenticator":
        """Test and local-development helper. Production must use hashed configuration."""
        return cls({hash_api_key(key): value for key, value in entries.items()})

    @property
    def enabled(self) -> bool:
        return bool(self._entries) or self._dynamic_lookup is not None

    def __call__(self, api_key: str | None = Security(API_KEY_HEADER)) -> ApiPrincipal:
        if not self.enabled:
            raise HTTPException(
                status_code=503,
                detail="The beta API is not provisioned on this deployment.",
            )
        if api_key is None or not api_key.strip():
            raise HTTPException(
                status_code=401,
                detail="X-API-Key is required.",
                headers={"WWW-Authenticate": "ApiKey"},
            )
        digest = hash_api_key(api_key.strip())
        matched: tuple[str, dict[str, Any]] | None = None
        for known, entry in self._entries.items():
            if hmac.compare_digest(digest, known):
                matched = (known, entry)
        if matched is None and self._dynamic_lookup is not None:
            try:
                dynamic = self._dynamic_lookup(digest)
            except Exception as exc:
                raise HTTPException(
                    status_code=503,
                    detail="API key verification is temporarily unavailable.",
                ) from exc
            if dynamic is not None:
                matched = (digest, self._validate({digest: dynamic})[digest])
        if matched is None:
            raise HTTPException(
                status_code=401,
                detail="The API key is invalid or revoked.",
                headers={"WWW-Authenticate": "ApiKey"},
            )
        known, entry = matched
        return ApiPrincipal(
            tenant_id=entry["tenant_id"],
            label=entry["label"],
            scopes=frozenset(entry["scopes"]),
            key_id=known[:12],
            key_digest=known,
        )

    @staticmethod
    def _validate(entries: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        clean: dict[str, dict[str, Any]] = {}
        for digest, raw in entries.items():
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise RuntimeError("Every configured API key name must be a lowercase SHA-256 digest")
            if not isinstance(raw, dict):
                raise RuntimeError("Every configured API key value must be an object")
            tenant = str(raw.get("tenant_id", "")).strip().lower()
            if not _TENANT.fullmatch(tenant):
                raise RuntimeError(f"Invalid tenant_id for key {digest[:12]}")
            label = str(raw.get("label") or tenant).strip()[:80]
            scopes = raw.get("scopes", ["beta:use"])
            if not isinstance(scopes, list) or not all(isinstance(item, str) for item in scopes):
                raise RuntimeError(f"Invalid scopes for key {digest[:12]}")
            clean[digest] = {"tenant_id": tenant, "label": label, "scopes": list(scopes)}
        return clean


def require_scope(principal: ApiPrincipal, scope: str) -> None:
    if scope not in principal.scopes and "*" not in principal.scopes:
        raise HTTPException(status_code=403, detail=f"API key lacks scope {scope}.")
