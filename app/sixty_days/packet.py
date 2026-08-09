"""Build a reviewable draft appeal packet from verified letter quotes and screened evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from spine.verify import (
    Claim,
    ClaimKind,
    RejectionCode,
    Result,
    SourceRef,
    Verdict,
    Verifier,
    normalise,
)


class DecisionLetterVerifier:
    """Adds the Sixty Days rule the generic source-existence verifier cannot know.

    A system-authored regulatory sentence must reproduce the decision letter's exact words.
    A plausible paraphrase is still rejected. Applicant-authored narrative is labelled separately
    and is never presented as a system claim.
    """

    def __init__(self, artifact_id: str, letter_quotes: list[str]) -> None:
        self._quotes = letter_quotes
        self._core = Verifier(artifacts={artifact_id: "\n".join(letter_quotes)})

    def verify(self, claim: Claim) -> Result:
        if claim.kind is ClaimKind.REGULATORY:
            text = normalise(claim.text)
            if not any(normalise(quote) in text for quote in self._quotes):
                return Result(
                    claim.id,
                    Verdict.REJECTED,
                    RejectionCode.QUOTE_NOT_FOUND,
                    "Decision-letter statements must reproduce the letter's exact words.",
                )
        return self._core.verify(claim)


@dataclass(frozen=True)
class PacketEvidence:
    requirement_key: str
    title: str
    artifact_id: str
    decision: str
    guidance: str
    fixture: str = ""


@dataclass
class AppealPacket:
    case_id: str
    applicant_ref: str
    deadline: str
    status: str
    applicant_statement: str
    verified_statements: list[str] = field(default_factory=list)
    evidence: list[PacketEvidence] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "applicant_ref": self.applicant_ref,
            "deadline": self.deadline,
            "status": self.status,
            "verified_statements": self.verified_statements,
            "evidence": [item.__dict__ for item in self.evidence],
            "missing": self.missing,
            "safety": "Draft only. The applicant reviews, signs, and submits it.",
        }


class PacketBuilder:
    def build(self, case: dict[str, Any], applicant_statement: str = "") -> AppealPacket:
        case_id = str(case["case_id"])
        quotes = [
            str(item["quoted_text"])
            for item in case.get("deficiencies", [])
            if item.get("quoted_text")
        ]
        artifact_id = f"decision_{case_id}"
        verifier = DecisionLetterVerifier(artifact_id, quotes)
        verified_statements: list[str] = []
        for index, quote in enumerate(quotes, start=1):
            text = f'Your decision letter states: "{quote}"'
            claim = Claim(
                id=f"{case_id}:letter:{index}",
                text=text,
                kind=ClaimKind.REGULATORY,
                source_refs=(SourceRef(artifact_id, quote, f"reason {index}"),),
            )
            result = verifier.verify(claim)
            if not result.accepted:
                raise ValueError(f"packet claim was not grounded: {result.reason}")
            verified_statements.append(text)

        evidence_by_key = {
            str(item["requirement_key"]): item
            for item in case.get("evidence", [])
            if item.get("decision") == "ready_for_review"
        }
        evidence: list[PacketEvidence] = []
        missing: list[str] = []
        for requirement in case.get("requirements", []):
            key = str(requirement["key"])
            found = evidence_by_key.get(key)
            if found is None:
                missing.append(str(requirement["title"]))
                continue
            evidence.append(
                PacketEvidence(
                    requirement_key=key,
                    title=str(requirement["title"]),
                    artifact_id=str(found["artifact_id"]),
                    decision=str(found["decision"]),
                    guidance=str(found["guidance"]),
                    fixture=str(found.get("fixture", "")),
                )
            )
        if not applicant_statement.strip():
            missing.append("Applicant's own explanation of why the decision should be reconsidered")
        status = "draft_ready_for_applicant" if not missing else "partial_draft"
        return AppealPacket(
            case_id=case_id,
            applicant_ref=str(case.get("applicant_ref", "applicant")),
            deadline=str(case["deadline"]),
            status=status,
            applicant_statement=applicant_statement.strip(),
            verified_statements=verified_statements,
            evidence=evidence,
            missing=missing,
        )


class PacketRenderer:
    def render(
        self,
        packet: AppealPacket,
        image_paths: dict[str, Path] | None = None,
    ) -> bytes:
        output = BytesIO()
        doc = SimpleDocTemplate(
            output,
            pagesize=letter,
            rightMargin=0.7 * inch,
            leftMargin=0.7 * inch,
            topMargin=0.65 * inch,
            bottomMargin=0.65 * inch,
            title=f"Draft appeal packet - {packet.case_id}",
            author="Sixty Days",
        )
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name="PacketTitle", parent=styles["Title"], alignment=TA_CENTER,
            textColor=colors.HexColor("#17324d"), spaceAfter=12,
        ))
        styles.add(ParagraphStyle(
            name="Safety", parent=styles["BodyText"], textColor=colors.HexColor("#7a2e12"),
            backColor=colors.HexColor("#fff3e8"), borderPadding=8, spaceAfter=12,
        ))
        story = [
            Paragraph("DRAFT APPEAL PACKET", styles["PacketTitle"]),
            Paragraph(
                "Applicant review required. This optional organizing draft is not an agency form, "
                "has not been submitted, and is not legal advice.",
                styles["Safety"],
            ),
            Table(
                [
                    ["Case reference", packet.applicant_ref],
                    ["Appeal deadline", packet.deadline],
                    ["Packet status", packet.status.replace("_", " ")],
                ],
                colWidths=[1.55 * inch, 4.8 * inch],
                style=TableStyle([
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9aa8b5")),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef3f7")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("PADDING", (0, 0), (-1, -1), 6),
                ]),
            ),
            Spacer(1, 14),
            Paragraph("Request for review", styles["Heading2"]),
            Paragraph(
                "I am asking for review of the decision identified in my decision letter.",
                styles["BodyText"],
            ),
        ]
        for statement in packet.verified_statements:
            story.append(Paragraph(escape(statement), styles["BodyText"]))
        story.extend([
            Spacer(1, 8),
            Paragraph("Applicant statement", styles["Heading2"]),
            Paragraph(
                escape(packet.applicant_statement) or
                "[Applicant: add your own explanation before signing or sending this draft.]",
                styles["BodyText"],
            ),
            Spacer(1, 8),
            Paragraph("Evidence index", styles["Heading2"]),
        ])
        if packet.evidence:
            rows = [["Item", "Screening status", "Artifact"]]
            rows.extend([
                [item.title, "Ready for applicant review", item.artifact_id]
                for item in packet.evidence
            ])
            story.append(Table(
                rows,
                colWidths=[3.0 * inch, 2.1 * inch, 1.25 * inch],
                repeatRows=1,
                style=TableStyle([
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9aa8b5")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17324d")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("PADDING", (0, 0), (-1, -1), 5),
                ]),
            ))
        else:
            story.append(Paragraph("No evidence has passed screening yet.", styles["BodyText"]))

        story.extend([Spacer(1, 10), Paragraph("Items still missing", styles["Heading2"])])
        if packet.missing:
            for item in packet.missing:
                story.append(Paragraph(f"- {escape(item)}", styles["BodyText"]))
        else:
            story.append(Paragraph("None listed. The applicant must still review every page.", styles["BodyText"]))

        for item in packet.evidence:
            path = (image_paths or {}).get(item.artifact_id)
            if path is None or not path.exists():
                continue
            story.extend([PageBreak(), Paragraph(escape(item.title), styles["Heading2"])])
            image = Image(str(path))
            scale = min(
                (6.6 * inch) / image.imageWidth,
                (8.2 * inch) / image.imageHeight,
                1.0,
            )
            image.drawWidth = image.imageWidth * scale
            image.drawHeight = image.imageHeight * scale
            story.append(image)
            story.append(Paragraph(
                "Synthetic evidence fixture - screening demonstration only.",
                styles["Safety"],
            ))

        def footer(canvas, _doc):
            canvas.saveState()
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(colors.HexColor("#52606d"))
            canvas.drawString(0.7 * inch, 0.35 * inch, "Draft only - applicant review and submission required")
            canvas.drawRightString(7.8 * inch, 0.35 * inch, f"Page {canvas.getPageNumber()}")
            canvas.restoreState()

        doc.build(story, onFirstPage=footer, onLaterPages=footer)
        return output.getvalue()
