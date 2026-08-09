from sixty_days.evidence import EvidenceChecker, EvidenceDecision


def response(**checks):
    return {"model": "gemini-3.5-flash", "recorded": True, "checks": checks}


def test_good_wide_damage_photo_is_ready_for_applicant_review_not_declared_valid():
    result = EvidenceChecker().check(
        "photo_wide", "evidence_good",
        response(damage_visible=True, floor_and_wall_visible=True, water_line_visible=True),
    )
    assert result.decision is EvidenceDecision.READY_FOR_REVIEW
    assert "Review the image yourself" in result.guidance
    assert "accept" not in result.guidance.casefold()


def test_close_damage_photo_gets_one_actionable_retake_instruction():
    result = EvidenceChecker().check(
        "photo_wide", "evidence_close",
        response(damage_visible=True, floor_and_wall_visible=False, water_line_visible=False),
    )
    assert result.decision is EvidenceDecision.RETAKE
    assert result.guidance == "Step back and include both the floor and wall for context."


def test_wrong_address_is_rejected_even_when_document_is_legible():
    result = EvidenceChecker().check(
        "deed", "evidence_wrong_address",
        response(
            legible=True, applicant_name_visible=True, address_visible=True,
            applicant_match=True, address_match=False,
        ),
    )
    assert result.decision is EvidenceDecision.RETAKE
    assert "different address" in result.guidance


def test_unknown_model_observation_routes_to_manual_review():
    result = EvidenceChecker().check(
        "identity", "evidence_uncertain",
        response(legible=True, applicant_name_visible=True),
    )
    assert result.decision is EvidenceDecision.MANUAL_REVIEW
    assert "could not determine" in result.guidance


def test_unsupported_requirement_never_gets_a_model_guess():
    result = EvidenceChecker().check("case_review", "evidence_other", response())
    assert result.decision is EvidenceDecision.MANUAL_REVIEW
    assert result.checks == {}
