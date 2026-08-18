# Sixty Days integration beta

The `/v1` API is an optional key-protected workflow for synthetic or deliberately de-identified
determination-letter text. It does not change the public judge demo.

## Provision a key

```bash
cd app
python scripts/create_beta_key.py --tenant aid_group_one --label "Aid group one"
```

Give the plaintext key to the intended caller. Save the hash-only JSON temporarily under the
ignored `.beta-keys/` directory as `keys.json`.

```bash
gcloud secrets create sixty-days-beta-api-keys --data-file=.beta-keys/keys.json
gcloud secrets add-iam-policy-binding sixty-days-beta-api-keys \
  --member=serviceAccount:sa-reason@agentic-fleet-2026.iam.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor
gcloud iam roles create betaModelPredictor \
  --project=agentic-fleet-2026 \
  --title="Beta model predictor" \
  --permissions=aiplatform.endpoints.predict \
  --stage=GA
gcloud projects add-iam-policy-binding agentic-fleet-2026 \
  --member=serviceAccount:sa-reason@agentic-fleet-2026.iam.gserviceaccount.com \
  --role=projects/agentic-fleet-2026/roles/betaModelPredictor
BETA_API_SECRET=sixty-days-beta-api-keys bash deploy.sh
```

The custom role grants only model prediction. It does not grant model, endpoint, dataset, job, or IAM management. Create it once per project.

For an existing secret, add a version containing the complete set of active hashes. Revoke a key
by removing its digest and deploying the new secret version.

## Contract

- Header: `X-API-Key`
- Scope: `sixty-days:use`
- Input: de-identified letter text, a `SUBJECT-*` pseudonym, and a non-personal disaster reference
- Storage: verified structured reasons, deadlines, requirements, wakes, and draft state
- Excluded storage: raw letters, model responses, transcriptions, and applicant statements
- Safety: no legal advice, predicted outcome, third-party contact, filing, or submission

The server derives tenant ownership from the key and returns 404 for another tenant's case. Obvious
direct identifiers are rejected before model processing. This is not a guarantee that arbitrary
personal text is safe, so the beta remains limited to synthetic or deliberately de-identified data.

Cloud Run is capped at three instances. Use API Gateway quotas before a broader external rollout.
