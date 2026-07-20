"""Category and completeness invariants for provider claim grounding."""

from __future__ import annotations

import pytest

from orkafin.domain.catalog import VerificationStatus
from orkafin.domain.sources import SourceType
from orkafin.providers.contracts import (
    ApprovedProviderSource,
    ClaimKind,
    ClaimOutputField,
    DraftKind,
    ProviderClaim,
    ProviderDraft,
    ProviderRequest,
    ResponseIntent,
    SafeCandidateField,
    SafeResolvedContextSummary,
    SafeResponseConstraints,
)
from orkafin.providers.grounding import ClaimGroundingChecker, ClaimGroundingError

FEATURE_ID = "candidate_directory"
ACTION_ID = "candidate.update_start_date"


def _source(
    source_id: str,
    source_type: SourceType,
    *,
    title: str,
    excerpt: str,
    steps: tuple[str, ...] = (),
    feature_ids: tuple[str, ...] = (),
    action_ids: tuple[str, ...] = (),
    verification_status: VerificationStatus = VerificationStatus.VERIFIED,
) -> ApprovedProviderSource:
    return ApprovedProviderSource(
        source_id=source_id,
        source_type=source_type,
        title=title,
        excerpt=excerpt,
        approved_steps=steps,
        feature_ids=feature_ids,
        action_ids=action_ids,
        verification_status=verification_status,
    )


def _request(
    *sources: ApprovedProviderSource,
    intent: ResponseIntent = ResponseIntent.EXPLAIN_PAGE,
    candidate_fields: tuple[SafeCandidateField, ...] = (),
    allowed_feature_ids: tuple[str, ...] = (),
    allowed_action_ids: tuple[str, ...] = (),
) -> ProviderRequest:
    return ProviderRequest(
        user_question="Explain the approved source.",
        context=SafeResolvedContextSummary(
            app_name="OrkaATS",
            page_id="candidate_profile",
            candidate_fields=candidate_fields,
        ),
        sources=sources,
        intent=intent,
        constraints=SafeResponseConstraints(
            allowed_kinds=(DraftKind.GROUNDED_GUIDANCE, DraftKind.VERIFIED_FACT),
            allowed_feature_ids=allowed_feature_ids,
            allowed_action_ids=allowed_action_ids,
            require_citations=True,
            fallback_reason_code="source_missing",
        ),
    )


def _claim(
    kind: ClaimKind,
    text: str,
    source_id: str,
    *,
    output_field: ClaimOutputField = ClaimOutputField.TEXT,
    step_index: int | None = None,
    feature_ids: tuple[str, ...] = (),
    action_ids: tuple[str, ...] = (),
    receipt_ids: tuple[str, ...] = (),
) -> ProviderClaim:
    return ProviderClaim(
        kind=kind,
        output_field=output_field,
        step_index=step_index,
        text=text,
        source_ids=(source_id,),
        feature_ids=feature_ids,
        action_ids=action_ids,
        receipt_ids=receipt_ids,
    )


def _draft(
    claim: ProviderClaim,
    *,
    steps: tuple[str, ...] = (),
    additional_claims: tuple[ProviderClaim, ...] = (),
    citations: tuple[str, ...] | None = None,
) -> ProviderDraft:
    return ProviderDraft(
        kind=DraftKind.GROUNDED_GUIDANCE,
        text=claim.text,
        steps=steps,
        cited_source_ids=citations or claim.source_ids,
        claims=(claim, *additional_claims),
        template_id="grounding_test",
    )


