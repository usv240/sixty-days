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
BETA_ENROLLMENT_SECRET="${BETA_ENROLLMENT_SECRET:-}"
# The worker route is closed even though the console is open. These two values are what
# spine/scheduler_auth.py checks; with them unset on Cloud Run the scanner fails closed.
SCHEDULER_IDENTITY="${SCHEDULER_IDENTITY:-agent-wake-scheduler@${PROJECT_ID}.iam.gserviceaccount.com}"

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

BETA_SECRET_MAPPINGS=()
if [[ -n "${BETA_API_SECRET}" ]]; then
  BETA_SECRET_MAPPINGS+=("BETA_API_KEY_HASHES=${BETA_API_SECRET}:latest")
fi
if [[ -n "${BETA_ENROLLMENT_SECRET}" ]]; then
  BETA_SECRET_MAPPINGS+=("BETA_ENROLLMENT_CODE_HASH=${BETA_ENROLLMENT_SECRET}:latest")
fi
BETA_SECRET_ARGS=()
if (( ${#BETA_SECRET_MAPPINGS[@]} )); then
  BETA_SECRET_VALUE="$(IFS=,; echo "${BETA_SECRET_MAPPINGS[*]}")"
  BETA_SECRET_ARGS=(--set-secrets "${BETA_SECRET_VALUE}")
fi

# Storage and compute resources are pinned here. Vertex model endpoints used by this build are
# available at global, so this check must not be described as pinning every byte or endpoint.
if [[ "${REGION}" != "us-central1" ]]; then
  echo "REGION is ${REGION} but every resource must be in us-central1." >&2
  echo "Cloud Run and Firestore deployment is intentionally limited to us-central1." >&2
  exit 1
fi

# --update-env-vars is additive: anything named here is written, anything omitted is left alone.
# That distinction matters for SCHEDULER_AUDIENCE. Passing it through as "${SCHEDULER_AUDIENCE:-}"
# writes an *empty* value when the caller has not exported one, and an empty audience makes
# verify_scheduler_token fail closed on Cloud Run -- every scan rejected, the deadline keeper
# silently stops, and the only symptom is a scheduler badge that goes stale minutes later. So the
# audience is named only when there is a real value to name; otherwise the deployed one survives.
#
# It is not derived from the service URL either. Cloud Run answers on two hostnames and the OIDC
# audience must be the exact one the scheduler job was provisioned with. Guessing wrong fails the
# same silent way.
ENV_VARS="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},REGION=${REGION},SIM_MODE=${SIM_MODE}"
ENV_VARS="${ENV_VARS},REPLAY_MODE=${REPLAY_MODE},PUBLIC_PROJECT=${PUBLIC_PROJECT}"
ENV_VARS="${ENV_VARS},WAKE_COLLECTION=${WAKE_COLLECTION:-wakes_sixty_days}"
ENV_VARS="${ENV_VARS},BETA_DEVELOPER_KEY_TTL_HOURS=168"
ENV_VARS="${ENV_VARS},SCHEDULER_SERVICE_ACCOUNT=${SCHEDULER_IDENTITY}"
if [[ -n "${SCHEDULER_AUDIENCE:-}" ]]; then
  ENV_VARS="${ENV_VARS},SCHEDULER_AUDIENCE=${SCHEDULER_AUDIENCE}"
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
  --update-env-vars "${ENV_VARS}" \
  "${BETA_SECRET_ARGS[@]}" \
  --labels "hackathon=all-things-agentic,component=${SERVICE}"

URL="$(run_gcloud run services describe "${SERVICE}" --project "${PROJECT_ID}" --region "${REGION}" --format 'value(status.url)' | tr -d '\r')"
echo
echo "Deployed: ${URL}"
echo
echo "Verify from an unauthenticated client:"
echo "  curl ${URL}/health"
echo "  curl -X POST -H \"Content-Type: application/json\" -d '{}' ${URL}/exit-test"

# The OIDC audience is the service URL, which is only known after the first deploy. On a first
# deploy it has to be set and the service redeployed, or the scanner fails closed and rejects every
# scan. On any later deploy the value already on the service was left untouched above, so this is
# only a reminder to check -- not a step that was skipped.
if [[ -z "${SCHEDULER_AUDIENCE:-}" ]]; then
  echo
  echo "SCHEDULER_AUDIENCE was not passed. The value already on the service was preserved."
  echo "Confirm the worker is still authenticated:"
  echo "  curl ${URL}/sixty-days/scheduler   # expect \"status\": \"running\""
  echo "If this was the first deploy, wire it now:"
  echo "  SCHEDULER_AUDIENCE=${URL} bash deploy.sh ${SERVICE}"
  echo "  bash infra/provision_scheduler.sh"
fi
