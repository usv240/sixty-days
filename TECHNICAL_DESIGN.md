# Sixty Days: Technical Design — As Built

**Status:** complete local build as of August 9, 2026. Read this with the repository-root
`AS_BUILT.md`; executable tests and the deployed HTTP surface outrank narrative documents.

Sixty Days is a self-contained repository and independent `sixty-days` Cloud Run service. Its
`app/spine/` is a reviewed snapshot of the same proven clock, wake, redaction, verification, and
tracing substrate used by Day Three; it shares the Google Cloud project and Firestore substrate,
not a product URL or repository. It is submitted separately in The Taskmaster category.

## 1. Product boundary

The system:

1. reads a clearly synthetic photographed determination letter;
2. keeps only reasons it can quote exactly;
3. redacts applicant identifiers before structured case persistence;
4. derives an auditable evidence plan from the quoted reason;
5. registers the full deadline ladder at intake;
6. screens synthetic evidence images for requested observable framing;
7. prepares records requests for the applicant to review and send;
8. tracks whether a requested record arrives; and
9. builds an optional, reviewable draft PDF from exact letter quotes and evidence metadata.

It does **not** decide eligibility, authenticate evidence, predict agency acceptance, give legal
advice, contact a third party, or submit an appeal. There is no send or submit endpoint.

Current FEMA guidance says supporting documents can be sent without a separate appeal form or
letter. The generated PDF is therefore an optional organizing draft, not a required agency form.

## 2. Actual architecture

```text
synthetic letter photo + adjacent truth
        |
        v
recorded Gemini 3.5 Flash transcription/extraction
        |
        v
LetterReader -> deterministic redaction -> exact-quote guard
        |
        v
requirements table -> CaseStore -> durable deadline wakes
        |                         |
        |                         +-> applicant-controlled request draft + no-reply wake
        v
recorded Gemini image checks -> EvidenceChecker -> booleans/metadata only
        |
        v
PacketBuilder -> DecisionLetterVerifier -> PacketRenderer -> draft PDF response
```

Code paths:

| Concern | Implementation |
|---|---|
| Letter extraction and quote guard | `app/sixty_days/reader.py` |
| Reason-to-evidence routing | `app/sixty_days/letters.py` |
| Deadline and no-reply wakes | `app/sixty_days/deadline.py` |
| Conservative image screening | `app/sixty_days/evidence.py` |
| Applicant-controlled request preparation | `app/sixty_days/outreach.py` |
| Exact-quote packet verification and PDF | `app/sixty_days/packet.py` |
| Structured persistence | `app/sixty_days/store.py` |
| HTTP surface | `app/service/sixty_days_routes.py` |
| Judge console | `app/web/sixty-days.html`, `app/web/sixty-days.js` |
| Executable acceptance flow | `app/scripts/sixty_days_demo_flow.py` |
| Date-stable frontend demo | `POST /sixty-days/demo/anchor` |

## 3. Model boundaries and measured fixtures

- Letter model: `gemini-3.5-flash`, Vertex AI global endpoint.
- Evidence model: `gemini-3.5-flash`, Vertex AI global endpoint.
- Redaction name reviewer: `gemma-4-26b-a4b-it-maas`, in process.
- Production/demo paths replay recordings; model recording is an explicit paid action.
- Four photographed letter recordings score 20/20 graded fields.
- Two clearly synthetic evidence-image recordings score 6/6 observable checks.
- The guided console anchors the simulated clock to the selected fixture's letter date before
  creating a fresh case. This prevents fixed evidence dates from making the recorded wake sequence
  drift as wall time advances; no durable case or audit record is deleted.

Evidence decisions are only:

- `ready_for_review`
- `retake`
- `manual_review`

`ready_for_review` means the requested feature is visible and the applicant should review the
image. It never means valid, sufficient, authentic, approved, or accepted.

## 4. Persistence and privacy

One Firestore document per case stores:

- explicitly synthetic `DEMO-*` application and `DR-DEMO*` disaster references;
- dates, determination, exact quoted reasons, and plain-language explanations;
- planned requirements and their statuses;
- evidence check booleans, guidance, fixture identifier, model, and recording flag;
- prepared request text and tracking metadata; and
- packet status, missing-item list, and build timestamp.

The public API rejects references without those demo prefixes. The store deliberately omits raw
letter text, model raw responses, photo bytes, photo transcriptions, real applicant
names/addresses/registration numbers, and the applicant’s free-text packet statement. The
statement exists only long enough to render the response PDF.

## 5. Request preparation, never autonomous contact

`RequestPreparer` accepts only `public_record` and `third_party` requirements. Its output:

- contains blanks for applicant identity/account details;
- is marked `prepared_for_applicant`;
- is marked `applicant_sends`;
- states that nothing was sent; and
- registers a capped no-reply wake through `DeadlineKeeper`.

Applicant-only photographs and identity documents are rejected from this route. The service does
not own legal authority to contact an insurer, utility, recorder, or legal-services organization
for a survivor.

