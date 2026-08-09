"""Runtime configuration.

Region pinning is enforced here rather than by convention. `assert_region_pinned()` is called
at process start and by a test, so a resource created outside the declared region fails the
build rather than quietly violating the data sovereignty claim in the design.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# The single region every *stored* resource in this system must live in.
# Changing this is a deliberate act, not a convenience.
PINNED_REGION = "us-central1"

# Model inference is a separate question, and we should be accurate about it rather than
# overclaiming.
#
# Rules.md mandates Gemini 3.5 or newer. Verified on 2026-08-08: Gemini 3.x is served only from
# the `global` endpoint. It returns NOT_FOUND in us-central1, us-east5 and every other regional
# endpoint tested. Only Gemini 2.5 is regionally available, and 2.5 does not satisfy the rules.
#
# So the honest scope of our sovereignty claim is:
#   * Storage and compute  -> pinned to us-central1, enforced by assert_region_pinned() and a test
#   * Model inference      -> global endpoint, because the mandated model is not offered otherwise
#
# This is exactly why the redaction gate exists. Identifiers are stripped before anything crosses
# that boundary, so what leaves the pinned region is pseudonymised rather than personal.
MODEL_LOCATION = "global"


class RegionViolation(RuntimeError):
    """Raised when configuration would place a resource outside the pinned region."""


@dataclass(frozen=True)
class Settings:
    project_id: str
    region: str = PINNED_REGION

    # Simulation. Off by default so production behaviour is the default behaviour.
    sim_mode: bool = False

    # Fixture replay. When on, model calls are served from recorded responses.
    # Rehearsing a demo costs nothing; only the real recording runs live.
    replay_mode: bool = True

    # Model selection. Flash by default, Pro only where the design says so.
    model_flash: str = "gemini-3.5-flash"
    model_pro: str = "gemini-3.1-pro-preview"
    model_redact: str = "gemma3"
    model_location: str = MODEL_LOCATION

    # Lease held by a worker while it processes a wake, in seconds.
    lease_seconds: int = 90

    # A run producing this many consecutive rejections on one claim is circuit broken.
    max_claim_rejections: int = 3

    # Collections
    runs_collection: str = "runs"
    wakes_collection: str = "wakes"
    claims_collection: str = "claims"
    artifacts_collection: str = "artifacts"

    labels: dict[str, str] = field(default_factory=lambda: {"hackathon": "all-things-agentic"})

    def assert_region_pinned(self) -> None:
        if self.region != PINNED_REGION:
            raise RegionViolation(
                f"region is {self.region!r} but every resource must be in {PINNED_REGION!r}. "
                "Data sovereignty is a stated property of this system, not a preference."
            )


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
    if not project_id:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT is required")

    settings = Settings(
        project_id=project_id,
        region=os.environ.get("REGION", PINNED_REGION).strip(),
        sim_mode=_env_bool("SIM_MODE", False),
        replay_mode=_env_bool("REPLAY_MODE", True),
    )
    settings.assert_region_pinned()
    return settings
