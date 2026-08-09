# A deadline agent that knows when not to act

I created this post for the purposes of entering the All Things Agentic Hackathon.

A disaster-assistance decision letter can start a short appeal clock while the records it requests
are scattered across insurers, public offices, and a damaged home. The obvious agent demo is to
read the letter and draft persuasive prose. Sixty Days takes a different position: the hard problem
is durable coordination, and the system must know which acts remain the applicant's.

## The delegated job

Sixty Days reads a synthetic decision letter, preserves its exact stated reason, routes requested
records, checks only observable photo framing, prepares applicant-controlled requests, registers an
eight-wake deadline ladder, and builds a visibly partial draft packet.

Its completion boundary is deliberate. The system prepares, tracks, checks, and assembles. It does
not contact an insurer, file a records request, provide legal advice, predict eligibility, or submit
an appeal. There is no send or submit endpoint.

## Exact words before polished prose

Gemini 3.5 Flash transcribes synthetic photographed letters through a structured schema. A reason
or requirement survives only when its quoted source occurs in the transcription. Four recorded
calls grade 20 of 20 fields against adjacent truth.

That measurement still missed a privacy bug. Early recordings showed an occupancy fixture with
zero redactions. The apparent fixture anomaly exposed two general failures: the label set knew
clinical terms such as Patient but not Applicant, and the name pattern assumed title case while
official letters often print names in capitals. FEMA registration references were also missing.
The redaction layer now generalizes to PERSON and CASE_REF, with regression tests across every
letter fixture.

The lesson was simple: generated records are not evidence of correctness unless they are
regenerated after a safety fix.

## A clock that survives the demo

The letter date creates a deterministic deadline and eight durable wakes. A Cloud Scheduler worker
claims due Firestore records in production. The guided preset anchors a clearly labelled simulation
clock so a judge can see the same sequence in four minutes without deleting stored audit evidence.

Parallel acceptance testing found that this project's clock originally interfered with another
submission sharing the same substrate. Separate per-project clock documents and owning-project
filters now isolate simulations while leaving the production wall-clock scheduler shared.

## Partial is a state, not a failure

A packet may be useful before every requested record arrives, but it must never look complete.
Sixty Days renders exact reasons beside supporting items and keeps missing records visible in the
HTML and PDF. The PDF is marked draft and not submitted, and repeats synthetic application and
disaster references on every page for applicant verification.

Evidence-photo checking is equally narrow. It may say that a close frame does not show the needed
context and suggest a wider retake. It does not value damage, authenticate a photo, determine legal
sufficiency, or predict agency acceptance.

## Three additional Google models, three bounded jobs

Gemma 4 reviews already-pattern-redacted text for remaining person-name spans. Gemini 3.1 Flash
Image creates a non-data-bearing first-use illustration. Veo 3.1 Fast creates a four-second motion
briefing. The media is optional, does not autoplay, never enters a case, never becomes evidence, and
never appears in a packet.

Prompts, exact model IDs, byte counts, and SHA-256 hashes are committed in a public manifest. The
models serve comprehension without gaining authority over the applicant's case.

## Reproduce it

The public repository contains the as-built architecture SVG, Mermaid source, local and cloud
spin-up instructions, truth-adjacent model recordings, 23-step live acceptance flow, accessibility
gate, conformance map, and shared-substrate exit test.

Live product: https://sixty-days-109051079423.us-central1.run.app

Public repository: https://github.com/usv240/sixty-days

Demo video: ADD PUBLIC YOUTUBE OR VIMEO URL BEFORE PUBLISHING

This project was built during the contest period with AI coding assistants, synthetic data, and no
government endorsement.
