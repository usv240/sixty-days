#!/usr/bin/env bash
# Deploy the standalone Sixty Days service to Cloud Run.
#
# Usage:
#   bash deploy.sh
#   SIM_MODE=true bash deploy.sh sixty-days
#
# Cost discipline, since the free trial on this billing account is closed:
#   --min-instances 0   nothing is charged while idle
#   --max-instances 3   a runaway loop cannot spend the budget
#   --allow-unauthenticated  judges must reach the site without credentials (Rules.md line 398).
#       Cost exposure is bounded by max-instances, replay mode, and budget alerts. Reset sim
#       state before recording, since /sim endpoints are public by this choice.

set -euo pipefail

SERVICE="${1:-sixty-days}"
PROJECT_ID="${PROJECT_ID:-agentic-fleet-2026}"
REGION="${REGION:-us-central1}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-sa-reason@${PROJECT_ID}.iam.gserviceaccount.com}"
SIM_MODE="${SIM_MODE:-true}"
REPLAY_MODE="${REPLAY_MODE:-true}"
PUBLIC_PROJECT="sixty-days"
BETA_API_SECRET="${BETA_API_SECRET:-}"

# WSL resolves the Windows Cloud SDK's extensionless `gcloud` through Linux Python, which uses a
# separate unauthenticated config under the WSL home. A Windows launcher must be invoked by a
# Windows shell; executing `gcloud.cmd` directly from bash makes bash parse batch syntax.
# `GCLOUD_BIN` remains overrideable for CI and non-Windows machines.
GCLOUD_BIN="${GCLOUD_BIN:-gcloud}"
GCLOUD_VIA_WINDOWS_POWERSHELL=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GCLOUD_WINDOWS_WRAPPER=""
if grep -qi microsoft /proc/version 2>/dev/null && command -v powershell.exe >/dev/null 2>&1; then
  GCLOUD_VIA_WINDOWS_POWERSHELL=true
  GCLOUD_WINDOWS_WRAPPER="$(wslpath -w "${SCRIPT_DIR}/infra/gcloud-wrapper.ps1")"
fi

run_gcloud() {
  if [[ "${GCLOUD_VIA_WINDOWS_POWERSHELL}" == "true" ]]; then
    powershell.exe -NoProfile -NonInteractive -File "${GCLOUD_WINDOWS_WRAPPER}" "$@"
  else
    "${GCLOUD_BIN}" "$@"
  fi
}

BETA_SECRET_ARGS=()
if [[ -n "${BETA_API_SECRET}" ]]; then
  BETA_SECRET_ARGS=(--set-secrets "BETA_API_KEY_HASHES=${BETA_API_SECRET}:latest")
fi

# Storage and compute resources are pinned here. Vertex model endpoints used by this build are
# available at global, so this check must not be described as pinning every byte or endpoint.
if [[ "${REGION}" != "us-central1" ]]; then
  echo "REGION is ${REGION} but every resource must be in us-central1." >&2
  echo "Cloud Run and Firestore deployment is intentionally limited to us-central1." >&2
  exit 1
fi

echo "Deploying ${SERVICE} to ${PROJECT_ID} in ${REGION}"
echo "  public_project=${PUBLIC_PROJECT}  sim_mode=${SIM_MODE}  replay_mode=${REPLAY_MODE}  sa=${SERVICE_ACCOUNT}"

run_gcloud run deploy "${SERVICE}" \
  --source . \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --service-account "${SERVICE_ACCOUNT}" \
  --min-instances 0 \
  --max-instances 3 \
  --concurrency 20 \
  --cpu 1 \
  --memory 512Mi \
  --timeout 300 \
  --allow-unauthenticated \
  --update-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},REGION=${REGION},SIM_MODE=${SIM_MODE},REPLAY_MODE=${REPLAY_MODE},PUBLIC_PROJECT=${PUBLIC_PROJECT}" \
  "${BETA_SECRET_ARGS[@]}" \
  --labels "hackathon=all-things-agentic,component=${SERVICE}"

URL="$(run_gcloud run services describe "${SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" --format 'value(status.url)' | tr -d '\r')"
echo
echo "Deployed: ${URL}"
echo
echo "Verify from an unauthenticated client:"
echo "  curl ${URL}/health"
echo "  curl -X POST -H \"Content-Type: application/json\" -d '{}' ${URL}/exit-test"
