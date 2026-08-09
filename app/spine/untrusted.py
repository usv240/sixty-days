"""Handling documents written by someone other than the user.

All three projects ingest untrusted input. A scanned culture report, a photographed determination
letter and a 1958 drawing are all produced by a third party, and any of them could contain text
shaped like an instruction.

Rules.md line 88 names prompt injection and tool poisoning as guardrail categories for this
platform. This module is defence in depth, not the guarantee. **The guarantee is the Verifier**:
an injected instruction cannot produce an accepted claim, because a claim must quote source
material that supports it. This module reduces the chance an agent is misled in the first place,
and makes what was suppressed visible in the UI rather than silent.

Three rules:

1. Document text never enters the instruction channel. It is wrapped in an explicitly labelled
   block, and system prompts state that its contents are material to quote and analyse, never
   directions to follow.
2. A pre-flight scan quarantines instruction-shaped spans before any reasoning agent sees them.
3. Tools cannot be introduced at runtime, so no document can grant a capability. That rule lives
   in the tool registry, not here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class Threat(StrEnum):
    INSTRUCTION_OVERRIDE = "instruction_override"
    ROLE_INJECTION = "role_injection"
    OUTPUT_HIJACK = "output_hijack"
    TOOL_SOLICITATION = "tool_solicitation"
    EMBEDDED_URL = "embedded_url"


@dataclass(frozen=True)
class Quarantined:
    threat: Threat
    text: str
    start: int
    end: int
    explanation: str


# Each pattern carries a plain explanation, because the UI shows the user what was removed and
# why. Silent filtering would be worse than no filtering.
_PATTERNS: tuple[tuple[Threat, re.Pattern[str], str], ...] = (
    (
        Threat.INSTRUCTION_OVERRIDE,
        re.compile(
            r"(?i)\b(?:ignore|disregard|forget|override)\b[^.\n]{0,40}"
            r"\b(?:previous|prior|earlier|above|all)\b[^.\n]{0,30}"
            r"\b(?:instruction|instructions|prompt|prompts|rule|rules|context)\b"
        ),
        "Text telling a system to ignore its instructions. Documents describe facts; they do "
        "not issue orders.",
    ),
    (
        Threat.ROLE_INJECTION,
        re.compile(r"(?im)^\s*(?:system|assistant|user)\s*:|<\|im_(?:start|end)\|>"),
        "Text imitating a conversation role marker, which could be read as a new speaker.",
    ),
    (
        Threat.ROLE_INJECTION,
        re.compile(r"(?i)\byou are (?:now|a|an)\b[^.\n]{0,60}"),
        "Text attempting to reassign the reader's role.",
    ),
    (
        Threat.OUTPUT_HIJACK,
        re.compile(
            r"(?i)\b(?:respond|reply|answer|output|return|print)\b\s+"
            r"(?:only\s+)?(?:with|exactly|the following)\b[^.\n]{0,60}"
        ),
        "Text dictating what the output should be, rather than stating a fact.",
    ),
    (
        Threat.TOOL_SOLICITATION,
        re.compile(
            r"(?i)\b(?:call|invoke|execute|run|use)\b\s+(?:the\s+)?"
            r"(?:tool|function|api|command|endpoint)\b[^.\n]{0,60}"
        ),
        "Text asking for a tool to be called. Tools are fixed at build time and cannot be "
        "introduced by a document.",
    ),
    (
        Threat.EMBEDDED_URL,
        re.compile(r"(?i)\bhttps?://[^\s<>\"']{4,}"),
        "A link embedded in a document. Links are recorded but never followed.",
    ),
)

# What replaces a quarantined span. Visible, so a reader can see something was removed.
REDACTION = "[quarantined]"


def scan(text: str) -> list[Quarantined]:
    """Find instruction-shaped spans. Does not modify the text."""
    found: list[Quarantined] = []
    claimed: list[tuple[int, int]] = []

    for threat, pattern, explanation in _PATTERNS:
        for match in pattern.finditer(text):
            start, end = match.span()
            if any(start < c_end and end > c_start for c_start, c_end in claimed):
                continue  # already covered by an earlier, higher priority pattern
            claimed.append((start, end))
            found.append(
                Quarantined(
                    threat=threat,
                    text=match.group(0).strip(),
                    start=start,
                    end=end,
                    explanation=explanation,
                )
            )

    return sorted(found, key=lambda q: q.start)


def sanitise(text: str) -> tuple[str, list[Quarantined]]:
    """Return the text with instruction-shaped spans replaced, plus what was removed.

    The run continues without the quarantined spans rather than failing, because a real scanned
    document can contain an unlucky phrase and refusing to process a patient's lab report would
    be a worse failure than removing a sentence.
    """
    spans = scan(text)
    if not spans:
        return text, []

    out: list[str] = []
    cursor = 0
    for span in spans:
        out.append(text[cursor : span.start])
        out.append(REDACTION)
        cursor = span.end
    out.append(text[cursor:])
    return "".join(out), spans


def wrap(artifact_id: str, text: str, origin: str = "scan") -> str:
    """Wrap document text for presentation to a model.

    The delimiter is explicit and the attributes name the source, so the surrounding system
    prompt can state without ambiguity that everything inside is material to be quoted, never
    directions to follow.
    """
    safe_id = re.sub(r"[^A-Za-z0-9_.:-]", "", artifact_id)
    safe_origin = re.sub(r"[^A-Za-z0-9_.:-]", "", origin)
    closing = re.compile(r"(?i)</?untrusted_document[^>]*>")
    body = closing.sub(REDACTION, text)
    return (
        f'<untrusted_document id="{safe_id}" origin="{safe_origin}">\n'
        f"{body}\n"
        f"</untrusted_document>"
    )


def prepare(artifact_id: str, text: str, origin: str = "scan") -> tuple[str, list[Quarantined]]:
    """The one call an ingesting agent makes. Sanitise, then wrap."""
    cleaned, spans = sanitise(text)
    return wrap(artifact_id, cleaned, origin), spans
