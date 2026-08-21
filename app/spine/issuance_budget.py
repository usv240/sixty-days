"""A durable ceiling on developer key issuance.

The public console is credential-free, and the developer beta is now self-serve for the same
reason: an evaluator who has no way to ask the project owner for an invitation code must still be
able to exercise the API. A private code is not a security boundary when the people it excludes are
exactly the people meant to test the thing.

Removing the code moves the risk rather than removing it. What an open form can be abused for is
issuance itself: one script filling the key store. So issuance is what gets capped here, per
address per day, with a global ceiling behind it so a distributed script cannot walk around the
per-address cap.

The counters live in Firestore rather than memory because Cloud Run runs several instances and
scales to zero; an in-process counter would reset under load, which is precisely when it matters.

The counter is read before it is incremented, so two simultaneous requests can both pass a check
at the boundary and overshoot by the number of concurrent instances (at most three here).
Overshooting a key-issuance cap by two is harmless — the keys still expire on their own and still
grant one scope — whereas a read-modify-write transaction on every request would add latency to a
form a judge is waiting on. Denied requests are never counted, so a caller who hits the wall cannot
push the day further into denial.
"""

from __future__ import annotations

import hashlib
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class BudgetDecision:
    allowed: bool
    reason: str
    global_used: int
    global_cap: int
    caller_used: int
    caller_cap: int

    def as_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "keys_issued_today": self.global_used,
            "keys_allowed_today": self.global_cap,
            "your_keys_today": self.caller_used,
            "your_keys_allowed_today": self.caller_cap,
        }


class CounterStore(ABC):
    """Named integer counters that survive a restart."""

    @abstractmethod
    def read(self, key: str) -> int: ...

    @abstractmethod
    def bump(self, key: str) -> int: ...


class MemoryCounterStore(CounterStore):
    def __init__(self) -> None:
        self.values: dict[str, int] = {}

    def read(self, key: str) -> int:
        return self.values.get(key, 0)

    def bump(self, key: str) -> int:
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]


class FirestoreCounterStore(CounterStore):
    """Server-side atomic increment, so concurrent instances cannot lose a count."""

    def __init__(self, client, collection: str = "key_issuance_budget") -> None:
        self._client = client
        self._collection = collection

    def read(self, key: str) -> int:
        snapshot = self._client.collection(self._collection).document(key).get()
        if not snapshot.exists:
            return 0
        return int((snapshot.to_dict() or {}).get("count", 0))

    def bump(self, key: str) -> int:
        from google.cloud import firestore

        document = self._client.collection(self._collection).document(key)
        document.set({"count": firestore.Increment(1)}, merge=True)
        return self.read(key)


def caller_fingerprint(forwarded_for: str, client_host: str) -> str:
    """A coarse per-address bucket for the issuance ceiling.

    This is a rate-limiting bucket, not an authentication boundary, and it is deliberately not
    reversible: the raw address is hashed and truncated, so the counter cannot be used to build a
    log of who visited. `X-Forwarded-For` is attacker-controlled, which is acceptable for a
    ceiling whose worst case is a slightly higher key count, and never acceptable for anything
    that grants access.
    """
    address = ""
    if forwarded_for:
        address = forwarded_for.split(",")[0].strip()
    if not address:
        address = (client_host or "").strip()
    return hashlib.sha256((address or "unknown").encode("utf-8")).hexdigest()[:16]


class IssuanceBudget:
    GLOBAL_DENIED = (
        "The shared daily key-issuance ceiling for this public beta is reached. "
        "The public console needs no key at all, and the ceiling resets at 00:00 UTC."
    )
    CALLER_DENIED = (
        "You have created this beta's daily allowance of keys from this address. "
        "Existing keys keep working until they expire, and the allowance resets at 00:00 UTC."
    )

    def __init__(
        self,
        store: CounterStore,
        *,
        daily_cap: int = 400,
        per_caller_cap: int = 50,
        global_denied: str = "",
        caller_denied: str = "",
    ) -> None:
        self._store = store
        self.daily_cap = daily_cap
        self.per_caller_cap = per_caller_cap
        self.global_denied = global_denied or self.GLOBAL_DENIED
        self.caller_denied = caller_denied or self.CALLER_DENIED

    @classmethod
    def from_environment(cls, store: CounterStore) -> "IssuanceBudget":
        return cls(
            store,
            daily_cap=int(os.environ.get("KEY_ISSUANCE_DAILY_CAP", "400")),
            per_caller_cap=int(os.environ.get("KEY_ISSUANCE_PER_CALLER_CAP", "50")),
        )

    def check(self, now: datetime, caller: str) -> BudgetDecision:
        """Report whether a key may be issued, without consuming budget."""
        day = now.strftime("%Y-%m-%d")
        global_used = self._store.read(f"global_{day}")
        caller_used = self._store.read(f"caller_{day}_{caller}")

        if global_used >= self.daily_cap:
            reason, allowed = self.global_denied, False
        elif caller_used >= self.per_caller_cap:
            reason, allowed = self.caller_denied, False
        else:
            reason, allowed = "within budget", True

        return BudgetDecision(
            allowed=allowed,
            reason=reason,
            global_used=global_used,
            global_cap=self.daily_cap,
            caller_used=caller_used,
            caller_cap=self.per_caller_cap,
        )

    def consume(self, now: datetime, caller: str) -> BudgetDecision:
        """Count one issued key. Call this only after the key is actually issued."""
        day = now.strftime("%Y-%m-%d")
        global_used = self._store.bump(f"global_{day}")
        caller_used = self._store.bump(f"caller_{day}_{caller}")
        return BudgetDecision(
            allowed=True,
            reason="counted",
            global_used=global_used,
            global_cap=self.daily_cap,
            caller_used=caller_used,
            caller_cap=self.per_caller_cap,
        )
