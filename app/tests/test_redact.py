"""Redaction gate tests.

The property under test: identifiers do not cross the model boundary, clinical content does, and
the gate fails closed rather than proceeding unredacted.
"""

import pytest

from spine.redact import (
    NullReviewer,
    RedactionError,
    Redactor,
    ReplayReviewer,
)

REPORT = """MERCY CRITICAL ACCESS HOSPITAL
Patient: Harold Jennings      MRN: 8842910
Accession: 26-004182
DOB: 04/12/1951               Phone: (406) 555-0173
Address: 118 Cedar Lane
Email: h.jennings51@example.com
SSN: 521-44-9083

Organism: Escherichia coli
CEFTRIAXONE          <=1        S
CIPROFLOXACIN         >2        R
"""


@pytest.fixture
def redactor():
    return Redactor(NullReviewer())


def test_all_identifier_kinds_are_removed(redactor):
    result = redactor.redact(REPORT)
    for identifier in (
        "Harold Jennings", "8842910", "26-004182", "04/12/1951", "(406) 555-0173",
        "118 Cedar Lane", "h.jennings51@example.com", "521-44-9083",
    ):
        assert identifier not in result.text, f"{identifier!r} leaked through the gate"


def test_clinical_content_is_untouched(redactor):
    """The gate removes who the patient is, never what the lab found."""
    result = redactor.redact(REPORT)
    assert "Escherichia coli" in result.text
    assert "CEFTRIAXONE          <=1        S" in result.text
    assert "CIPROFLOXACIN         >2        R" in result.text


def test_pseudonyms_are_stable_and_labeled(redactor):
    result = redactor.redact(REPORT)
    assert "PERSON_1" in result.text
    assert "MRN_1" in result.text
    assert "ACCESSION_1" in result.text
    assert "SSN_1" in result.text
    assert "DOB_1" in result.text


def test_labels_survive_so_the_document_stays_readable(redactor):
    """A model still needs to know a field was an MRN; it must not know which."""
    result = redactor.redact(REPORT)
    assert "MRN: MRN_1" in result.text
    assert "Patient: PERSON_1" in result.text


def test_the_mapping_recovers_every_original(redactor):
    result = redactor.redact(REPORT)
    mapping = result.mapping
    assert mapping["PERSON_1"] == "Harold Jennings"
    assert mapping["MRN_1"] == "8842910"
    assert mapping["SSN_1"] == "521-44-9083"


def test_repeated_identifiers_get_distinct_pseudonyms(redactor):
    text = "Patient: Ann Berg\nPatient: Joe Ruiz\nSSN: 111-22-3333\nSSN: 444-55-6666"
    result = redactor.redact(text)
    assert "PERSON_1" in result.text and "PERSON_2" in result.text
    assert result.mapping["SSN_1"] == "111-22-3333"
    assert result.mapping["SSN_2"] == "444-55-6666"


def test_all_caps_names_are_caught(redactor):
    """Regression. Government letters print names in caps; the pattern required Titlecase, so
    'Applicant: DEVON CARTER' matched nothing and the name reached the model endpoint."""
    result = redactor.redact("Applicant: DEVON CARTER\nStatus: ineligible")
    assert "DEVON CARTER" not in result.text
    assert result.mapping["PERSON_1"] == "DEVON CARTER"


def test_benefit_labels_are_recognised_not_just_clinical_ones(redactor):
    """Regression. The label list only knew Patient and Name, so every FEMA letter leaked."""
    for label in ("Applicant", "Applicant Name", "Recipient", "Claimant"):
        result = redactor.redact(f"{label}: Mara Rivera")
        assert "Mara Rivera" not in result.text, f"{label} label leaked the name"


def test_case_reference_numbers_are_removed(redactor):
    """A FEMA registration number identifies the applicant as directly as their name."""
    result = redactor.redact("Registration: DEMO-7319\nDisaster: DR-4999")
    assert "DEMO-7319" not in result.text
    assert result.mapping["CASE_REF_1"] == "DEMO-7319"


def test_a_letter_with_no_street_address_still_redacts(redactor):
    """The audit that started this: one fixture reported zero redactions purely because it had
    no street address, which masked the fact that names and case numbers were leaking in all
    four letters."""
    letter = (
        "FEDERAL DISASTER ASSISTANCE\n"
        "Applicant: DEVON CARTER\n"
        "Registration: DEMO-7319\n"
        "We could not confirm that you lived at the damaged address.\n"
    )
    result = redactor.redact(letter)
    assert len(result.replacements) >= 2
    assert "DEVON CARTER" not in result.text
    assert "DEMO-7319" not in result.text
    # The reason for denial must survive: it is the whole product.
    assert "could not confirm that you lived" in result.text


@pytest.mark.parametrize(
    "text,identifier",
    [
        ("Applicant: MARY-JANE OKONKWO", "MARY-JANE OKONKWO"),
        ("Applicant: SEAN O'BRIEN", "SEAN O'BRIEN"),
        ("Applicant: SEAN O’BRIEN", "SEAN O’BRIEN"),
        ("applicant: Devon Carter", "Devon Carter"),
        ("Mailing: P.O. Box 4417", "P.O. Box 4417"),
        ("Mailing: PO Box 22", "PO Box 22"),
    ],
)
def test_ordinary_real_world_spellings_are_not_missed(redactor, text, identifier):
    """Regression from boundary probing. Every one of these leaked: the name class excluded
    hyphens and apostrophes, the label was case-sensitive, and a PO box has no street suffix
    for the address pattern to anchor on."""
    assert identifier not in redactor.redact(text).text


@pytest.mark.parametrize(
    "text",
    [
        "The organism Escherichia coli was isolated from urine.",
        "Name of disaster: SEVERE STORMS AND FLOODING",
        "CEFTRIAXONE          <=1        S",
    ],
)
def test_the_gate_does_not_over_redact(redactor, text):
    """Over-redaction is safer than under-redaction but still destroys the product: the reason
    for a denial and the susceptibility results are the whole output."""
    assert redactor.redact(text).text == text


def test_a_document_with_no_identifiers_passes_through_unchanged(redactor):
    text = "Organism: Klebsiella pneumoniae\nMEROPENEM  <=0.25  S"
    result = redactor.redact(text)
    assert result.text == text
    assert result.replacements == []


def test_the_reviewer_catches_unlabeled_names():
    """Layer 2: a name in running text has no shape a regex can trust."""
    text = "Culture discussed with Harold Jennings at bedside. Organism: E. coli."
    result = Redactor(ReplayReviewer(["Harold Jennings"])).redact(text)
    assert "Harold Jennings" not in result.text
    assert "PERSON_1" in result.text
    assert "E. coli" in result.text


def test_reviewer_names_not_present_are_ignored():
    result = Redactor(ReplayReviewer(["Nobody Here"])).redact("Organism: E. coli")
    assert result.replacements == []


def test_replay_reviewer_costs_are_visible():
    reviewer = ReplayReviewer([])
    redactor = Redactor(reviewer)
    for _ in range(5):
        redactor.redact("some text")
    assert reviewer.calls == 5


def test_a_failing_reviewer_fails_the_gate_closed():
    """If the gate errors, the step fails. Unredacted text never proceeds as a fallback."""

    class Broken(NullReviewer):
        def find_names(self, text):
            raise RedactionError("model unavailable")

    with pytest.raises(RedactionError):
        Redactor(Broken()).redact(REPORT)
