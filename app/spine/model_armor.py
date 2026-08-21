"""Google Cloud Model Armor as an additional screen in front of the model.

This project already screens untrusted text deterministically: identifiers are redacted by pattern
before anything leaves the process, instruction-shaped lines are quarantined rather than obeyed, and
the Verifier discards any claim whose exact words are absent from the source. Those checks are the
ones the tests pin, and they keep working when nothing else does.

Model Armor is added in front of them, not instead of them. It is a managed classifier for prompt
injection, jailbreak attempts, malicious URIs, and sensitive data, and it catches shapes a pattern
set will not anticipate. But it is a classifier: it has a confidence level, it can be wrong in both
directions, and it is a network call that can fail. Treating it as the whole defence would replace a
guarantee with a probability.

So the contract here is deliberately narrow:

* A `MATCH_FOUND` on prompt injection is a **hard block**. Something is trying to steer the agent.
* Anything else, including an outage, a timeout, or a missing configuration, is **not** treated as
  a pass. It returns `available=False` and the deterministic layer decides, exactly as it did
  before this module existed.

That asymmetry is the point. Model Armor can only ever make this stricter, never more permissive,
so adding it cannot weaken a guarantee that is already tested.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ArmorVerdict:
    """What the screen concluded, and whether it was able to conclude anything at all."""

    available: bool
    blocked: bool
    match_state: str = "UNKNOWN"
    filters: dict[str, str] = field(default_factory=dict)
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "blocked": self.blocked,
            "match_state": self.match_state,
            "filters": self.filters,
            "detail": self.detail,
        }


class ModelArmorScreen:
    def __init__(
        self,
        project_id: str,
        location: str = "us-central1",
        template: str = "",
        timeout_seconds: float = 6.0,
    ) -> None:
        self.project_id = project_id
        self.location = location
        self.template = template.strip()
        self.timeout_seconds = timeout_seconds
        self._credentials = None

    @classmethod
    def from_environment(cls, project_id: str) -> "ModelArmorScreen":
        return cls(
            project_id=project_id,
            location=os.environ.get("MODEL_ARMOR_LOCATION", "us-central1").strip(),
            template=os.environ.get("MODEL_ARMOR_TEMPLATE", "").strip(),
        )

    @property
    def enabled(self) -> bool:
        return bool(self.template and self.project_id)

    @property
    def endpoint(self) -> str:
        return (
            f"https://modelarmor.{self.location}.rep.googleapis.com/v1/"
            f"projects/{self.project_id}/locations/{self.location}/"
            f"templates/{self.template}:sanitizeUserPrompt"
        )

    def _token(self) -> str:
        """Reuse the instance's credentials instead of rediscovering them per request.

        Calling `google.auth.default()` and forcing a refresh on every screen costs a metadata
        server round trip on a path that is already in front of a model call, and throws away a
        token that is still valid. Credentials are discovered once and refreshed only when the
        library says they are no longer usable.
        """
        from google.auth.transport.requests import Request

        if self._credentials is None:
            import google.auth

            self._credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
        if not self._credentials.valid:
            self._credentials.refresh(Request())
        return self._credentials.token

    def screen(self, text: str) -> ArmorVerdict:
        """Screen untrusted text. Never raises: an unavailable screen is not a passing screen."""
        if not self.enabled:
            return ArmorVerdict(available=False, blocked=False, detail="not configured")
        if not text.strip():
            return ArmorVerdict(available=False, blocked=False, detail="nothing to screen")

        payload = json.dumps({"userPromptData": {"text": text}}).encode()
        request = urllib.request.Request(self.endpoint, data=payload, method="POST")
        request.add_header("Content-Type", "application/json")
        try:
            request.add_header("Authorization", f"Bearer {self._token()}")
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8", "replace"))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            # Fail neither open nor closed: hand the decision back to the deterministic layer.
            return ArmorVerdict(available=False, blocked=False, detail=f"unavailable: {exc}")
        except Exception as exc:  # noqa: BLE001 - credentials or SDK problems land here
            return ArmorVerdict(available=False, blocked=False, detail=f"unavailable: {exc}")

        return self.interpret(body)

    @staticmethod
    def interpret(body: dict[str, Any]) -> ArmorVerdict:
        """Turn a sanitize response into a verdict.

        Only prompt injection and jailbreak blocks. Sensitive-data findings are informative here
        rather than fatal: the deterministic redaction gate already removed identifiers before this
        text existed, and a second opinion should not be able to reject a letter the applicant is
        entitled to have read.
        """
        result = body.get("sanitizationResult") or {}
        match_state = str(result.get("filterMatchState", "UNKNOWN"))
        filters: dict[str, str] = {}
        for name, entry in (result.get("filterResults") or {}).items():
            state = "UNKNOWN"
            if isinstance(entry, dict):
                for value in entry.values():
                    if isinstance(value, dict) and value.get("matchState"):
                        state = str(value["matchState"])
                        break
            filters[str(name)] = state

        injection = filters.get("pi_and_jailbreak", "NO_MATCH_FOUND") == "MATCH_FOUND"
        return ArmorVerdict(
            available=True,
            blocked=injection,
            match_state=match_state,
            filters=filters,
            detail=(
                "Model Armor detected a prompt-injection or jailbreak attempt."
                if injection
                else "No prompt-injection or jailbreak match."
            ),
        )
