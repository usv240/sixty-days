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
applicant's authority. It quotes the letter's exact reason, sets eight reminders for itself, checks only whether an
evidence photo is readable, drafts the requests for the applicant to send, and builds a PDF that
still shows every gap. It never contacts a third party, gives legal advice, predicts
eligibility, or submits an appeal.

A Cloud Scheduler job wakes the deployed service every minute, and the site shows when it last
ran, so the autonomy is checkable rather than narrated.

Adversarial testing improved the core safety boundary. The Verifier rejects empty and
whitespace-only quotes, and one valid reference cannot launder an empty one.

Model Armor now screens for prompt injection in front of that deterministic layer. Measured on
the live service it blocked a direct injection and missed the same injection diluted inside a
long letter, which the deterministic quarantine caught. Publishing the miss is the point: a
screen whose failures are unknown cannot be relied on.

The console replays recorded model calls so judging is repeatable, and carries one button that
calls Gemini 3.5 Flash live and grades the answer against the same truth file, so the
integration is provable rather than claimed.

Current proof:

- 338 standalone tests
- 24 of 24 public acceptance checks
- 29 of 29 developer-API checks, including tenant isolation
- 33 of 33 responsive checks and 11 of 11 screen sizes
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
visibly partial. It never sends or submits. Proven by 338 tests and a 24 of 24 public flow.

Live: https://sixty-days-109051079423.us-central1.run.app

I created this post for the purposes of entering the All Things Agentic Hackathon.
#AllThingsAgenticHackathon
