# Sixty Days: Submission Plan

**Track:** The Taskmaster
**Portfolio role:** second complete project on the shared agentic spine
**Hosted project:** `https://sixty-days-109051079423.us-central1.run.app`

> A decision letter arrives, a 60-day clock starts, and the evidence hunt begins.

## 1. The friction

A disaster survivor receives a dense assistance decision while also trying to obtain documents
from insurers, public-record offices, utilities, and their own damaged home. The system turns the
letter’s exact quoted reason into a concrete evidence plan and holds the deadline while evidence
arrives.

The differentiator is not generic letter drafting. It is a standing watch that accumulates
case-specific evidence, changes the ask when framing is wrong, tracks applicant-sent records
requests, and produces an honest partial draft before the deadline.

## 2. Evidence and citations

| Claim | Source |
|---|---|
| Current Individual Assistance guidance says appeals must be submitted within 60 days of the date on the decision letter and lists supporting-document examples | [FEMA Individual Assistance appeals quick reference](https://www.fema.gov/sites/default/files/documents/fema_ia-quick-reference_appeals.pdf) |
| The decision letter should be read for the reason and requested documentation; examples include insurer, occupancy, and ownership records | [FEMA, 8 Tips for Appealing FEMA’s Decision](https://www.fema.gov/fact-sheet/8-tips-appealing-femas-decision-1) |
| From 2016 through 2018, roughly 1.7 million applicants were determined ineligible; common reasons included insufficient damage, failure to submit supporting evidence, and failure to contact an inspector | [GAO-20-503](https://www.gao.gov/products/gao-20-503) |
| FEMA lists alternative ownership and occupancy records and describes their date context; one rigid document should not be prescribed when the letter and official alternatives allow others | [FEMA, Verifying Home Ownership or Occupancy](https://www.fema.gov/fact-sheet/verifying-home-ownership-or-occupancy) |
| FEMA's insurance guide distinguishes settlement information, denial letters, and proof that coverage is excluded or absent | [FEMA, Help for Survivors with Insurance](https://www.fema.gov/sites/default/files/documents/fema_insurance_qrg_20241010.pdf) |
| A September 2025 IHP explainer instructs applicants to include their application and disaster numbers on every page of submitted documentation | [FEMA IHP application, eligibility, registration, and appeals](https://www.fema.gov/fact-sheet/fema-individuals-and-households-program-application-eligibility-registration-and-appeals) |

The GAO finding is historical problem context, not an estimate of current denial rates or product
impact. An unsupported five-percent appeal-rate claim was removed during the August 8 audit.

Current FEMA guidance also says a separate appeal letter/form is optional when supporting
documents are sent. The generated PDF is presented only as an optional organizing draft.

## 3. What is built

| Component | Behavior |
|---|---|
| Letter Reader | Replays four real Gemini 3.5 Flash extractions; a reason survives only if its exact quote appears in the redacted source |
| Reason Decoder / Evidence Planner | Uses a versioned, tested table to route each quoted deficiency to a concrete source |
| Deadline Keeper | Registers the full day 3–58 wake ladder at intake and caps every action at the letter deadline |
| Evidence Checker | Replays two real Gemini visual checks and returns only ready-for-review, retake, or manual-review |
| Request Preparer | Creates a fill-in draft and no-reply wake; the applicant sends it |
| Packet Builder / Verifier | Rejects unquoted regulatory paraphrases and renders an optional draft PDF with visible missing items |
| Console and acceptance flow | Runs the full path at `/sixty-days`; `scripts/sixty_days_demo_flow.py` proves it |

Measured results:

- letters: 20/20 graded fields across four recorded model calls;
- evidence: 6/6 observable checks across two recorded model calls;
- standalone repository: 202 tests (291 in the separate combined integration workspace);
- Sixty Days executable flow: 23/23;
- accessibility: WCAG gate green in light and dark themes.

## 4. Honest autonomy boundary

The service autonomously reads, routes, schedules, screens, verifies, assembles, and wakes.
Actions that require the survivor’s identity or legal authority stop at a prepared draft:

- the applicant reviews and sends an insurer, utility, or records request;
- the applicant reviews every image;
- the applicant authors their own explanatory statement; and
- the applicant reviews and submits any appeal material.

There is no contact, send, or submit endpoint. That boundary is both a legal/safety decision and an
executable OpenAPI assertion.

## 5. Rubric mapping

| Criterion | Demonstrated implementation |
|---|---|
| Continuous action | Long-lived case with all deadline wakes registered at intake plus a separate no-reply wake for applicant-sent records requests |
| Multi-step task completion | Quote-grounded letter read → evidence plan → framing checks → records-request preparation → draft packet |
| State management | Structured Firestore case state; raw transcripts, image bytes, and applicant narrative deliberately omitted |
| Modular architecture | Shared spine plus separate reader, planner, deadline, evidence, outreach, packet, store, and route modules |
| Safe tool scope | One deployed runtime identity is disclosed honestly; five differentiated identities are provisioned boundaries, not claimed per-agent execution |
| Verifiable action | 23-step executable flow against the HTTP service; recorded model outputs and adjacent ground truth ship in the image |
| Google Cloud | Cloud Run, Firestore, Cloud Scheduler, Cloud Trace/Logging, Vertex AI Gemini, and Gemma MaaS |

Pub/Sub, OpenFEMA ingestion, autonomous third-party contact, Cloud Storage packet persistence,
Veo, and per-agent runtime identities are not part of this build and must not appear as claims.

## 6. Four-minute video

| Time | Beat |
|---|---|
| 0:00–0:25 | Letter arrives; explain the 60-day standing watch and applicant-control boundary |
| 0:25–0:55 | Open `damage_and_insurance`; show exact quoted reasons, redaction count, routes, and all registered wakes |
| 0:55–1:30 | Screen the too-close synthetic photo: actionable retake. Screen the wide photo: ready for applicant review, never “accepted” |
| 1:30–2:00 | Prepare the insurer request. Show “nothing was sent,” applicant-sends status, and no-reply wake |
| 2:00–2:40 | Build the packet; show exact letter statements and missing items; download the labeled draft PDF and show its synthetic application/disaster references repeated in the page footer |
| 2:40–3:10 | Advance the simulated clock and show the agent wake itself |
| 3:10–3:35 | Open conformance: each rule maps to an official FEMA source, implementation, and test |
| 3:35–4:00 | Cloud Run, Firestore, Vertex recordings, Cloud Trace, 202 standalone tests, 23/23 acceptance, accessibility |

## 7. Submission checklist

- Deploy and run `scripts/sixty_days_demo_flow.py` against the public project-number URL.
- Run the 10/10 shared exit test and Day Three 17/17 regression after deploy.
- Verify the independent Sixty Days root and its PDF route from a clean, unauthenticated client.
- Link Sixty Days from Day Three and Judges only after the public 23/23 flow is green.
- Capture Cloud Run revision, Trace evidence, and the measured fixture catalogues.
- Use no agency seals, marks, or language implying endorsement.
- Build the Sixty Days Devpost submission and video separately from Day Three.