@pytest.mark.parametrize(
    ("provider_request", "claim"),
    (
        (
            _request(
                _source(
                    "page_source",
                    SourceType.PAGE_CATALOG,
                    title="Candidate profile",
                    excerpt="Candidate profile guidance",
                )
            ),
            _claim(ClaimKind.PRODUCT_FACT, "Candidate profile guidance", "page_source"),
        ),
        (
            _request(
                _source(
                    "feature_source",
                    SourceType.FEATURE_CATALOG,
                    title="Candidate directory",
                    excerpt="Candidate directory guidance",
                    feature_ids=(FEATURE_ID,),
                ),
                allowed_feature_ids=(FEATURE_ID,),
            ),
            _claim(
                ClaimKind.FEATURE_FACT,
                "Candidate directory guidance",
                "feature_source",
                feature_ids=(FEATURE_ID,),
            ),
        ),
        (
            _request(
                _source(
                    "help_source",
                    SourceType.HELP_ARTICLE,
                    title="Candidate help",
                    excerpt="Candidate help guidance",
                )
            ),
            _claim(ClaimKind.HELP_FACT, "Candidate help guidance", "help_source"),
        ),
        (
            _request(
                _source(
                    "candidate_source",
                    SourceType.CANDIDATE_SUMMARY,
                    title="Candidate summary",
                    excerpt="Authorized candidate summary",
                ),
                candidate_fields=(SafeCandidateField(label="Candidate name", value="Taylor"),),
            ),
            _claim(
                ClaimKind.CANDIDATE_FACT,
                "Candidate name Taylor",
                "candidate_source",
            ),
        ),
        (
            _request(
                _source(
                    "action_source",
                    SourceType.ACTION_DEFINITION,
                    title="Update start date",
                    excerpt="Update start date guidance",
                    action_ids=(ACTION_ID,),
                ),
                allowed_action_ids=(ACTION_ID,),
            ),
            _claim(
                ClaimKind.ACTION_SUGGESTION,
                "Update start date guidance",
                "action_source",
                action_ids=(ACTION_ID,),
            ),
        ),
    ),
)
def test_each_claim_category_requires_matching_approved_evidence(
    provider_request: ProviderRequest, claim: ProviderClaim
) -> None:
    ClaimGroundingChecker().check(_draft(claim), provider_request)


def test_unverified_source_requires_uncertainty_intent() -> None:
    source = _source(
        "provisional_page",
        SourceType.PAGE_CATALOG,
        title="Candidate profile",
        excerpt="Candidate profile guidance",
        verification_status=VerificationStatus.PROVISIONAL,
    )
    claim = _claim(ClaimKind.PRODUCT_FACT, "Candidate profile guidance", "provisional_page")

    with pytest.raises(ClaimGroundingError, match="uncertainty"):
        ClaimGroundingChecker().check(_draft(claim), _request(source))

    ClaimGroundingChecker().check(
        _draft(claim), _request(source, intent=ResponseIntent.UNCERTAINTY)
    )


def test_feature_and_action_ids_must_be_backed_by_the_claims_own_sources() -> None:
    page = _source(
        "page_source",
        SourceType.PAGE_CATALOG,
        title="Candidate profile",
        excerpt="Candidate profile guidance",
    )
    feature = _source(
        "feature_source",
        SourceType.FEATURE_CATALOG,
        title="Candidate directory",
        excerpt="Candidate directory guidance",
        feature_ids=(FEATURE_ID,),
    )
    action = _source(
        "action_source",
        SourceType.ACTION_DEFINITION,
        title="Update start date",
        excerpt="Update start date guidance",
        action_ids=(ACTION_ID,),
    )
    request = _request(
        page,
        feature,
        action,
        allowed_feature_ids=(FEATURE_ID,),
        allowed_action_ids=(ACTION_ID,),
    )

    with pytest.raises(ClaimGroundingError, match="matching catalog evidence"):
        ClaimGroundingChecker().check(
            _draft(
                _claim(
                    ClaimKind.FEATURE_FACT,
                    "Candidate profile guidance",
                    "page_source",
                    feature_ids=(FEATURE_ID,),
                )
            ),
            request,
        )
    with pytest.raises(ClaimGroundingError, match="matching definition evidence"):
        ClaimGroundingChecker().check(
            _draft(
                _claim(
                    ClaimKind.ACTION_SUGGESTION,
                    "Candidate profile guidance",
                    "page_source",
                    action_ids=(ACTION_ID,),
                )
            ),
            request,
        )


