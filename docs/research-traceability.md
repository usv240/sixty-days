# Sixty Days research traceability

**Last source review:** August 9, 2026

Sixty Days operates near a legal and administrative process. This ledger distinguishes official
FEMA instructions from product choices, historical problem context, and executable product proof.
The application organizes work; it does not interpret the law, decide eligibility, or submit.

## Source hierarchy

1. Current FEMA Individual Assistance guidance for applicant-facing timing and documentation.
2. Official FEMA fact sheets for examples of ownership, occupancy, insurance, and appeal records.
3. GAO findings for clearly dated historical process context.
4. The applicant's own decision letter for case-specific reasons and requested documents.

The decision letter always outranks the generic catalogue. If its quoted reason does not map safely,
the workflow stops for caseworker review rather than inventing a document request.

## Source-to-decision matrix

| Source | Verified finding used | Product decision | Limit preserved |
|---|---|---|---|
| [FEMA Individual Assistance appeals quick reference](https://www.fema.gov/sites/default/files/documents/fema_ia-quick-reference_appeals.pdf) | Current guidance describes the 60-day window, supporting-document examples, and an optional appeal form or letter. | Register the deadline ladder at intake and keep the generated PDF optional. | The product neither files nor calls its PDF an official form. |
| [FEMA, 8 Tips for Appealing a Decision](https://www.fema.gov/fact-sheet/8-tips-appealing-femas-decision-1) | The letter explains the reason and documents relevant to that decision. | Every requirement begins with an exact verified quote from the synthetic letter. | Generic routing cannot override the letter. |
| [FEMA, Verifying Home Ownership or Occupancy](https://www.fema.gov/fact-sheet/verifying-home-ownership-or-occupancy) | FEMA lists multiple ownership and occupancy records and date context, including alternatives to automated public-record matching. | Show multiple examples instead of prescribing one rigid record. | No listed document is called sufficient or outcome-determinative. |
| [FEMA, Help for Survivors with Insurance](https://www.fema.gov/sites/default/files/documents/fema_insurance_qrg_20241010.pdf) | Insurance documentation may include settlement information, a denial, or policy evidence of excluded or absent coverage. | Request those records; remove the unsupported equivalence between insurer documentation and a self-authored statement. | The applicant sends the request; Sixty Days does not contact an insurer. |
| [FEMA IHP application, eligibility, registration, and appeals](https://www.fema.gov/fact-sheet/fema-individuals-and-households-program-application-eligibility-registration-and-appeals) | The September 2025 explainer instructs applicants to place application and disaster numbers on every submitted page. | Repeat validated synthetic application and disaster references in every PDF footer and tell the applicant to verify them. | The API accepts only explicit demo-prefixed references; the draft is not submitted. |
| [Texas Law Help, Disaster Manual Section 2: Handling a FEMA Appeal](https://texaslawhelp.org/article/disaster-manual-section-2-fema-individual-and-households-program-handling-a-fema-appeal-for-a) | Written for volunteer lawyers, not survivors: "This resource is meant for volunteer lawyers." It states the burden directly — applicants, not FEMA, collect the evidence — and that "the applicant must get a repair estimate. Without a repair estimate, FEMA will likely deny the applicant immediately." | Confirms the workflow's central premise from people who do this work: the collecting is the applicant's job, and the repair estimate is load-bearing rather than optional. | Practitioner description of the process, not a claim about this product. |
| [Advocates for Disaster Justice, FEMA Appeals FAQ](https://www.advocatesfordisasterjustice.org/femaappealsfaqs/) (with Pro Bono Net, Lone Star Legal Aid, NLADA, and the ABA Standing Committee on Pro Bono) | Lists the records an appeal carries — the decision letter, the insurance policy and insurer correspondence, contractor estimates and receipts, inspection reports and photographs — and requires that third-party documents include "the third party's contact information so FEMA can verify it." | The "who holds what" routing is checked against a legal-aid coalition's own list rather than inferred, and each route names the holder because FEMA expects the holder to be nameable. | The list is the coalition's; nothing here is called sufficient for any applicant. |
| [GAO-20-503](https://www.gao.gov/products/gao-20-503) | From 2016-2018, roughly 1.7 million applicants were determined ineligible; cited reasons included insufficient damage and missing supporting evidence. | Motivate a quote-grounded evidence workflow. | Historical context only; not a current denial rate or appeal-success estimate. |

## Product evidence, separate from policy

- Four recorded Gemini letter calls grade 20/20 fields against adjacent synthetic truth.
- Two recorded evidence-image calls grade 6/6 observable checks.
- The standalone repository passes 365 tests.
- The deployed public acceptance flow passes 24/24.
- The shared resilience exit test passes 10/10.

Photo automation evaluates only observable framing and legibility. A "ready for applicant review"
result does not establish authenticity, sufficiency, causation, valuation, or agency acceptance.

## A source that corrected the product

The same practitioner manual states that "FEMA has a deadline for its appeals but generally accepts
appeals submitted after the deadline for a good cause reason."

That complicates this project's premise. The product is built around a hard 60-day window, and its
closing message told an applicant at day 61 only that the window had closed and no further reminders
were scheduled. Accurate, and read at the wrong moment it means "you have lost." A survivor who
believes that stops, and by this source they may have stopped for no reason.

The message now says the window has closed, that everything gathered stays available, and that a
late appeal can still be accepted for good cause and a disaster legal-aid service is worth asking
before treating it as over. The deadline ladder is unchanged: sixty days is still the target, being
early is still the point, and the agent still stops rather than nagging past the window. What
changed is that the last thing it says is no longer a dead end.

## Claims and designs deliberately rejected

- An Associated Press finding, reported in 2018, that missed deadlines were among the most common
  reasons FEMA denied appeals, worth over $100 million in a year — it is the closest thing found to
  direct evidence that the deadline itself defeats appeals, and the original could not be read
  behind a paywall. It is recorded here as unverified and is cited nowhere in the product. It also
  concerns public entities appealing to FEMA headquarters, not individual survivors, which is a
  different population from this one.
- A 5% appeal-rate statistic â€" source support did not survive audit.
- "A wide photo proves the damage" â€" current official examples emphasize case-specific supporting
  records; photos are optional context in this product.
- "A signed statement proves no insurance" â€" removed from the insurer route because the reviewed
  guide instead identifies settlement, denial, and coverage documents.
- Autonomous insurer contact or appeal submission â€" no authority and no endpoint.
- Eligibility or outcome prediction â€" outside the product's role and evidence.
