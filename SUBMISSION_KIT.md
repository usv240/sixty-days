# Sixty Days: Submission Kit

This is the final evidence and recording plan for the independent **Taskmaster** submission.
Every number and infrastructure statement below is tied to the standalone repository or deployed
service. Do not substitute the combined workspace's larger test count.

## Submission facts

- Hosted project: `https://sixty-days-109051079423.us-central1.run.app`
- Judge evidence: `https://sixty-days-109051079423.us-central1.run.app/judges`
- Public repository: `https://github.com/usv240/sixty-days`
- Public acceptance: **23/23**
- Standalone tests: **187 passed**
- Recorded model measurements: **20/20 letter fields**, **6/6 evidence decisions**
- Shared substrate exit test: **10/10**
- Category: **The Taskmaster**

## Four-minute video

The video is a Stage One requirement and 30 percent of Stage Two. It must be public on YouTube or
Vimeo, no longer than four minutes, in English or accurately captioned, and must visibly prove that
the backend runs on Google Cloud.

### Pre-flight

1. Run `python scripts/sixty_days_demo_flow.py --url https://sixty-days-109051079423.us-central1.run.app` and save the 23/23 result.
2. Run the standalone suite and accessibility gate; confirm 187 passing tests.
3. Use a fresh 1440x900 browser window, light theme, no bookmarks bar, and no extensions.
4. Open the live app in the first tab and the `sixty-days` Cloud Run service in the second.
5. Open Cloud Trace only if a fresh trace from this exact rehearsal has been inspected.
6. Rehearse once. Record the product execution in one continuous take; edits may precede or follow it.
7. Keep the final export below 3:55 and correct the English captions before publishing.

### Shot list and narration

| Time | On screen | Narration |
|---|---|---|
| 0:00-0:22 | Landing hero and problem cards | “A disaster-assistance decision letter can start a short appeal clock while the records it requests are scattered across insurers, public offices, and a damaged home. Sixty Days is a deadline keeper that organizes that work without pretending to be a lawyer or acting as the applicant.” |
| 0:22-0:38 | Product boundaries and four-stage workflow | “It understands the letter, gathers and checks evidence, tracks applicant-controlled requests, and builds a reviewable draft. It never sends, contacts, or submits.” |
| 0:38-1:08 | Open `damage_and_insurance` | “This is the deployed service reading a synthetic photographed letter. Gemini 3.5 Flash preserves the exact stated reasons and requirements. Direct identifiers are redacted before structured persistence. Four recorded calls score twenty out of twenty fields against adjacent truth.” |
| 1:08-1:35 | Show deadline and registered wakes | “The whole deadline ladder is registered immediately: eight deterministic wakes, including early no-reply and final packet checks. The simulated clock is labeled; production due wakes are claimed from Firestore by a scheduled worker.” |
| 1:35-2:04 | Check close and wide evidence images | “The close image receives an actionable retake because the requested context is not visible. The wider image is ready for applicant review. The system checks only observable framing and legibility; it never values damage or predicts acceptance. Two recorded model calls score six out of six decisions.” |
| 2:04-2:28 | Prepare insurer request | “The agent prepares this insurer request and registers a no-reply wake. Notice the boundary: nothing was sent. The applicant reviews and sends every external request.” |
| 2:28-2:53 | Build packet and download PDF | “The packet keeps the letter's exact reason next to the supporting evidence and lists anything still missing. A partial packet stays visibly partial. The PDF is explicitly marked draft and not submitted.” |
| 2:53-3:14 | Advance simulated clock; show wake event | “Now time advances. The deadline watcher wakes, records the due action idempotently, and surfaces the missing work. That is asynchronous action over durable state, not a chat response.” |
| 3:14-3:34 | Conformance and judge pages | “Every public rule links to an official FEMA source, implementation, and test. The standalone repository has one hundred and eighty-seven passing tests, a twenty-three-step live acceptance flow, and explicit legal and privacy boundaries.” |
| 3:34-3:52 | Cloud Run dashboard, service and revision visible | “This is the independent `sixty-days` Cloud Run service in `us-central1`, backed by Firestore, Vertex AI, Cloud Scheduler, and Cloud Trace. The public URL you just watched is this revision.” |

Upload as **“Sixty Days - All Things Agentic Hackathon”**, public, with corrected English captions.

## Devpost copy

### Tagline

The letter says no. The clock has already started.

### Short description

Sixty Days turns a synthetic disaster-assistance decision letter into an auditable, applicant-
controlled evidence workflow. Gemini 3.5 Flash extracts only quote-grounded reasons and requested
documents; a durable deadline ladder tracks the case; evidence checks return retake, manual review,
or ready for applicant review; and a verifier builds a partial-safe draft packet. The agent prepares
and tracks work but never contacts a third party, provides legal advice, predicts eligibility, or
submits an appeal.

### Features and functionality

- Quote-grounded letter transcription and requirement routing
- Deterministic deadline calculation and eight registered wakes
- Observable evidence-photo framing checks with actionable retake guidance
- Applicant-reviewable records-request preparation and no-reply tracking
- Partial-safe draft packet and PDF with visible missing items
- Redaction, prompt-injection quarantine, independent verification, and durable audit state
- Public conformance map from policy source to implementation and test

### Technologies

Gemini 3.5 Flash and Gemma 4 MaaS through Vertex AI, Google GenAI SDK, FastAPI, Cloud Run,
Firestore, Cloud Scheduler, Cloud Trace/Logging, OpenTelemetry, Artifact Registry, and Cloud Build.
Pub/Sub, autonomous third-party contact, and appeal submission are not part of the build.

### Data sources

All demonstration letters, people, addresses, and images are synthetic. Policy claims cite the
current FEMA Individual Assistance appeals quick reference and appeal tips. Historical problem
context cites GAO-20-503. Truth files sit beside every fixture, and recorded model calls are graded.

### Findings and learnings

Exact quoting matters more than polished paraphrase when a deadline workflow starts from an
official letter. A redaction audit also showed why generated artifacts need regression tests: an
older pattern set missed all-caps applicant names and FEMA registration references, so PERSON and
CASE_REF coverage is now enforced. Finally, a visibly partial packet is safer than a false-complete
one, and preparing a request is meaningfully different from having authority to send it.

### Disclosure

Built during the contest period with AI coding assistants. The shared spine was developed during
the same period and copied into this standalone repository. All demonstration data is synthetic;
no government agency endorses the project.

## Final submission checklist

- [ ] Public YouTube or Vimeo video under four minutes with corrected English captions
- [ ] Live Cloud Run proof visible in the video
- [x] Public hosted project, no credentials required
- [x] Public standalone repository
- [x] Reproducible README and architecture diagram
- [x] Feature, technology, data-source, findings, limitations, and disclosure copy
- [x] 23/23 public acceptance, 187 tests, accessibility, and 10/10 exit test
- [ ] Final link and citation check immediately before Devpost submission
- [ ] Freeze the submitted revision and keep it available through judging