@pytest.mark.parametrize(
    ("claim", "error"),
    (
        (
            _claim(ClaimKind.FEATURE_FACT, "Candidate directory guidance", "feature_source"),
            "explicit feature IDs",
        ),
        (
            _claim(ClaimKind.ACTION_SUGGESTION, "Update start date guidance", "action_source"),
            "explicit action IDs",
        ),
        (
            _claim(ClaimKind.HELP_FACT, "Candidate profile guidance", "page_source"),
            "approved help source",
        ),
        (
            _claim(ClaimKind.CANDIDATE_FACT, "Candidate summary", "candidate_source"),
            "supplied verified fields",
        ),
        (
            _claim(ClaimKind.ACTION_SUCCESS, "Update start date guidance", "action_source"),
            "cannot author action-success",
        ),
    ),
)
def test_missing_category_authority_is_rejected(claim: ProviderClaim, error: str) -> None:
    sources = (
        _source(
            "page_source",
            SourceType.PAGE_CATALOG,
            title="Candidate profile",
            excerpt="Candidate profile guidance",
        ),
        _source(
            "feature_source",
            SourceType.FEATURE_CATALOG,
            title="Candidate directory",
            excerpt="Candidate directory guidance",
            feature_ids=(FEATURE_ID,),
        ),
        _source(
            "candidate_source",
            SourceType.CANDIDATE_SUMMARY,
            title="Candidate summary",
            excerpt="Candidate summary guidance",
        ),
        _source(
            "action_source",
            SourceType.ACTION_DEFINITION,
            title="Update start date",
            excerpt="Update start date guidance",
            action_ids=(ACTION_ID,),
        ),
    )
    request = _request(
        *sources,
        allowed_feature_ids=(FEATURE_ID,),
        allowed_action_ids=(ACTION_ID,),
    )

    with pytest.raises(ClaimGroundingError, match=error):
        ClaimGroundingChecker().check(_draft(claim), request)


def test_steps_claim_coverage_citations_and_lexical_support_are_exact() -> None:
    step = "Open candidate profile"
    source = _source(
        "help_source",
        SourceType.HELP_ARTICLE,
        title="Candidate help",
        excerpt="Candidate help guidance",
        steps=(step,),
    )
    request = _request(source)
    text_claim = _claim(ClaimKind.HELP_FACT, "Candidate help guidance", "help_source")
    step_claim = _claim(
        ClaimKind.HELP_FACT,
        step,
        "help_source",
        output_field=ClaimOutputField.STEP,
        step_index=0,
    )
    ClaimGroundingChecker().check(
        _draft(text_claim, steps=(step,), additional_claims=(step_claim,)), request
    )

    missing_step_claim = _draft(text_claim, steps=(step,))
    with pytest.raises(ClaimGroundingError, match="cover the text and every step"):
        ClaimGroundingChecker().check(missing_step_claim, request)

    wrong_step = _claim(
        ClaimKind.HELP_FACT,
        "Open invented console",
        "help_source",
        output_field=ClaimOutputField.STEP,
        step_index=0,
    )
    with pytest.raises(ClaimGroundingError, match="approved verified instruction"):
        ClaimGroundingChecker().check(
            _draft(
                text_claim,
                steps=(wrong_step.text,),
                additional_claims=(wrong_step,),
            ),
            request,
        )

    unsupported = _claim(ClaimKind.HELP_FACT, "Candidate quantum guidance", "help_source")
    with pytest.raises(ClaimGroundingError, match="terms absent"):
        ClaimGroundingChecker().check(_draft(unsupported), request)

    with pytest.raises(ClaimGroundingError, match="citations must exactly match"):
        ClaimGroundingChecker().check(_draft(text_claim, citations=("other_source",)), request)


def test_duplicate_claim_locations_and_mismatched_output_text_are_rejected() -> None:
    source = _source(
        "page_source",
        SourceType.PAGE_CATALOG,
        title="Candidate profile",
        excerpt="Candidate profile guidance",
    )
    request = _request(source)
    claim = _claim(ClaimKind.PRODUCT_FACT, "Candidate profile guidance", "page_source")

    with pytest.raises(ClaimGroundingError, match="exactly one claim"):
        ClaimGroundingChecker().check(_draft(claim, additional_claims=(claim,)), request)

    mismatch = ProviderDraft(
        kind=DraftKind.GROUNDED_GUIDANCE,
        text="Candidate profile",
        cited_source_ids=("page_source",),
        claims=(claim,),
        template_id="grounding_mismatch",
    )
    with pytest.raises(ClaimGroundingError, match="exactly match"):
        ClaimGroundingChecker().check(mismatch, request)
