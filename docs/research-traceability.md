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
| [GAO-20-503](https://www.gao.gov/products/gao-20-503) | From 2016-2018, roughly 1.7 million applicants were determined ineligible; cited reasons included insufficient damage and missing supporting evidence. | Motivate a quote-grounded evidence workflow. | Historical context only; not a current denial rate or appeal-success estimate. |

## Product evidence, separate from policy

- Four recorded Gemini letter calls grade 20/20 fields against adjacent synthetic truth.
- Two recorded evidence-image calls grade 6/6 observable checks.
- The standalone repository passes 202 tests.
- The deployed public acceptance flow passes 23/23.
- The shared resilience exit test passes 10/10.

Photo automation evaluates only observable framing and legibility. A “ready for applicant review”
result does not establish authenticity, sufficiency, causation, valuation, or agency acceptance.

## Claims and designs deliberately rejected

- A 5% appeal-rate statistic — source support did not survive audit.
- “A wide photo proves the damage” — current official examples emphasize case-specific supporting
  records; photos are optional context in this product.
- “A signed statement proves no insurance” — removed from the insurer route because the reviewed
  guide instead identifies settlement, denial, and coverage documents.
- Autonomous insurer contact or appeal submission — no authority and no endpoint.
- Eligibility or outcome prediction — outside the product's role and evidence.
