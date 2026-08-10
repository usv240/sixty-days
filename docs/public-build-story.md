# A deadline agent that knows when not to act

I created this post for the purposes of entering the All Things Agentic Hackathon.

A disaster-assistance decision letter can start a short appeal clock while requested records remain
scattered across insurers, public offices, and a damaged home. The obvious AI demo is to read the
letter and draft persuasive prose. Sixty Days takes a different position: the hard problem is
durable coordination, and the system must know which acts still belong to the applicant.

## The friction, with honest denominators

[GAO-20-503](https://www.gao.gov/products/gao-20-503) reports that approximately 4.4 million
applicants were referred to FEMA's Individuals and Households Program from 2016 through 2018, and
roughly 1.7 million were determined ineligible during that historical period. The cited reasons
included insufficient damage and failure to submit supporting evidence.

Those figures are historical context. They are not a current denial rate, an appeal-success rate,
or a prediction of how many people this product could help.

Current
[FEMA Individual Assistance appeal guidance](https://www.fema.gov/sites/default/files/documents/fema_ia-quick-reference_appeals.pdf)
describes a 60-day window from the decision-letter date and explains that the letter identifies the
reason and relevant supporting documents. Sixty Days turns that bounded process into a standing
watch.

The fourth number belongs to the product itself. Four recorded Gemini 3.5 Flash calls extract 20 of
20 graded letter fields against adjacent synthetic truth. That proves behavior on committed
fixtures, not legal accuracy or agency acceptance.

## The delegated job

Sixty Days reads a synthetic decision letter, preserves its exact stated reason, routes requested
records, checks only observable photo framing, prepares applicant-controlled request drafts,
registers an eight-wake deadline ladder, and builds a visibly partial draft packet.

Its completion boundary is deliberate. The system prepares, tracks, checks, and assembles. It does
not contact an insurer, file a records request, provide legal advice, predict eligibility, or submit
an appeal. There is no contact, send, or submit endpoint.

This is the product's operational twist: the agent owns the waiting and follow-through without
claiming authority over the applicant's case.

## Exact words before polished prose

Gemini 3.5 Flash transcribes synthetic photographed letters through a structured schema. A reason or
requirement survives only when its exact quoted source occurs in the transcription.

Boundary testing found that the shared Verifier did not fully enforce that promise. A source
reference could be present while its quote was empty. Because an empty string is contained in every
string, the claim passed. The repaired Verifier now rejects empty and whitespace-only quotes, and a
valid reference cannot launder an empty companion reference.

That finding matters more than a polished model answer. It protects the invariant that the packet
depends on: no quote, no claim, no rendered sentence.

## Privacy failed on ordinary spellings

An earlier audit found that all-caps applicant names and FEMA registration references could survive
redaction. Further boundary testing found four more ordinary formats: hyphenated names, straight and
typographic apostrophes, lowercase applicant labels, and PO boxes.

The deterministic gate now covers all of them. Negative controls prove that the broader patterns do
not erase organism names, susceptibility rows, or a phrase such as "Name of disaster: SEVERE STORMS
AND FLOODING." Gemma 4 reviews already-redacted text for remaining person-name spans.

The lesson is that privacy tests need realistic spelling variation, not only happy-path fixtures.

## A clock that survives the demo

The letter date creates a deterministic deadline and eight durable wakes. A Cloud Scheduler worker
claims due Firestore records in production. The guided preset anchors a clearly labelled simulation
clock so a judge can see the sequence in minutes without deleting stored audit evidence.

Parallel acceptance testing exposed cross-project interference when Day Three and Sixty Days shared
one simulation clock. The fix introduced separate per-project clock documents and owning-project
filters for simulated claims. The production wall-clock worker remains shared and intentionally
unfiltered.

The system also survives repeated failure, concurrent wake dispatch, cancelled work, and deadline
windows from 60 days to zero without duplicating wake IDs or hiding a partial packet.

## Partial is a state, not a failure

A packet may be useful before every requested record arrives, but it must never look complete.
Sixty Days renders exact reasons beside supporting items and keeps missing records visible in the
HTML and PDF. The PDF is marked draft and not submitted.

Current FEMA guidance instructs applicants to identify submitted pages with application and disaster
references. The draft repeats validated synthetic references in every footer and asks the applicant
to verify them. The public API rejects real-looking identifiers and accepts only explicit demo
prefixes.

Evidence-photo screening is equally narrow. It may say that a close frame lacks context and suggest
a wider retake. It does not value damage, authenticate a photo, determine legal sufficiency, or
predict agency acceptance. Two recorded image calls score 6 of 6 observable decisions against
adjacent truth.

## Three additional Google models, three bounded jobs

Gemma 4 reviews already-pattern-redacted text for remaining person-name spans. Gemini 3.1 Flash
Image creates an optional abstract first-use illustration. Veo 3.1 Fast creates a four-second motion
briefing.

The onboarding media contains no case identifiers, damage inference, legal conclusion, or approval
symbol. It never becomes evidence, never appears in a packet, and never autoplays. The public
provenance manifest records each prompt, exact model ID, location, byte count, and SHA-256 hash.

The models serve comprehension and privacy without gaining authority over the applicant's case.

## Shared substrate, substantially different work

Sixty Days and Day Three reuse the same reviewed durable spine for runs, wakes, claims, redaction,
verification, tracing, and Firestore adapters. The infrastructure reuse and shared production
scheduler are disclosed in both repositories.

Sixty Days has its own disaster-letter reader, deadline and requirement router, evidence-screening
workflow, request preparation, partial-safe PDF builder, FEMA-oriented conformance, synthetic case
fixtures, applicant boundary, repository, Cloud Run service, interface, and 24-step acceptance flow.
Day Three has none of those domain modules.

The two projects share infrastructure primitives. They do not claim separate infrastructure stacks,
and they do not solve the same user problem.

## Reproduce and inspect it

The public repository contains the architecture SVG and Mermaid source, local and cloud spin-up
instructions, truth-adjacent recordings, 205 standalone tests, a 24-step live acceptance flow,
accessibility checks, public conformance evidence, and the 10-clause shared-substrate exit test.

Live product: https://sixty-days-109051079423.us-central1.run.app

Judge evidence: https://sixty-days-109051079423.us-central1.run.app/judges

Public repository: https://github.com/usv240/sixty-days

Demo video: ADD PUBLIC YOUTUBE OR VIMEO URL BEFORE PUBLISHING

This project was built during the contest period with AI coding assistants, synthetic data, and no
government endorsement.
