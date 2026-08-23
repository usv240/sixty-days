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
- Standalone tests: 357 passed
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

**The recording itself lives in one place: [DEMO_SCRIPT.md](DEMO_SCRIPT.md).** Beat timings,
pre-flight, exact narration, click order, and what to do if a beat runs long are all there, and the
whole take is continuous with no cuts anywhere -- the rules reward "unedited, live execution" and
that is easier to honour than to edit around. This file carries the submission-form material only.
Two scripts drift; one does not.

## Three moments the video should not skip

Each was added after an audit, and each answers a sceptical question a recording cannot.

**The reminder that fires with nobody watching.** Arm it in the first thirty seconds and do not
touch it again. It registers a reminder ninety seconds out on the real calendar; the page only
polls to ask whether it has happened. Cloud Scheduler claims it on its next pass and the record
names the Cloud Run revision that executed it. Measured arm-to-fired: 111 and 131 seconds across
two runs, with a 150-second ceiling. This is the beat that answers "you pressed a button" without
argument, because between arming and firing you are visibly doing something else.

**The scheduler badge.** The demo clock is simulated and the page says so, which fairly invites the
question of whether anything runs on its own. The badge beside it reads "Real scheduler woke this
service 12s ago" and refreshes while you watch. Show it next to the simulated clock and name the
difference out loud; the contrast is the honest version of the autonomy claim.

**The live model call.** Everything else replays a recording. Press "Read the letter live" and it
calls Gemini 3.5 Flash on Vertex AI on a letter image with no transcript supplied, then scores the
answer against the same truth file by the same fields as the published run. It takes ten to thirty
seconds; let it run rather than cutting. Five of five, live, is worth more than any claim about
fixtures.

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
- [x] 357 standalone tests
- [x] 20/20 letter fields and 6/6 evidence decisions
- [x] Accessibility gate and 10/10 exit test
- [x] Public build story published: https://dev.to/ujwal240/a-deadline-does-not-care-that-you-are-still-recovering-3080
- [ ] Add the public build story URL to the Sixty Days Devpost submission
- [ ] Public social post URL added to Devpost
- [x] Model Armor screening live, with its measured miss published
- [x] Live Gemini call a judge can trigger, bounded per visitor and per day
- [x] Dedicated Cloud Scheduler job, with wall-clock proof in the product
- [x] Rules compliance verified by script: 24 checks against the deployed service
- [ ] Final link, citation, and claim check
- [ ] Freeze and preserve the submitted revision through judging
