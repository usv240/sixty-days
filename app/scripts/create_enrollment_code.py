"""Generate an invitation code and the hash-only value stored in Secret Manager."""

import hashlib
import secrets


code = "invite_" + secrets.token_urlsafe(24)
digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
print("Invitation code, shown once:")
print(code)
print("\nBETA_ENROLLMENT_CODE_HASH Secret Manager value:")
print(digest)
