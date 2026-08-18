# Day Three and Sixty Days project differentiation

**Reviewed:** August 9, 2026

This document addresses the multiple-submission requirement directly. The two submissions reuse a
shared durable infrastructure library, but they solve different problems for different users, in
different categories, through different domain agents, data models, interfaces, safety boundaries,
conformance sources, repositories, services, and acceptance flows.

## What is intentionally shared

Both repositories contain a reviewed copy of the spine package:

- Clock abstraction and namespaced simulation state
- Durable runs, wakes, claims, leases, and idempotency
- Source-reference verification
- Untrusted-instruction quarantine
- Deterministic redaction and Gemma review
- Firestore adapters
- Trace and logging instrumentation
- Shared exit-test contract

The copies are byte-identical by design. Both deployed services use the same Firestore project and
the same production due-work scheduler. Neither submission claims a separate infrastructure stack
or per-agent runtime identity.

This is analogous to two products using the same internal platform library. Reusing tested
infrastructure reduces duplicated security and resilience logic.

## What is substantially different

| Dimension | Day Three | Sixty Days |
|---|---|---|
| Category | The Fortified Enterprise Fleet | The Taskmaster |
| Primary user | Small-hospital pharmacist | Disaster-assistance applicant |
| Operational friction | Antibiotic review can be missed after final microbiology evidence arrives | Appeal evidence and third-party records must be coordinated inside a short window |
| Input | Synthetic microbiology report scans and an antibiotic course | Synthetic decision letters and evidence images |
| Domain modules | Intake, isolate curator, antibiogram, Course Watch, reconciler, router, registry | Letter reader, deadline keeper, requirement router, evidence screen, request preparation, packet builder |
| Durable horizon | Five-week antibiotic-course ladder | Day-3 through day-58 appeal ladder and no-reply wakes |
| Data model | Isolates, susceptibility cells, courses, clinical review claims | Cases, deficiencies, requirements, requests, evidence status, packet metadata |
| Human authority | Licensed pharmacist reviews any recommendation | Applicant reviews and sends every request and decides what to submit |
| Forbidden actions | Prescribing, dosing, ordering, paging, chart mutation | Legal advice, eligibility prediction, third-party contact, appeal submission |
| Domain verification | Source-grounded susceptibility and recommendation claims | Exact decision-letter reasons, bounded evidence checks, partial-safe packets |
| Research basis | CDC stewardship guidance, CAH studies, low-isolate evidence, CLSI-oriented rules | FEMA appeal, ownership, occupancy, insurance, and page-identification guidance; GAO context |
| Known domain limit | First ingested isolate can differ from earliest collected when reports arrive out of order | No legal or agency validation; photo checks cannot establish sufficiency or authenticity |
| Public interface | Antibiogram and timed pharmacist-review console | Understand, Gather, Track, Review applicant console |
| Public acceptance | 18-step Day Three flow | 24-step Sixty Days flow |
| Deployment | day-three Cloud Run service and URL | sixty-days Cloud Run service and URL |
| Repository | github.com/usv240/day-three | github.com/usv240/sixty-days |

## Concrete repository evidence

Snapshot from the committed repositories:

| Surface | Day Three | Sixty Days |
|---|---:|---:|
| Project-specific domain package | 11 Python files, 1,733 lines | 8 Python files, 1,260 lines |
| Shared spine package | 11 Python files, 1,735 lines | 11 Python files, 1,735 lines |
| Test suite | 24 Python files, 2,622 lines | 20 Python files, 2,068 lines |
| Web surface | 5 files, 96,892 bytes | 4 files, 74,626 bytes |
| Standalone test result | 240 passed | 215 passed |

Line counts are descriptive evidence of separate implementation surfaces, not a quality score.

## Independent proof paths

A judge can evaluate either project without opening the other:

### Day Three

- Live: https://day-three-109051079423.us-central1.run.app
- Judges: https://day-three-109051079423.us-central1.run.app/judges
- Repository: https://github.com/usv240/day-three
- Acceptance script: app/scripts/demo_flow.py
- Validation dossier: VALIDATION_EVIDENCE.md

### Sixty Days

- Live: https://sixty-days-109051079423.us-central1.run.app
- Judges: https://sixty-days-109051079423.us-central1.run.app/judges
- Repository: https://github.com/usv240/sixty-days
- Acceptance script: app/scripts/sixty_days_demo_flow.py
- Validation dossier: VALIDATION_EVIDENCE.md

## Honest conclusion

The submissions share infrastructure primitives and cloud resources. They are not presented as two
independent stacks.

Their user problems, category fit, domain agents, state schemas, evidence rules, interfaces,
safety boundaries, research sources, demonstrations, and acceptance criteria are substantially
different. The shared spine makes their reliability story consistent without making their product
work the same.
