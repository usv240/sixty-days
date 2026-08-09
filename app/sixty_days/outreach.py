"""Prepare applicant-controlled records requests without contacting anyone."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any


PREPARABLE_SOURCES = {"public_record", "third_party"}


@dataclass(frozen=True)
class PreparedRequest:
    requirement_key: str
    requested_on: str
    addressee: str
    subject: str
    body: str
    status: str = "prepared_for_applicant"
    delivery: str = "applicant_sends"

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "safety": (
                "Nothing was sent. The applicant must review, complete, and send this request."
            ),
        }


class RequestPreparer:
    def prepare(self, requirement: dict[str, Any], requested_on: date) -> PreparedRequest:
        source = str(requirement.get("source", ""))
        if source not in PREPARABLE_SOURCES:
            raise ValueError("this item cannot be requested from a third party")
        title = str(requirement["title"])
        addressee = str(requirement["routed_to"])
        body = (
            f"To {addressee},\n\n"
            f"I am requesting a copy of: {title}. "
            "I will add my name, account or property details, and any authorization you require "
            "before I send this request. Please return the record directly to me.\n\n"
            "Applicant signature: ____________________\n"
            "Preferred return method: ____________________"
        )
        return PreparedRequest(
            requirement_key=str(requirement["key"]),
            requested_on=requested_on.isoformat(),
            addressee=addressee,
            subject=f"Applicant request for {title}",
            body=body,
        )
