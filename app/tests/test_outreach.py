from datetime import date

import pytest

from sixty_days.outreach import RequestPreparer


def test_third_party_request_is_prepared_for_applicant_and_never_sent():
    result = RequestPreparer().prepare({
        "key": "insurance_denial",
        "title": "Your insurer's decision letter",
        "source": "third_party",
        "routed_to": "your insurer",
    }, date(2026, 8, 10)).as_dict()
    assert result["status"] == "prepared_for_applicant"
    assert result["delivery"] == "applicant_sends"
    assert "Nothing was sent" in result["safety"]
    assert "add my name" in result["body"]


def test_applicant_only_evidence_cannot_be_misrepresented_as_third_party_outreach():
    with pytest.raises(ValueError, match="cannot be requested"):
        RequestPreparer().prepare({
            "key": "photo_wide",
            "title": "Wide photo",
            "source": "applicant_only",
            "routed_to": "you",
        }, date(2026, 8, 10))
