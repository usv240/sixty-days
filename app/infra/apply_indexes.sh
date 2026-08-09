#!/usr/bin/env bash
# Create the Firestore composite indexes the spine's wake queries require.
#
# Idempotent: re-running is safe, an existing index is reported and skipped.
# Index builds are asynchronous and take a few minutes. Run this before the first
# scan_due, or queries will fail with FAILED_PRECONDITION.
#
# Usage: PROJECT_ID=agentic-fleet-2026 bash infra/apply_indexes.sh

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-agentic-fleet-2026}"

create_index() {
  local collection="$1" field_a="$2" field_b="$3" why="$4"
  echo "  ${collection}: (${field_a}, ${field_b})  -- ${why}"
  gcloud firestore indexes composite create \
    --collection-group="${collection}" \
    --field-config="field-path=${field_a},order=ascending" \
    --field-config="field-path=${field_b},order=ascending" \
    --project="${PROJECT_ID}" \
    --async \
    2>&1 | grep -v "already exists" || true
}

echo "Creating Firestore composite indexes in ${PROJECT_ID}"
create_index wakes status due_at            "scan_due: pending wakes whose time has arrived"
create_index wakes status lease_expires_at  "scan_due: reclaim wakes whose worker died"
create_index wakes run_id due_at            "for_run: a course's whole ladder, in order"

echo
echo "Index builds are asynchronous. Check readiness with:"
echo "  gcloud firestore indexes composite list --project=${PROJECT_ID}"