## 6. Packet grounding

`DecisionLetterVerifier` is stricter than source existence. A system-authored sentence about the
decision must reproduce one of the letter’s exact quoted reasons. A plausible paraphrase is
rejected even when it cites a genuine letter artifact.

The PDF:

- is watermarked/labeled DRAFT;
- says it is optional, not an agency form, not submitted, and not legal advice;
- includes exact letter statements, applicant-authored narrative, evidence index, and missing
  items;
- embeds only evidence that reached `ready_for_review`; and
- labels every synthetic image as a screening demonstration.

Partial packets are first-class. Missing evidence remains visible rather than being silently
dropped.

## 7. Deadline behavior

The ladder is registered at case creation for days 3, 7, 14, 21, 30, 45, 52, and 58. If the
letter’s printed deadline is earlier than letter date plus 60 days, the earlier date controls and
the partial-packet/final-alert safeguards move earlier. Third-party requests get their own
21-day no-reply wake capped at the appeal deadline.

## 8. Actual Google Cloud topology

- One submission-specific Cloud Run service. It uses the same tested container source and shared
  spine as Day Three, while exposing a distinct root, judges page, health identity, and URL.
- Firestore for structured case/run/wake state.
- The existing `spine-scan-due` Cloud Scheduler job invokes a shared spine worker that claims due
  wakes from the same Firestore substrate; it is not a second Sixty Days service.
- Firestore simulation clocks are namespaced per public project
  (`sim/clock-sixty-days` here). Simulated advances filter candidates by the owning run's project
  before claiming, so concurrent demos cannot move or consume each other's timeline. The
  production wall-clock scanner stays shared and unfiltered.
- Cloud Trace and Cloud Logging are wired and verified.
- Vertex AI global endpoint serves Gemini and Gemma MaaS.
- Five differentiated service accounts are provisioned as intended boundaries, but the deployed
  service currently executes as `sa-reason`; do not claim per-agent runtime identity.
- Pub/Sub is not provisioned and is not in the code. Scan-due claims and executes due wakes
  directly.
- There is no Sixty Days Cloud Storage persistence, OpenFEMA ingestion, Secret Manager
  integration, or Veo explainer in this build.

## 9. HTTP surface

```text
GET  /sixty-days/fixtures
GET  /sixty-days/fixtures/{name}
GET  /sixty-days/fixtures/{name}/image
GET  /sixty-days/evidence/fixtures
GET  /sixty-days/evidence/fixtures/{name}/image
POST /sixty-days/cases
GET  /sixty-days/cases
GET  /sixty-days/cases/{case_id}
POST /sixty-days/cases/{case_id}/evidence/check
POST /sixty-days/cases/{case_id}/requests/prepare
POST /sixty-days/cases/{case_id}/chase
POST /sixty-days/cases/{case_id}/packet
POST /sixty-days/cases/{case_id}/packet.pdf
GET  /sixty-days/conformance
```

There is deliberately no reset, delete, send, contact, submit, or close-as-submitted route.

## 10. Research sources

- [FEMA Individual Assistance appeals quick reference](https://www.fema.gov/sites/default/files/documents/fema_ia-quick-reference_appeals.pdf)
  for the 60-day window, supporting-document examples, and the optional appeal form/letter.
- [FEMA, 8 Tips for Appealing FEMA’s Decision](https://www.fema.gov/fact-sheet/8-tips-appealing-femas-decision-1)
  for reading the letter’s reason and examples of insurance, occupancy, and ownership records.
- [GAO-20-503](https://www.gao.gov/products/gao-20-503) for historical evidence that insufficient
  damage and missing supporting evidence were common ineligibility reasons. This is problem
  context, never an outcome claim.
- [FEMA, Verifying Home Ownership or Occupancy](https://www.fema.gov/fact-sheet/verifying-home-ownership-or-occupancy)
  for alternative records and their date context.
- [FEMA, Help for Survivors with Insurance](https://www.fema.gov/sites/default/files/documents/fema_insurance_qrg_20241010.pdf)
  for settlement, denial, and coverage-exclusion documentation.
- [FEMA IHP application, eligibility, registration, and appeals](https://www.fema.gov/fact-sheet/fema-individuals-and-households-program-application-eligibility-registration-and-appeals)
  for the applicant/disaster references repeated on every draft PDF page.

The code treats these as routing examples and conservative packet checks. No listed document is
called sufficient, and a photo is optional supporting context rather than proof of eligibility.

The machine-readable mapping from each public rule to source, implementation, and test is served
at `/sixty-days/conformance`.

## 11. Verification

```powershell
cd app
python -m pytest tests -q
python scripts/check_a11y.py
python scripts/sixty_days_demo_flow.py --url https://SERVICE.run.app
```

The standalone completion baseline is 202 tests, accessibility green, and 23/23 Sixty Days
acceptance checks. The combined integration workspace currently has 291 tests; never substitute
that larger number for the standalone repository result. Update either number only from real output.
