from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from sixty_days.packet import DecisionLetterVerifier, PacketBuilder, PacketRenderer
from spine.verify import Claim, ClaimKind, SourceRef


CASE = {
    "case_id": "case_demo",
    "applicant_ref": "DEMO-APPLICANT_1",
    "disaster_ref": "DR-DEMO",
    "deadline": "2026-09-30",
    "deficiencies": [{
        "kind": "damage_evidence",
        "plain_language": "More damage evidence is needed.",
        "quoted_text": "We could not verify the reported disaster damage.",
    }],
    "requirements": [{
        "key": "photo_wide",
        "title": "A wide photo of the damaged room",
        "source": "applicant_only",
    }],
    "evidence": [{
        "requirement_key": "photo_wide",
        "artifact_id": "ev_good",
        "decision": "ready_for_review",
        "guidance": "Review it.",
        "fixture": "damage_wide_good",
    }],
}


def test_regulatory_paraphrase_is_rejected_even_when_it_cites_a_real_quote():
    quote = CASE["deficiencies"][0]["quoted_text"]
    verifier = DecisionLetterVerifier("decision", [quote])
    result = verifier.verify(Claim(
        id="bad",
        text="FEMA requires proof of damage.",
        kind=ClaimKind.REGULATORY,
        source_refs=(SourceRef("decision", quote),),
    ))
    assert not result.accepted
    assert "exact words" in result.reason


def test_packet_uses_exact_letter_words_and_ready_evidence():
    packet = PacketBuilder().build(CASE, "The repair estimate and photos show the damaged room.")
    assert packet.status == "draft_ready_for_applicant"
    assert CASE["deficiencies"][0]["quoted_text"] in packet.verified_statements[0]
    assert [item.artifact_id for item in packet.evidence] == ["ev_good"]
    assert packet.missing == []


def test_partial_packet_lists_missing_evidence_and_applicant_statement():
    partial = {**CASE, "evidence": []}
    packet = PacketBuilder().build(partial)
    assert packet.status == "partial_draft"
    assert "A wide photo of the damaged room" in packet.missing
    assert any("Applicant's own explanation" in item for item in packet.missing)


def test_pdf_is_parseable_labeled_draft_and_page_numbered():
    packet = PacketBuilder().build(CASE, "Please review the attached evidence.")
    image = Path(__file__).resolve().parents[1] / "fixtures" / "evidence_scans" / "damage_wide_good.png"
    raw = PacketRenderer().render(packet, {"ev_good": image})
    reader = PdfReader(BytesIO(raw))
    page_texts = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(page_texts)
    assert raw.startswith(b"%PDF")
    assert "DRAFT APPEAL PACKET" in text
    assert "has not been submitted" in text
    assert "not an agency form" in text
    assert "Verify the application and disaster references" in text
    assert "Ready for applicant review" in text
    assert "Page 1" in text
    assert len(page_texts) >= 2
    assert all("Application DEMO-APPLICANT_1 | Disaster DR-DEMO" in page for page in page_texts)


def test_applicant_markup_is_rendered_as_text_not_reportlab_markup():
    packet = PacketBuilder().build(CASE, "Water reached <b>two feet</b> & damaged the wall.")
    raw = PacketRenderer().render(packet)
    text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(raw)).pages)
    assert "<b>two feet</b>" in text
    assert "& damaged" in text
