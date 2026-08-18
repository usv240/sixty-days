# Sixty Days: keep the deadline, evidence, and applicant together

**An applicant-controlled deadline and evidence workflow for disaster-assistance appeals.**

Sixty Days reads a synthetic determination letter, preserves its exact stated reason, calculates the
deadline, organizes supporting evidence, and builds a visibly incomplete draft packet when anything
is still missing. The agent carries the checklist and the clock; the applicant keeps every external
decision.

> **New here?** Open the live app, keep the default synthetic letter selected, and press
> **Start guided demo with this letter**. Nothing is sent and no real survivor data is used.

- [Open the live application](https://sixty-days-109051079423.us-central1.run.app)
- [Read the judge evidence](https://sixty-days-109051079423.us-central1.run.app/judges)
- [Inspect machine-checkable conformance](https://sixty-days-109051079423.us-central1.run.app/sixty-days/conformance)

## Judge it in 90 seconds

1. Press **Start guided demo with this letter**: the demo clock anchors to the synthetic letter date.
2. Inspect the exact quoted decision reason, routed evidence needs, deadline, and eight registered wakes.
3. Press **Screen close photo (expected retake)**: the observable framing check asks for a retake and selects the wider comparison.
4. Screen the wider photo: it may become ready for applicant review, never "accepted by FEMA."
5. Press **Prepare and track** using the clearly labelled do-not-send control, then inspect the draft with blanks and the no-reply wake.
6. Add an applicant explanation, press **Check draft packet**, and download the clearly marked draft PDF.
7. Advance the simulated days: watch the scheduled safeguard build a partial packet snapshot automatically while preserving every missing item.

Everything needed for the walkthrough is preset on the frontend. Disabled controls unlock only when
their prerequisites exist, so the judge can follow the numbered stages without guessing.

## Verified evidence

| Gate | Reproducible result |
|---|---:|
| Deployed public acceptance flow | **24/24** |
| Standalone automated tests | **219 passed** |
| Recorded letter fields | **20/20** |
| Recorded evidence decisions | **6/6** |
| Shared-substrate exit test | **10/10** |
| Accessibility gate | **Pass: light and dark themes** |

Every synthetic input has adjacent truth. Recorded Gemini outputs and grading reports are committed,
so the extraction and image-screening claims can be audited without trusting a screenshot.

## The problem

A disaster-assistance decision letter can start a short appeal window while the relevant records sit
with different people or organizations. The applicant may need to understand the exact reason, gather
case-specific documents, follow up on missing replies, and keep the deadline visible, all while
recovering from the disaster itself.

Sixty Days joins those tasks into one calm workflow. It is an organizer and deadline keeper, not a
lawyer, caseworker, insurer, or filing service.

## What happens end to end

| Stage | What the system does | What remains applicant-controlled |
|---|---|---|
| **1. Understand** | Transcribes a synthetic letter, removes direct identifiers, verifies an exact reason quote, and derives the stated deadline deterministically. | The decision letter outranks the generic catalogue. An unsafe mismatch stops for review. |
| **2. Gather** | Routes ownership, occupancy, insurance, or damage evidence and checks only observable photo framing and legibility. | No photo is called authentic, sufficient, causal, valued, or agency-approved. |
| **3. Track** | Prepares a records-request draft and registers a no-reply wake. | The applicant reviews and sends it; the service has no contact or send route. |
| **4. Review** | Builds a partial-safe draft packet, repeats synthetic references in each footer, and lists every missing item. | The applicant verifies the draft and decides what, if anything, to submit. |
| **5. Wake** | Registers the full day-3 through day-58 ladder up front. Due wakes create typed case actions; the packet safeguard builds a partial snapshot from accepted evidence automatically. | No wake contacts a third party, submits a packet, or claims an official filing or extension. |
| **6. Verify** | Rejects unsupported quotes, real-looking identifiers, and overconfident evidence claims. | It does not interpret law, predict eligibility, or forecast appeal success. |

## Architecture

![Sixty Days as-built architecture](docs/architecture.svg)

The solid path below is the live applicant workflow. The dotted path is optional onboarding media
generated at build time. It never sees a letter, image, case reference, or applicant narrative.

```mermaid
flowchart LR
    A[Synthetic judge letter and evidence] --> B[Cloud Run: sixty-days]
    API[Approved API client] --> K[Hash-only API key and server-derived tenant]
    K --> DI[De-identified /v1 letter intake]
    B --> L[Letter reader and redaction]
    DI --> L
    L --> D[Deadline and requirement router]
    D --> E[Evidence check and request preparation]
    E --> P[Packet builder and verifier]
    B <--> F[(Firestore: tenant cases, requirements, and wakes)]
    L --> V[Vertex AI: Gemini 3.5 Flash and Gemma 4 MaaS]
    F --> X[Deadline action executor]
    X --> P
    S[Shared Cloud Scheduler worker] --> F
    B --> T[Cloud Trace and Logging]
    P --> H[Applicant-reviewed draft]
    M[Gemini 3.1 Flash Image and Veo 3.1 Fast] -. recorded at build time .-> O[Static onboarding media]
    O -. outside case path .-> B
```

The domain modules and copied spine run inside one `sixty-days` Cloud Run service. It is not a fleet of
pretend microservices. The shared `spine-scan-due` scheduler invokes a worker that claims due wakes
from Firestore. Each claimed wake creates one idempotent, typed case action. The packet safeguard
actually builds and records a partial packet snapshot; no action sends or submits. Raw letter text,
image bytes, and applicant narrative are deliberately omitted from durable case records.

Only explicit `DEMO-*` application references and `DR-DEMO*` disaster references are accepted by
the public packet workflow. Day Three and Sixty Days share durable infrastructure, but their public
services, repositories, and simulation clocks are separate; simulated wake claims are filtered by
the owning project.

- [Diffable Mermaid source](docs/architecture.mmd)
- [Recorded media provenance: prompts, model IDs, sizes, and SHA-256 hashes](app/web/media/bonus-media-provenance.json)
- [Bonus evidence map](BONUS_EVIDENCE.md)

## Why each model is here

| Model | Narrow job | Boundary |
|---|---|---|
| **Gemini 3.5 Flash** | Structured transcription of synthetic letters and observable evidence-photo screening. | Outputs are schema-validated and graded against adjacent truth. |
| **Gemma 4 MaaS** (`gemma-4-26b-a4b-it-maas`) | Second-pass privacy review after deterministic redaction. | It does not interpret eligibility or legal rights. |
| **Gemini 3.1 Flash Image** | Creates the optional abstract first-use briefing. | Build-time media only; no applicant data or case facts. |
| **Veo 3.1 Fast** | Creates the optional four-second motion briefing. | Muted, user-controlled, and outside the case path. |

The additional models have narrow, inspectable roles. Their prompts, exact IDs, byte counts, and
hashes are public, and none of them creates evidence or makes an appeal decision.

## Safety and legal boundaries

- Synthetic, unbranded fixtures only; no real survivor or applicant data.
- Deterministic redaction covers names with common punctuation, lowercase labels, street addresses, PO boxes, and FEMA-style case references before model review.
- Every source reference must contain a nonempty quote; one valid reference cannot launder an empty one.
- No legal advice, eligibility prediction, appeal strategy, or outcome forecast.
- No send, contact, or submission endpoint; the applicant controls every external action.
- Evidence screening is limited to observable framing and legibility, never authenticity or damage valuation.
- A "ready for applicant review" result is not a claim that an agency will accept the evidence.
- Partial packets remain visibly partial; missing evidence is never converted into confidence.
- The appeal letter or form remains optional, in line with the reviewed FEMA guidance.
- Raw letters, photos, transcriptions, and applicant free text are omitted from Firestore.

## Research and citations

Official guidance changed the product. The decision letter now outranks the generic requirement
catalogue; insurer-document requests no longer treat a self-authored statement as equivalent; and
every PDF page repeats synthetic references for applicant verification. Historical GAO data explains
the problem context. It is never presented as a current denial rate.

### Complete source list

1. [FEMA: Individual Assistance Appeals Quick Reference](https://www.fema.gov/sites/default/files/documents/fema_ia-quick-reference_appeals.pdf) describes the 60-day appeal window, supporting-document examples, and an optional appeal form or letter; Sixty Days neither files nor calls its PDF official.
2. [FEMA: 8 Tips for Appealing FEMA's Decision](https://www.fema.gov/fact-sheet/8-tips-appealing-femas-decision-1) says the decision letter explains the reason and relevant documents; every routed requirement therefore begins with an exact verified quote.
3. [FEMA: Verifying Home Ownership or Occupancy](https://www.fema.gov/fact-sheet/verifying-home-ownership-or-occupancy) lists multiple records and date contexts; the planner offers examples without calling any one document sufficient.
4. [FEMA: Help for Survivors with Insurance](https://www.fema.gov/sites/default/files/documents/fema_insurance_qrg_20241010.pdf) distinguishes settlement information, denials, and policy evidence of exclusions or absent coverage; the applicant, not the service, contacts the insurer.
5. [FEMA: IHP Application, Eligibility, Registration and Appeals](https://www.fema.gov/fact-sheet/fema-individuals-and-households-program-application-eligibility-registration-and-appeals) instructs applicants to put application and disaster references on submitted pages; the draft repeats validated synthetic references and asks the applicant to verify them.
6. [GAO-20-503: Disaster Assistance](https://www.gao.gov/products/gao-20-503) reports historical 2016 to 2018 ineligibility context and cited reasons such as insufficient damage and missing support; this is not a current rate or an appeal-success estimate.

For the official-source hierarchy, exact source-to-guardrail mapping, and rejected claims, read the
[research traceability ledger](docs/research-traceability.md).

## Use it through the API

The public web console remains a synthetic, credential-free judge experience. The protected `/v1`
surface accepts de-identified determination-letter text for applicant-controlled preparation.
Every key derives a private tenant on the server. A caller cannot select another tenant in JSON.

The raw letter and model response are processed in memory and not persisted. Stored case state is
limited to pseudonymous references, verified reason quotes, deadlines, requirements, wake records,
and draft status. The API can prepare a third-party request and a packet draft, but it has no send,
contact, filing, submission, legal-advice, or outcome-prediction operation.

Full provisioning, expiry, and rotation instructions are in [the beta API guide](docs/api-beta.md).

Invited developers can open [the live Developer page](https://sixty-days-109051079423.us-central1.run.app/developer), enter the invitation
code supplied by the project owner, and generate a tenant-scoped key that expires after seven days.
The plaintext key is shown once and remains only in page memory. The page includes a connection
test, a copyable project request, immediate revocation, and a link to the interactive OpenAPI schema.

Operators can also create a non-expiring key through Secret Manager:

```bash
cd app
python scripts/create_beta_key.py --tenant aid_group_one --label "Aid group one"
```

Store the printed hash-only JSON as the `BETA_API_KEY_HASHES` Secret Manager value and expose it
to Cloud Run. Give the plaintext key only to the intended API user.

```bash
curl -H "X-API-Key: $SIXTY_DAYS_API_KEY" \
  https://sixty-days-109051079423.us-central1.run.app/v1

curl -X POST \
  -H "X-API-Key: $SIXTY_DAYS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"document":"DE-IDENTIFIED DETERMINATION LETTER ...","applicant_ref":"SUBJECT-001","disaster_ref":"DR-TEST-001","acknowledge_deidentified":true}' \
  https://sixty-days-109051079423.us-central1.run.app/v1/cases
```

Open `/docs`, select **Authorize**, and enter the key for interactive schemas. The API rejects
obvious direct identifiers before model processing, but an API key does not make arbitrary personal
documents safe. This beta is for synthetic or deliberately de-identified text only.

## Reproduce locally

Prerequisites: Python 3.12. New live model calls also require Application Default Credentials
for a Google Cloud project with Vertex AI enabled.

```bash
cd app
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
python -m pytest -q
python scripts/check_a11y.py
```

Run deterministically with the committed recordings:

```bash
export GOOGLE_CLOUD_PROJECT=agentic-fleet-2026
export SIM_MODE=true
export REPLAY_MODE=true
uvicorn service.main:app --reload
python scripts/sixty_days_demo_flow.py --url http://127.0.0.1:8000
curl -X POST -H "Content-Type: application/json" -d '{}' http://127.0.0.1:8000/exit-test
```

The guided control calls `/sixty-days/demo/anchor` before opening the selected fixture. It freezes
the labelled simulation at that letter's date without deleting case, wake, or audit records, so the
day-3 through day-58 sequence stays reproducible during judging. The close-photo preset automatically
selects the wider comparison after the expected retake.

Deploying from `app/` with `bash deploy.sh` targets the independent Cloud Run service
`sixty-days`. The explicit empty JSON body in the exit-test request matters; a bodyless POST
receives HTTP 411.

## Repository map

- `app/sixty_days/`: project domain logic
- `app/spine/`: copied, reviewed runtime substrate required by this standalone project
- `app/service/`: public and operational routes
- `app/fixtures/`: synthetic inputs, adjacent truth, and recorded model outputs
- `app/tests/`: unit, integration, safety, claim, and UI-contract tests
- `app/scripts/`: fixture creation, recording, grading, accessibility, demo, and deployment verification
- `docs/research-traceability.md`: official source-to-guardrail decisions and rejected claims
- [Validation evidence](VALIDATION_EVIDENCE.md): research-to-test evidence, adversarial checks, and explicit limits
- [Project differentiation](PROJECT_DIFFERENTIATION.md): concrete separation from the other submission and shared-spine disclosure
- `SUBMISSION_KIT.md`: evidence-backed video and Devpost plan

## Disclosure

Built during the contest period with AI coding assistants. All public demonstration data is
synthetic. No government agency endorses this project, and the generated packet has no official
status.
