# Sixty Days

Sixty Days reads a synthetic disaster determination letter, extracts its deadline and evidence
requirements, checks supplied evidence, prepares applicant-reviewable request drafts, and builds
a draft appeal packet. It does not provide legal advice, send third-party communications, or
submit an appeal.

- Live app: https://sixty-days-109051079423.us-central1.run.app
- Judge brief: https://sixty-days-109051079423.us-central1.run.app/judges
- Independent code root: app/

## Verify locally

    cd app
    python -m pip install -e ".[dev]"
    python -m pytest -q
    python scripts/check_a11y.py

Run with Application Default Credentials and a Google Cloud project:

    export GOOGLE_CLOUD_PROJECT=agentic-fleet-2026
    export SIM_MODE=true
    export REPLAY_MODE=true
    uvicorn service.main:app --reload

Deploying from app/ with bash deploy.sh targets the independent Cloud Run service sixty-days.
See REPOSITORY_MANIFEST.md for the repository boundary.
