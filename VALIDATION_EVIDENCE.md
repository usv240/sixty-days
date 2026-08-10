# Sixty Days validation evidence

**Reviewed:** August 9, 2026

This dossier is the substitute used when applicant, caseworker, or legal-aid access is not available
during a hackathon. It is not a usability study, legal review, or government validation. It combines
current official guidance, historical context, adversarial tests, recorded model fixtures, live
acceptance checks, and explicit limits.

## What each evidence layer can establish

| Evidence | What it can establish | What it cannot establish |
|---|---|---|
| Current FEMA guidance | The documented appeal process, timing, and record examples | Eligibility, legal interpretation, or acceptance |
| GAO historical analysis | Documented historical scale and process friction | A current denial rate or appeal-success rate |
| Recorded model calls with adjacent truth | Behavior on committed synthetic fixtures | Accuracy across all decision letters and evidence |
| Unit and integration tests | Defined safety and workflow invariants hold under tested conditions | Real-world applicant adoption |
| Public acceptance and exit tests | The deployed workflow and failure recovery are executable | Government production readiness |
| Accessibility checks | Token contrast and coded interface contracts pass | A human usability study |

## Research to implementation trace

| Source | Product decision | Executable or visible evidence |
|---|---|---|
| [FEMA Individual Assistance Appeals Quick Reference](https://www.fema.gov/sites/default/files/documents/fema_ia-quick-reference_appeals.pdf) | Register a 60-day ladder and keep an appeal letter or form optional | tests/test_deadline.py; partial draft labels |
| [FEMA 8 Tips for Appealing a Decision](https://www.fema.gov/fact-sheet/8-tips-appealing-femas-decision-1) | Let the exact decision-letter reason control the evidence plan | test_reads_a_letter_and_keeps_the_source_quote |
| [FEMA ownership and occupancy guidance](https://www.fema.gov/fact-sheet/verifying-home-ownership-or-occupancy) | Offer multiple record examples instead of prescribing one document | Requirement router and conformance rows |
| [FEMA insurance guidance](https://www.fema.gov/sites/default/files/documents/fema_insurance_qrg_20241010.pdf) | Request settlement, denial, or coverage records without treating a self-authored statement as equivalent | Insurer request route |
| [FEMA IHP application and appeals explainer](https://www.fema.gov/fact-sheet/fema-individuals-and-households-program-application-eligibility-registration-and-appeals) | Repeat validated synthetic references in each PDF footer | test_partial_packet_pdf_is_grounded_draft_and_does_not_persist_statement |
| [GAO-20-503](https://www.gao.gov/products/gao-20-503) | Quantify historical process friction with the original 2016 to 2018 scope | Cited stat strip and explicit outcome disclaimer |

The full source hierarchy and rejected claims are in
[docs/research-traceability.md](docs/research-traceability.md).

## Product measurements

| Measurement | Current result | Reproduce |
|---|---:|---|
| Recorded Gemini letter extraction | 20 of 20 fields | python scripts/record_letters.py and adjacent report |
| Recorded evidence screening | 6 of 6 decisions | python scripts/record_evidence.py and adjacent report |
| Standalone test suite | 202 passed | python -m pytest -q |
| Public acceptance flow | 23 of 23 | python scripts/sixty_days_demo_flow.py with the public URL |
| Shared-substrate exit test | 10 of 10 | POST /exit-test with an empty JSON body |
| Accessibility gate | Pass in light and dark themes | python scripts/check_a11y.py |

These measurements describe committed synthetic fixtures and specified behavior. They are not
legal accuracy, eligibility, evidence sufficiency, or appeal-outcome measurements.

## Adversarial safety matrix

| Attack or failure | Required behavior | Regression evidence |
|---|---|---|
| Empty source quote | Reject as no source | test_rejects_a_source_reference_with_an_empty_quote |
| Whitespace-only quote | Reject as no source | test_rejects_a_whitespace_only_quote |
| Valid quote beside empty quote | Reject the claim | test_an_empty_quote_cannot_be_hidden_behind_a_valid_one |
| Regulatory paraphrase not supported by the letter | Reject | test_regulatory_paraphrase_is_rejected_even_when_it_cites_a_real_quote |
| Unsupported evidence requirement | Do not ask the model to guess | test_unsupported_requirement_never_gets_a_model_guess |
| Unknown visual observation | Route to manual review | test_unknown_model_observation_routes_to_manual_review |
| Wrong address on a legible record | Reject for mismatch | test_wrong_address_is_rejected_even_when_document_is_legible |
| Hyphenated or apostrophe-bearing name | Redact | test_ordinary_real_world_spellings_are_not_missed |
| Lowercase applicant label or PO box | Redact | test_ordinary_real_world_spellings_are_not_missed |
| Disaster-name prose | Preserve | test_the_gate_does_not_over_redact |
| Applicant markup in PDF text | Render as text, not markup | test_applicant_markup_is_rendered_as_text_not_reportlab_markup |
| Real-looking packet references | Reject | Public route contract tests |

## Deadline and resilience matrix

| Condition | Required behavior | Regression evidence |
|---|---|---|
| Case opened twice | Keep wake creation idempotent | test_reopening_after_a_restart_is_idempotent |
| Shorter printed deadline | Move the partial packet and final warning earlier | test_earlier_deadline_still_builds_a_partial_packet_and_warns_two_days_before |
| Later printed deadline | Do not extend beyond the 60-day safeguard | test_later_stated_deadline_does_not_extend_the_sixty_day_window |
| Third-party request near deadline | Cap the chase before the deadline | test_third_party_chase_never_lands_after_the_appeal_deadline |
| Two requirements created together | Preserve distinct wake IDs | test_two_third_party_requirements_do_not_collide |
| Two workers claim one wake | Exactly one claim succeeds | test_a_wake_is_claimed_by_exactly_one_worker |
| Crash after completed work | Resume without repeating completed work | test_resume_after_crash_does_not_repeat_completed_work |
| Repeated failure | Dead-letter instead of infinite loop | test_repeated_failure_dead_letters_rather_than_looping |
| Case closed | Mark remaining contacts cancelled without deleting them | test_close_marks_every_remaining_contact_cancelled |
| Partial evidence | Keep missing items visible | test_partial_packet_lists_missing_evidence_and_applicant_statement |

## Usability evidence without pretending it is user research

The project uses a first-time cognitive walkthrough rather than a claimed user study:

- Light mode is the default.
- The workflow is presented as Understand, Gather, Track, and Review.
- The default guided preset selects a complete synthetic path.
- Controls unlock only when their prerequisites exist.
- The close-photo failure automatically selects the wider comparison.
- "Ready for applicant review" is distinct from accepted, valid, or sufficient.
- Every external action remains applicant-controlled.
- Synthetic data, simulated time, and draft status are visible.
- The guided flow requires no credentials or terminal.
- Accessibility checks cover both themes.

An applicant or practitioner usability study remains future work.

## What remains unproven

- Legal accuracy or legal advice
- Eligibility, appeal success, or evidence sufficiency
- Usability with survivors under real disaster conditions
- External validity across agency letters and jurisdictions
- Evidence authenticity, causation, or damage valuation
- Government integration or endorsement
- Production use with real applicant information

See [PROJECT_DIFFERENTIATION.md](PROJECT_DIFFERENTIATION.md) for the evidence that this submission
is substantially different from Day Three despite shared infrastructure primitives.
