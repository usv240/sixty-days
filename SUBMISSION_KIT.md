# Sixty Days: Submission Kit

This is the final evidence, recording, and Devpost package for the independent Taskmaster
submission. Every number below belongs to the standalone Sixty Days repository or its deployed
service. Do not substitute the larger combined-workspace count.

## Submission facts

- Hosted project: `https://sixty-days-109051079423.us-central1.run.app`
- Judge evidence: `https://sixty-days-109051079423.us-central1.run.app/judges`
- Conformance evidence: `https://sixty-days-109051079423.us-central1.run.app/sixty-days/conformance`
- Public repository: `https://github.com/usv240/sixty-days`
- Category: The Taskmaster
- Public acceptance flow: 24/24
- Standalone tests: 205 passed
- Recorded letter extraction: 20/20 fields
- Recorded evidence screening: 6/6 decisions
- Shared-substrate exit test: 10/10
- Accessibility: passing in light and dark themes
- Additional Google models: Gemma 4 MaaS, Gemini 3.1 Flash Image, and Veo 3.1 Fast

## What the video must prove

The video is required for Stage One and carries 30 percent of Stage Two. In less than four minutes,
it must make five things undeniable:

1. The friction is real and specific.
2. The system performs a multi-step workflow over durable time, not a single chat response.
3. The applicant retains control of every external action.
4. The architecture and safety boundaries are deliberate.
5. The demonstrated backend is running on Google Cloud.

The live product execution should be one continuous take. Introductory and closing stills may be
edited around it, but the proof-of-action sequence should not be cut.

## Pre-flight checklist

1. From `app/`, run:
   `python scripts/sixty_days_demo_flow.py --url https://sixty-days-109051079423.us-central1.run.app`
   and save the 24/24 result.
2. Run `python -m pytest -q` and confirm 205 passed.
3. Run `python scripts/check_a11y.py` and confirm both themes pass.
4. Use a fresh 1440 by 900 browser window in light mode. Hide bookmarks, extensions, notifications,
   personal accounts, and unrelated tabs.
5. Open the live app in tab one, the architecture diagram in tab two, and the Google Cloud Run
   service page for `sixty-days` in tab three.
6. Show Cloud Trace only if a fresh trace from the exact rehearsal has been inspected first.
7. Leave the default `damage_and_insurance` fixture selected.
8. Press **Start guided demo with this letter** and confirm the labelled clock anchors to
   August 5, 2026.
9. Rehearse once, then record one continuous product run.
10. Export below 3 minutes 55 seconds and correct the English captions before publishing.

## Four-minute shot list and exact narration

Timings are targets. Keep at least five seconds of final margin.

| Time | On screen | Say exactly |
|---|---|---|
| 0:00 to 0:20 | Landing hero and problem cards | "A disaster-assistance decision letter can start a short appeal clock while the records it requests are scattered across insurers, public offices, and a damaged home. Sixty Days keeps the reason, evidence, and deadline together without pretending to be a lawyer or acting as the applicant." |
| 0:20 to 0:35 | Four-stage workflow and boundaries | "It understands the letter, checks observable evidence, tracks applicant-controlled requests, and builds a reviewable draft. It never contacts a third party, predicts eligibility, or submits an appeal." |
| 0:35 to 1:05 | Open the console and press **Start guided demo with this letter** | "This is the live deployed service. The guided preset anchors a clearly labelled simulation clock to this synthetic letter, so every rehearsal proves the same sequence without deleting stored audit evidence. Gemini 3.5 Flash preserves exact reasons and requirements. Four recorded calls score twenty out of twenty fields against adjacent truth." |
| 1:05 to 1:30 | Show exact reason, deadline, requirements, and eight wakes | "The letter controls the plan. Its exact reason is quoted, the deadline is calculated deterministically, and all eight wakes are registered immediately. In production, a scheduled worker claims due work from Firestore on wall-clock time." |
| 1:30 to 1:58 | Press **Screen close photo**, then screen the automatically selected wider comparison | "The close image receives an actionable retake because the requested context is missing. The wider comparison becomes ready for applicant review. That phrase is deliberate. The system checks only framing and legibility. It does not authenticate evidence, value damage, or predict agency acceptance. Two recorded calls score six out of six decisions." |
| 1:58 to 2:20 | Prepare the insurer request | "The agent prepares an insurer request with blanks and registers a no-reply wake. Nothing is sent. The applicant reviews and sends every external request, and the service has no send endpoint." |
| 2:20 to 2:48 | Add the applicant statement, check the packet, and download the PDF | "The packet keeps the letter's quoted reason beside the evidence and lists everything still missing. Every page repeats validated synthetic application and disaster references for applicant verification. The PDF is clearly marked draft, optional, and not submitted." |
| 2:48 to 3:08 | Advance the simulated days and show the automatic packet snapshot | "Now time advances. The deadline keeper resumes from durable state. At the packet safeguard, it actually runs the packet builder against accepted evidence, stores a visibly partial snapshot with everything missing, and does not send or submit. That is asynchronous action over time, not a chat response." |
| 3:08 to 3:30 | Show the architecture diagram, then the judge evidence page | "One Cloud Run service coordinates bounded modules. Firestore stores structured cases and wakes, while raw letters, photo bytes, and applicant narrative are omitted. Gemini performs measured extraction, Gemma reviews redaction, and the Verifier rejects unsupported or empty quotes. The standalone repository passes two hundred and five tests." |
| 3:30 to 3:52 | Show the Cloud Run service, public URL, and current revision | "This is the independent sixty-days service running on Google Cloud in us-central1, with Firestore, Vertex AI, Cloud Scheduler, Cloud Trace, and scale-to-zero Cloud Run. The public URL you just watched is this deployed service." |

