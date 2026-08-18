"""Generate one Sixty Days beta key and its hash-only Cloud Run configuration."""

import argparse
import hashlib
import json
import secrets

parser = argparse.ArgumentParser()
parser.add_argument("--tenant", required=True, help="Lowercase tenant slug")
parser.add_argument("--label", default="")
args = parser.parse_args()

key = "sd_live_" + secrets.token_urlsafe(24)
digest = hashlib.sha256(key.encode()).hexdigest()
config = {digest: {"tenant_id": args.tenant, "label": args.label or args.tenant, "scopes": ["sixty-days:use"]}}
print("API key, shown once:")
print(key)
print("\nHash-only BETA_API_KEY_HASHES value:")
print(json.dumps(config, separators=(",", ":")))
