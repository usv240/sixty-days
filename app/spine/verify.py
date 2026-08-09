"""The Verifier: an adversarial gate between what an agent says and what a human sees.

The rule the whole system rests on: **a sentence is only rendered if a claim behind it was
accepted.** That turns hallucination containment from a paragraph in a write up into a property
of the system, and it is what makes the on camera rejection in every demo possible.

It also does a second job for free. Injected instructions hidden inside an untrusted document
cannot produce an accepted claim, because a claim must quote source material that supports it.
An agent that has been talked into a wrong conclusion still cannot get that conclusion rendered.
The hallucination defence and the prompt injection defence are the same mechanism.

Rules.md line 498 asks how the system recovers if a worker agent loops or returns a
hallucination. This module is the answer, and it is demonstrated rather than described.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum


class ClaimKind(StrEnum):
    SUSCEPTIBILITY = "susceptibility"  # this organism is susceptible to this drug
    GUIDELINE = "guideline"  # a clinical or regulatory guideline says X
    REGULATORY = "regulatory"  # a rule this jurisdiction imposes
    MEASUREMENT = "measurement"  # a number: a percentage, a count, a distance
    INFERENCE = "inference"  # derived from other claims, which must be named


class Verdict(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class RejectionCode(StrEnum):
    NO_SOURCE = "no_source"
    QUOTE_NOT_FOUND = "quote_not_found"
    CONTRADICTS_RECORD = "contradicts_record"
    UNGROUNDED_INFERENCE = "ungrounded_inference"
    NUMBER_NOT_IN_SOURCE = "number_not_in_source"
    UNKNOWN_ARTIFACT = "unknown_artifact"


@dataclass(frozen=True)
class SourceRef:
    artifact_id: str
    quoted_text: str
    locator: str = ""


@dataclass(frozen=True)
class Record:
    """An established structured fact, and what may not be asserted against it.

    Contradiction detection by string similarity is brittle and indefensible, so records are
    explicit instead. `forbids` names the assertions this fact rules out. A recorded penicillin
    allergy forbids calling penicillin safe. A recorded resistant result forbids calling that
    organism susceptible to that drug.

    In Day Three these come from structured patient data and finalised susceptibility results,
    not from prose, which is why the rule can be exact.
    """

    key: str
    value: str
    forbids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Claim:
    id: str
    text: str
    kind: ClaimKind
    source_refs: tuple[SourceRef, ...] = ()
    depends_on: tuple[str, ...] = ()  # required for INFERENCE


@dataclass(frozen=True)
class Result:
    claim_id: str
    verdict: Verdict
    code: RejectionCode | None = None
    reason: str = ""

    @property
    def accepted(self) -> bool:
        return self.verdict is Verdict.ACCEPTED


class CircuitBroken(RuntimeError):
    """Raised when one claim has been rejected too many times. A human is required."""


def normalise(text: str) -> str:
    """Collapse the noise that separates a quote from its source.

    Scanned lab reports contain runs of spaces, inconsistent case, and unicode dashes that differ
    from what a model reproduces. None of that should decide whether a quote is genuine, but a
    changed word should.
    """
    text = unicodedata.normalize("NFKD", text)
    text = text.replace("–", "-").replace("—", "-").replace("≤", "<=")
    text = re.sub(r"\s+", " ", text)
    return text.strip().casefold()


_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def numbers_in(text: str) -> list[str]:
    """Numbers a claim asserts. Trailing zeros normalised so 40 and 40.0 compare equal."""
    out = []
    for raw in _NUMBER.findall(text):
        value = float(raw)
        out.append(str(int(value)) if value.is_integer() else str(value))
    return out


class Verifier:
    """Checks claims against the artifacts and structured records they say they come from.

    `artifacts` maps artifact id to its full extracted text.
    `records` holds structured facts already established, used to catch direct contradictions.
    """

    def __init__(
        self,
        artifacts: dict[str, str] | None = None,
        records: list[Record] | None = None,
        max_rejections: int = 3,
    ) -> None:
        self._artifacts = {k: normalise(v) for k, v in (artifacts or {}).items()}
        self._records: list[Record] = list(records or [])
        self._max_rejections = max_rejections
        self._rejections: dict[str, int] = defaultdict(int)
        self.accepted_ids: set[str] = set()

    def add_artifact(self, artifact_id: str, text: str) -> None:
        self._artifacts[artifact_id] = normalise(text)

    def add_record(self, record: Record) -> None:
        self._records.append(record)

    def verify(self, claim: Claim) -> Result:
        result = self._check(claim)
        if result.accepted:
            self.accepted_ids.add(claim.id)
            self._rejections.pop(claim.id, None)
            return result

        self._rejections[claim.id] += 1
        if self._rejections[claim.id] >= self._max_rejections:
            raise CircuitBroken(
                f"claim {claim.id} rejected {self._rejections[claim.id]} times "
                f"({result.code}). Pausing the run and escalating to a human rather than "
                "retrying forever."
            )
        return result

    def rejection_count(self, claim_id: str) -> int:
        return self._rejections[claim_id]

    def _check(self, claim: Claim) -> Result:
        # Rule 4: an inference must name the claims it rests on, and those must be accepted.
        if claim.kind is ClaimKind.INFERENCE:
            if not claim.depends_on:
                return Result(
                    claim.id,
                    Verdict.REJECTED,
                    RejectionCode.UNGROUNDED_INFERENCE,
                    "Inference does not name the claims it depends on.",
                )
            missing = [d for d in claim.depends_on if d not in self.accepted_ids]
            if missing:
                return Result(
                    claim.id,
                    Verdict.REJECTED,
                    RejectionCode.UNGROUNDED_INFERENCE,
                    f"Depends on claims that were not accepted: {', '.join(sorted(missing))}.",
                )
            return Result(claim.id, Verdict.ACCEPTED)

        # Rule 1: no source, no claim.
        if not claim.source_refs:
            return Result(
                claim.id,
                Verdict.REJECTED,
                RejectionCode.NO_SOURCE,
                "Claim carries no source reference. Nothing can be rendered from it.",
            )

        # Rule 2: the quote must actually appear in the artifact it names.
        for ref in claim.source_refs:
            if ref.artifact_id not in self._artifacts:
                return Result(
                    claim.id,
                    Verdict.REJECTED,
                    RejectionCode.UNKNOWN_ARTIFACT,
                    f"Cites artifact {ref.artifact_id!r}, which this run has never seen.",
                )
            needle = normalise(ref.quoted_text)
            # An empty quote must be rejected explicitly. `"" in anything` is True, so without
            # this guard a source reference carrying no quote at all satisfies the containment
            # check and the claim is accepted. That silently defeats the one invariant the whole
            # system rests on: no quote, no claim, no rendered sentence. Rule 1 only catches an
            # empty `source_refs` tuple, not a present-but-empty quote.
            if not needle:
                return Result(
                    claim.id,
                    Verdict.REJECTED,
                    RejectionCode.NO_SOURCE,
                    f"Source reference to {ref.artifact_id} carries an empty quote, so it "
                    "supports nothing.",
                )
            if needle not in self._artifacts[ref.artifact_id]:
                return Result(
                    claim.id,
                    Verdict.REJECTED,
                    RejectionCode.QUOTE_NOT_FOUND,
                    f"Quoted text does not appear in {ref.artifact_id}: {ref.quoted_text!r}.",
                )

        # Rule 3: a claim cannot assert something an established record forbids.
        claim_text = normalise(claim.text)
        for record in self._records:
            if normalise(record.key) not in claim_text:
                continue
            hit = next((f for f in record.forbids if normalise(f) in claim_text), None)
            if hit is not None:
                return Result(
                    claim.id,
                    Verdict.REJECTED,
                    RejectionCode.CONTRADICTS_RECORD,
                    f"Asserts {hit!r} about {record.key!r}, but the record says "
                    f"{record.value!r}.",
                )

        # Rule 5: a measurement must have its number present in a source.
        if claim.kind is ClaimKind.MEASUREMENT:
            quoted = " ".join(r.quoted_text for r in claim.source_refs)
            available = set(numbers_in(quoted))
            asserted = numbers_in(claim.text)
            unsupported = [n for n in asserted if n not in available]
            if unsupported:
                return Result(
                    claim.id,
                    Verdict.REJECTED,
                    RejectionCode.NUMBER_NOT_IN_SOURCE,
                    f"Asserts {', '.join(unsupported)} but no source contains that number.",
                )

        return Result(claim.id, Verdict.ACCEPTED)


@dataclass
class RenderGate:
    """Refuses to render a sentence whose claim was not accepted.

    This is where the guarantee becomes structural rather than aspirational. The UI calls this,
    not the agent, so an agent cannot talk its way past it.
    """

    verifier: Verifier
    _blocked: list[str] = field(default_factory=list)

    def render(self, claim: Claim, sentence: str) -> str:
        if claim.id not in self.verifier.accepted_ids:
            self._blocked.append(claim.id)
            raise PermissionError(
                f"refusing to render a sentence backed by unaccepted claim {claim.id}"
            )
        return sentence

    @property
    def blocked(self) -> list[str]:
        return list(self._blocked)
