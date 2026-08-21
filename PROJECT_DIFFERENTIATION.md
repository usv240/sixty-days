# What is original here, and what was reused

This page exists because the contest rules require two disclosures: that the project was newly
created during the submission period, and that any pre-existing code incorporated into it is
declared. Both are answered below without asking a reader to take anything on trust.

## The reusable substrate, and where its boundary is

`app/spine/` is a general-purpose runtime substrate: an injectable clock, durable run state, a wake
scheduler with lease-based claiming and dead-lettering, a redaction gate, an untrusted-input
quarantine, and a claim verifier. It was written during the contest period and is deliberately
domain-free. Nothing in it knows what a disaster-assistance appeal is.

It is copied into this repository rather than imported as a package. That is a deliberate trade:
a judge can clone one repository, run one test suite, and read every line that executes, without
resolving a private dependency. The cost is duplication, and this page is where that cost is
declared rather than hidden.

The boundary is checkable rather than asserted:

- `POST /exit-test` runs the substrate's ten-stage acceptance test against the deployed service and
  returns a structured report.
- `app/tests/test_submission_independence.py` fails the build if this repository references a
  sibling project by name.
- Every domain concept — letters, deadlines, evidence routing, packets, appeal wakes — lives in
  `app/sixty_days/`, which the substrate never imports.

## What is specific to Sixty Days

None of the following exists in the substrate, and none of it was adapted from other work:

| Module | What it does that is unique to this problem |
|---|---|
| `sixty_days/reader.py` | Transcribes a determination letter and discards any reason whose exact words are not present in the transcription. |
| `sixty_days/deadline.py` | Derives the appeal window from the letter's own printed date, registers the day-3 through day-58 ladder, and refuses to extend past the sixty-day safeguard. |
| `sixty_days/evidence.py` | Screens observable photo framing and legibility, and can only return retake, manual review, or ready for applicant review. |
| `sixty_days/outreach.py` | Prepares a third-party records request with blanks and registers a no-reply check. It has no send path. |
| `sixty_days/packet.py` | Builds a partial-safe draft packet that lists every missing item instead of implying completeness. |
| `sixty_days/wake_actions.py` | Executes a due wake as one typed, idempotent case action, including the packet safeguard that actually builds a snapshot. |
| `sixty_days/store.py` | Persists structured case state while deliberately omitting raw letters, image bytes, transcriptions, and applicant free text. |

The research that shaped these decisions, the sources behind each guardrail, and the claims that
were rejected as unsupported are recorded in
[docs/research-traceability.md](docs/research-traceability.md).

## Shared infrastructure, stated plainly

The substrate is deployed more than once inside one Google Cloud project, and those deployments
share a Firestore database. That sharing is a real architectural fact with a real failure mode, so
it is handled rather than glossed:

Wakes from every deployment live in one collection, and claiming a wake is a compare-and-swap. A
worker that claims a wake it has no handler for still *completes* it, and a wake fires once — so a
neighbouring worker scanning the same collection does not duplicate work, it permanently retires
another service's safeguard, with no error raised anywhere.

Sixty Days therefore claims only the projects it can execute (`sixty-days` and `sixty-days-beta`),
its own `sixty-days-wake-scan` Cloud Scheduler job drives its worker, and that worker route rejects
anonymous callers. The rule is enforced in `spine/wake_ownership.py` and pinned by
`app/tests/test_wake_ownership.py`, which was written after the unbounded shared scanner was found
claiming this project's wakes.

## Disclosure

Built during the contest period with AI coding assistants. The shared substrate was developed during
the same period and copied into this standalone repository. All demonstration data is synthetic. No
government agency endorses this project, and the generated packet has no official status.
