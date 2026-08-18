"""The redaction gate: what stands between a document and the global model endpoint.

Why this exists, precisely. Storage and compute are pinned to us-central1 and enforced by
`spine/config.py`. But Gemini 3.x is served only from the `global` endpoint, so document text
must cross a boundary we do not control the geography of. The gate strips identifiers before
that happens, so what crosses is pseudonymised rather than personal.

Two layers, deliberately in this order:

1. **Deterministic patterns first.** Identifiers with reliable shapes: MRNs, SSNs, phone numbers,
   dates of birth, street addresses, email addresses. Regex catches these with certainty, and a
   certainty is worth more than a probability. This layer alone satisfies the gate in replay and
   test environments, and it is what the 165-test suite exercises.
2. **Gemma second, for what has no shape.** Person names mostly. `GemmaReviewer` sends the
   already-pattern-redacted text to Gemma on Vertex AI and asks only for spans to remove, never
   for a rewrite, so the reviewer cannot alter clinical content. In replay mode this layer serves
   recordings like every other model call.

The mapping from pseudonym to original value never leaves this module's store. Reasoning services
receive text with PERSON_1, MRN_1, DOB_1 in it and have no way back.

Fail closed: if the gate errors, the step fails. A document never proceeds to the model
unredacted because redaction was inconvenient.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Replacement:
    kind: str
    original: str
    pseudonym: str
    start: int
    end: int


@dataclass
class RedactionResult:
    text: str
    replacements: list[Replacement] = field(default_factory=list)

    @property
    def mapping(self) -> dict[str, str]:
        """pseudonym -> original. Stored separately from the text, never sent anywhere."""
        return {r.pseudonym: r.original for r in self.replacements}


class RedactionError(RuntimeError):
    """The gate failed. The calling step must fail with it, never proceed unredacted."""


# Order matters: more specific shapes first, so an SSN is not half-eaten by the phone pattern.
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("MRN", re.compile(r"\b(?:MRN|MR#|Medical Record(?: No\.?| Number)?)[:\s#]*([A-Z]?\d{5,10})\b", re.I)),    # Laboratory accession numbers link a specimen to a patient even when the name and MRN are
    # absent. Keep the label narrow so ordinary phrases such as "Laboratory Medicine" survive.
    ("ACCESSION", re.compile(
        r"\b(?:Accession(?: No\.?| Number| ID)?|Lab(?:oratory)? (?:ID|No\.?|Number))"
        r"[:\s#]*([A-Z0-9][A-Z0-9-]{3,24})\b",
        re.I,
    )),
    # No leading \b: a word boundary before "(" can never match, since both the preceding space
    # and the paren are non-word characters. (?<!\d) guards against eating the tail of a longer
    # number instead.
    ("PHONE", re.compile(r"(?<!\d)(?:\+1[\s.-]?)?(?:\(\d{3}\)\s?|\d{3}[\s.-])\d{3}[\s.-]\d{4}\b")),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")),
    ("DOB", re.compile(r"\b(?:DOB|Date of Birth|Born)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})", re.I)),
    ("ADDRESS", re.compile(r"\b\d{1,5}\s+(?:[A-Z][a-z]+\s){1,3}(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Boulevard|Blvd)\b\.?", re.I)),
    # Government benefit case numbers. FEMA prints a registration number on every determination
    # letter; it identifies the applicant as directly as a name does.
    ("CASE_REF", re.compile(
        r"\b(?:Registration|Application|Case|Claim|Reference)\s*(?:No\.?|Number|#|ID)?[:\s#]+"
        r"([A-Z0-9][A-Z0-9-]{3,19})\b",
        re.I,
    )),
    # Labeled person names.
    #
    # Two bugs lived here and both leaked real identifiers, found by auditing the Sixty Days
    # letter fixtures:
    #   1. The label list only knew clinical words, so "Applicant:" was never matched.
    #   2. The name shape required Titlecase, but government letters print names in ALL CAPS,
    #      so "Applicant: DEVON CARTER" matched nothing even once the label was added.
    # Single spaces only between name words: \s would match a newline and swallow the next label.
    # PO boxes: a mailing address with no street suffix for the ADDRESS pattern to anchor on.
    ("ADDRESS", re.compile(r"\bP\.?\s?O\.?\s?Box\s+\d+\b", re.I)),
    # Labeled person names.
    #
    # Boundary probing found three further leaks after the ALL-CAPS fix, all of them ordinary
    # real-world spellings:
    #   * hyphenated names   ("MARY-JANE OKONKWO")
    #   * apostrophes        ("SEAN O'BRIEN", including the typographic apostrophe)
    #   * a lowercase label  ("applicant:" as typed in an email or a scan transcription)
    # The label is matched case-insensitively via a scoped group, but the *name* stays
    # case-sensitive on purpose: making the whole pattern IGNORECASE would let the all-caps
    # alternative match ordinary lowercase prose and redact half the letter.
    ("PERSON", re.compile(
        r"\b(?i:Patient(?: Name)?|Applicant(?: Name)?|Recipient|Claimant|Name)[: ]+"
        r"((?:[A-Z][a-z'’-]+|[A-Z][A-Z'’-]+)"
        r"(?: (?:[A-Z][a-z'’-]+|[A-Z][A-Z'’-]+)){1,3})"
    )),
)


class NameReviewer(ABC):
    """Second layer: finds person names the patterns cannot. Returns spans, never rewrites."""

    @abstractmethod
    def find_names(self, text: str) -> list[str]: ...


class NullReviewer(NameReviewer):
    """Pattern layer only. Used in unit tests and anywhere a model is unavailable."""

    def find_names(self, text: str) -> list[str]:
        return []


class ReplayReviewer(NameReviewer):
    """Serves a recorded Gemma response, so rehearsal costs nothing."""

    def __init__(self, names: list[str]) -> None:
        self._names = names
        self.calls = 0

    def find_names(self, text: str) -> list[str]:
        self.calls += 1
        return [n for n in self._names if n in text]


class GemmaReviewer(NameReviewer):
    """The real second layer: Gemma on Vertex AI.

    Asked one narrow question: list person names appearing in this text. It is given text the
    pattern layer has already cleaned, and its answer is used only to remove spans. It cannot
    inject, rewrite, or embellish, because we never use its prose.
    """

    PROMPT = (
        "List every person name that appears in the following text. Reply with a JSON array of "
        "strings, nothing else. If there are none, reply []. Do not include organisation names, "
        "drug names, or organism names.\n\nText:\n"
    )

    # Verified 2026-08-08: Gemma is served through Model as a Service. The bare `gemma3` /
    # `gemma4` publisher paths 404; only the -maas id is callable, and only from `global`.
    DEFAULT_MODEL = "gemma-4-26b-a4b-it-maas"

    def __init__(
        self, project: str, location: str = "global", model: str = DEFAULT_MODEL
    ) -> None:
        self._project = project
        self._location = location
        self._model = model

    def find_names(self, text: str) -> list[str]:
        from google import genai
        from google.genai import types

        client = genai.Client(vertexai=True, project=self._project, location=self._location)
        try:
            response = client.models.generate_content(
                model=self._model,
                contents=self.PROMPT + text,
                config=types.GenerateContentConfig(temperature=0.0),
            )
            raw = (response.text or "[]").strip()
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            names = json.loads(raw)
        except Exception as exc:  # noqa: BLE001 - converted to fail-closed
            raise RedactionError(f"name review failed, refusing to proceed unredacted: {exc}") from exc
        if not isinstance(names, list):
            raise RedactionError("name reviewer returned a non-list, refusing to proceed")
        return [n for n in names if isinstance(n, str) and 1 < len(n) < 80]


class Redactor:
    def __init__(self, reviewer: NameReviewer | None = None) -> None:
        self._reviewer = reviewer or NullReviewer()

    def redact(self, text: str) -> RedactionResult:
        replacements: list[Replacement] = []
        counters: dict[str, int] = {}
        out = text

        def substitute(kind: str, match_text: str, span: tuple[int, int]) -> str:
            counters[kind] = counters.get(kind, 0) + 1
            pseudonym = f"{kind}_{counters[kind]}"
            replacements.append(
                Replacement(kind=kind, original=match_text, pseudonym=pseudonym,
                            start=span[0], end=span[1])
            )
            return pseudonym

        # Layer 1: deterministic patterns.
        for kind, pattern in _PATTERNS:
            def repl(match: re.Match[str], kind: str = kind) -> str:
                # For labeled patterns, keep the label and replace only the captured value.
                if match.groups():
                    value = match.group(1)
                    prefix = match.group(0)[: match.start(1) - match.start(0)]
                    return prefix + substitute(kind, value, match.span(1))
                return substitute(kind, match.group(0), match.span(0))

            out = pattern.sub(repl, out)

        # Layer 2: names with no shape.
        for name in self._reviewer.find_names(out):
            if name in out:
                counters["PERSON"] = counters.get("PERSON", 0) + 1
                pseudonym = f"PERSON_{counters['PERSON']}"
                replacements.append(
                    Replacement(kind="PERSON", original=name, pseudonym=pseudonym, start=-1, end=-1)
                )
                out = out.replace(name, pseudonym)

        return RedactionResult(text=out, replacements=replacements)
