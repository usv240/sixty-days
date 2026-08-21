#!/usr/bin/env bash
# Provision the Cloud Scheduler job that wakes this service.
#
# Usage:
#   bash infra/provision_scheduler.sh
#
# This is the piece that makes the deadline keeper autonomous. Without it the service only ever
# advances when a person calls it, which is a workflow UI, not an agent. The job posts to
# /internal/scan-due once a minute; the handler claims due wakes, runs the typed case action, and
# completes them. Nothing here contacts a third party or submits anything.
#
# The job authenticates with an OIDC token minted for a dedicated service account and scoped to
# this service's URL as the audience. The service verifies both (see spine/scheduler_auth.py), so
# the worker route stays closed even though the public console is deliberately credential-free.
# Re-running this script is safe: an existing job is updated in place.

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-agentic-fleet-2026}"
LOCATION="${LOCATION:-us-central1}"
SERVICE="${SERVICE:-sixty-days}"
JOB="${JOB:-sixty-days-wake-scan}"
SCHEDULER_IDENTITY="${SCHEDULER_IDENTITY:-agent-wake-scheduler@${PROJECT_ID}.iam.gserviceaccount.com}"
SCHEDULE="${SCHEDULE:-* * * * *}"

# Same WSL launcher problem as deploy.sh: a Windows gcloud shim must be invoked by a Windows shell.
GCLOUD_BIN="${GCLOUD_BIN:-gcloud}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USE_WINDOWS_SHELL=false
WINDOWS_WRAPPER=""
if grep -qi microsoft /proc/version 2>/dev/null && command -v powershell.exe >/dev/null 2>&1; then
  USE_WINDOWS_SHELL=true
  WINDOWS_WRAPPER="$(wslpath -w "${SCRIPT_DIR}/gcloud-wrapper.ps1")"
fi

run_gcloud() {
  if [[ "${USE_WINDOWS_SHELL}" == "true" ]]; then
    powershell.exe -NoProfile -NonInteractive -File "${WINDOWS_WRAPPER}" "$@"
  else
    "${GCLOUD_BIN}" "$@"
  fi
}

URL="$(run_gcloud run services describe "${SERVICE}" \
  --project "${PROJECT_ID}" --region "${LOCATION}" \
  --format 'value(status.url)' | tr -d '\r')"

if [[ -z "${URL}" ]]; then
  echo "Could not resolve the URL for Cloud Run service ${SERVICE}. Deploy it first." >&2
  exit 1
fi

echo "Provisioning ${JOB}"
echo "  target   ${URL}/internal/scan-due"
echo "  schedule ${SCHEDULE}"
echo "  identity ${SCHEDULER_IDENTITY}"

EXISTING="$(run_gcloud scheduler jobs list \
  --project "${PROJECT_ID}" --location "${LOCATION}" \
  --filter "name:${JOB}" --format 'value(name)' | tr -d '\r')"

ACTION="create"
if [[ -n "${EXISTING}" ]]; then
  ACTION="update"
fi

# --attempt-deadline is short and retries are bounded on purpose. A scan that cannot finish in
# thirty seconds should be retried by the next minute's tick, not held open; wake claiming is
# idempotent, so a retry is always cheaper than a long-running request.
run_gcloud scheduler jobs "${ACTION}" http "${JOB}" \
  --project "${PROJECT_ID}" \
  --location "${LOCATION}" \
  --schedule "${SCHEDULE}" \
  --time-zone Etc/UTC \
  --uri "${URL}/internal/scan-due" \
  --http-method POST \
  --oidc-service-account-email "${SCHEDULER_IDENTITY}" \
  --oidc-token-audience "${URL}" \
  --attempt-deadline 30s \
  --max-retry-attempts 3 \
  --min-backoff 5s \
  --max-backoff 60s \
  --max-doublings 2 \
  --description "Wakes the Sixty Days deadline keeper. Claims due wakes and runs typed case actions. No external contact or submission." \
  --quiet

echo
echo "Forcing one execution so the job proves itself now rather than at the next minute:"
run_gcloud scheduler jobs run "${JOB}" --project "${PROJECT_ID}" --location "${LOCATION}" --quiet

echo
echo "Confirm the worker route rejects anonymous callers:"
echo "  curl -s -o /dev/null -w '%{http_code}\\n' -X POST ${URL}/internal/scan-due   # expect 401"
