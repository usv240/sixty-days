# Sixty Days social copy

Replace the video placeholder before publishing.

## LinkedIn version

A disaster-assistance decision letter can start a 60-day appeal window while the records it requests
are still scattered across insurers, public offices, and a damaged home.

GAO reported that approximately 4.4 million applicants were referred to FEMA's Individuals and
Households Program from 2016 through 2018, and roughly 1.7 million were determined ineligible during
that historical period. Failure to submit supporting evidence was among the cited reasons. These are
historical process figures, not a current denial rate or a prediction of appeal success.

Source context: https://www.gao.gov/products/gao-20-503

Sixty Days is a deployed deadline keeper that carries the coordination burden without taking the
applicant's authority. It preserves the synthetic letter's exact reason, registers eight durable
wakes, checks only observable evidence framing, prepares applicant-controlled request drafts, and
builds a visibly partial PDF. It never contacts a third party, provides legal advice, predicts
eligibility, or submits an appeal.

Adversarial testing improved the core safety boundary. The Verifier now rejects empty and
whitespace-only quotes, and one valid reference cannot launder an empty one. Redaction tests now
cover hyphenated and apostrophe-bearing names, lowercase applicant labels, FEMA-style references,
street addresses, and PO boxes.

Current proof:

- 205 standalone tests
- 24 of 24 public acceptance checks
- 20 of 20 recorded letter fields
- 6 of 6 recorded evidence decisions
- 10 of 10 shared-substrate exit-test clauses
- Accessibility passing in light and dark themes

Built with Cloud Run, Firestore, Cloud Scheduler, Cloud Trace, Gemini 3.5 Flash, Gemma 4 MaaS,
Gemini 3.1 Flash Image, and Veo 3.1 Fast.

Live: https://sixty-days-109051079423.us-central1.run.app

Video: ADD PUBLIC VIDEO URL

Code: https://github.com/usv240/sixty-days

I created this post for the purposes of entering the All Things Agentic Hackathon.

#AllThingsAgenticHackathon

## Compact version

Sixty Days is a deployed deadline agent for synthetic disaster-assistance appeals. It quotes the
letter, registers eight wakes, prepares applicant-controlled requests, and keeps partial packets
visibly partial. It never sends or submits. Proven by 219 tests and a 24 of 24 public flow.

Live: https://sixty-days-109051079423.us-central1.run.app

I created this post for the purposes of entering the All Things Agentic Hackathon.
#AllThingsAgenticHackathon