Upload publicly to YouTube or Vimeo with the title:

**Sixty Days: All Things Agentic Hackathon**

Use corrected English captions. Do not leave the video unlisted.

## Hardening evidence worth mentioning in judging

The best engineering story is not that no bug existed. It is that adversarial checks found bugs
before judging and turned them into permanent invariants.

- The Verifier used to accept a present source reference with an empty quote because an empty string
  is contained in every string. It now rejects empty and whitespace-only quotes, and a valid quote
  cannot launder an empty reference beside it.
- The deterministic privacy layer now covers hyphenated names, straight and typographic
  apostrophes, lowercase applicant labels, and PO boxes.
- Negative controls prove the expanded patterns do not erase organism names, susceptibility rows,
  or phrases such as "Name of disaster."
- Partial packets stay visibly partial. A missing record never becomes a confident eligibility claim.

These are verified by tests and should be described as hardening work, not as product outcome proof.

## Devpost copy

### Tagline

The letter says no. The clock has already started.

### Short description

Sixty Days turns a synthetic disaster-assistance decision letter into an auditable,
applicant-controlled evidence workflow. Gemini 3.5 Flash extracts only quote-grounded reasons and
requested documents. A durable deadline ladder tracks the case, evidence screening returns retake,
manual review, or ready for applicant review, and a verifier builds a partial-safe draft packet.
The agent prepares and tracks work but never contacts a third party, provides legal advice, predicts
eligibility, or submits an appeal.

### Features and functionality

- Quote-grounded letter transcription and requirement routing
- Deterministic deadline calculation and eight registered wakes
- Observable evidence-photo framing checks with actionable retake guidance
- Applicant-reviewable records-request preparation and no-reply tracking
- Partial-safe draft packet and PDF with visible missing items
- Synthetic references repeated in every PDF footer for applicant verification
- Redaction, prompt-injection quarantine, independent verification, and durable audit state
- Public policy-to-implementation conformance evidence

### Architecture and technologies

One FastAPI service runs on Cloud Run. Modular roles share a reviewed durable spine. Firestore stores
structured case, requirement, request, and wake state. Cloud Scheduler invokes the due-work path.
Cloud Trace and Logging expose execution evidence.

Models and tools:

- Gemini 3.5 Flash through Vertex AI for measured structured transcription and evidence screening
- Gemma 4 MaaS for second-pass privacy review
- Gemini 3.1 Flash Image for optional build-time onboarding media
- Veo 3.1 Fast for optional build-time motion briefing
- Google GenAI SDK, FastAPI, Firestore, Cloud Scheduler, Cloud Trace, OpenTelemetry, Artifact
  Registry, and Cloud Build

Pub/Sub, autonomous third-party contact, eligibility prediction, and appeal submission are not part
of the build.

### Data sources

All demonstration letters, people, addresses, case references, and images are synthetic. Policy
claims cite current FEMA Individual Assistance appeal guidance, ownership and occupancy examples,
insurance documentation guidance, and the September 2025 IHP explainer. Historical problem context
uses GAO-20-503 with its original 2016 to 2018 scope. Truth files sit beside every fixture, and
recorded model calls are graded against them.

### Findings and learnings

Exact quoting matters more than polished paraphrase when an administrative deadline begins with an
official letter. The strongest verifier rule also needed an adversarial test: a source reference
could be present while its quote was empty, so every reference now has to carry nonempty support.
Privacy patterns also needed ordinary real-world spellings, including hyphenated names, apostrophes,
lowercase labels, and PO boxes. Finally, a visibly partial packet is safer than a false-complete one,
and preparing a request is meaningfully different from having authority to send it.

### Disclosure

Built during the contest period with AI coding assistants. The shared spine was developed during
the same period and copied into this standalone repository. All demonstration data is synthetic.
No government agency endorses this project.

## Bonus contribution package

- Additional Google models: three integrated models provide the maximum model-integration bonus
  evidence. Prompts, model IDs, sizes, and hashes are public in `BONUS_EVIDENCE.md` and the media
  provenance manifest.
- Build story: [A Deadline Does Not Care That You Are Still Recovering](https://dev.to/ujwal240/a-deadline-does-not-care-that-you-are-still-recovering-3080)
  is public and contains the required hackathon-purpose disclosure.
- Social post: publish `docs/social-post.md` on an eligible social platform with the exact hashtag
  `#AllThingsAgenticHackathon`.

## Final submission checklist

- [ ] Public YouTube or Vimeo video under four minutes
- [ ] English captions reviewed and corrected
- [ ] Problem, value proposition, architecture, live action, and Google Cloud proof visible
- [ ] Continuous product execution shown without cuts
- [x] Public hosted project with no credentials required
- [x] Public standalone repository
- [x] README with local setup and deployment instructions
- [x] Submission-ready architecture SVG and Mermaid source
- [x] Three additional Google model integrations with public provenance
- [x] 24/24 public acceptance flow
- [x] 205 standalone tests
- [x] 20/20 letter fields and 6/6 evidence decisions
- [x] Accessibility gate and 10/10 exit test
- [x] Public build story published: https://dev.to/ujwal240/a-deadline-does-not-care-that-you-are-still-recovering-3080
- [ ] Add the public build story URL to the Sixty Days Devpost submission
- [ ] Public social post URL added to Devpost
- [ ] Final link, citation, and claim check
- [ ] Freeze and preserve the submitted revision through judging
