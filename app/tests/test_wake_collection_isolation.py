"""The wake collection must be this service's own, and every piece of config must agree on which.

Ownership predicates stop this service claiming a neighbour's wakes. They cannot stop a neighbour
claiming this service's wakes, because that depends on the neighbour running the fixed build. A
collection nobody else scans does not depend on anyone else's deployment, so the collection name is
the actual safeguard and these tests defend it.

The failure this catches is not a code change. It is drift: the module default, the deploy script,
and the index script each name a collection, and a service pointed at a collection whose composite
indexes were never built fails every due-wake query with FAILED_PRECONDITION -- which surfaces as a
scheduler that silently stops firing, not as an error anyone sees.
"""

import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1]

# The shared collection. Naming it here rather than inline is the point of the test: if this service
# is ever pointed back at it, these fail loudly instead of the safeguards going quiet.
SHARED = "wakes"


def _module_default() -> str:
    source = (APP / "service" / "main.py").read_text(encoding="utf-8")
    match = re.search(r'WAKE_COLLECTION = os\.environ\.get\("WAKE_COLLECTION", "([^"]+)"\)', source)
    assert match, "WAKE_COLLECTION default not found in service/main.py"
    return match.group(1)


def test_the_service_does_not_default_to_the_shared_collection() -> None:
    assert _module_default() != SHARED


def test_the_deploy_script_pins_the_same_collection() -> None:
    deploy = (APP / "deploy.sh").read_text(encoding="utf-8")
    assert f"WAKE_COLLECTION=${{WAKE_COLLECTION:-{_module_default()}}}" in deploy, (
        "deploy.sh uses --update-env-vars, which is additive: a stale WAKE_COLLECTION set on an "
        "earlier revision survives every later deploy unless the script sets it explicitly."
    )


def test_the_index_script_builds_indexes_for_the_collection_the_service_queries() -> None:
    indexes = (APP / "infra" / "apply_indexes.sh").read_text(encoding="utf-8")
    assert f'COLLECTION="${{WAKE_COLLECTION:-{_module_default()}}}"' in indexes
    for field in ("status due_at", "status lease_expires_at", "run_id due_at"):
        assert f'create_index "${{COLLECTION}}" {field}' in indexes, f"no index for ({field})"


def test_the_checked_in_index_definitions_cover_the_collection() -> None:
    import json

    definitions = json.loads((APP / "infra" / "firestore.indexes.json").read_text(encoding="utf-8"))
    groups = [index["collectionGroup"] for index in definitions["indexes"]]
    assert groups.count(_module_default()) == 3, (
        "scan_due needs (status, due_at) and (status, lease_expires_at); "
        "for_run needs (run_id, due_at)"
    )
