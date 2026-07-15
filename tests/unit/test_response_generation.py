"""Contract coverage for deterministic and fallback response generation."""

from __future__ import annotations

from datetime import UTC, datetime

from orkafin.application.response_generation import (
    ResponseGenerationRequest,
    ResponseGenerationService,
)
from orkafin.application.retrieval import RetrievalIntent, RetrievalResult
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
    SafeResolvedContextSummary,
    SafeResponseConstraints,
)
from orkafin.providers.deterministic import DeterministicResponseProvider
from tests.unit.test_retrieval_service import _context, _request, _service

NOW = datetime(2026, 7, 14, tzinfo=UTC)


class _ErrorProvider:
    def generate(self, request: ProviderRequest) -> ProviderDraft:
        raise TimeoutError("synthetic timeout")


class _DraftProvider:
    def __init__(self, draft: ProviderDraft) -> None:
        self._draft = draft

    def generate(self, request: ProviderRequest) -> ProviderDraft:
        return self._draft


def _provider_request() -> ProviderRequest:
    return ProviderRequest(
        user_question="explain this page",
        context=SafeResolvedContextSummary(app_name="OrkaATS", page_id="candidate_profile"),
        sources=(
            ApprovedProviderSource(
                source_id="candidate_profile",
                source_type=SourceType.PAGE_CATALOG,
                title="Candidate profile",
                excerpt="View the approved candidate profile.",
                verification_status=VerificationStatus.PROVISIONAL,
            ),
        ),
        intent=ResponseIntent.EXPLAIN_PAGE,
        constraints=SafeResponseConstraints(
            allowed_kinds=(DraftKind.GROUNDED_GUIDANCE,),
            require_citations=True,
            fallback_reason_code="source_missing",
        ),
    )


def _generation_request(*, no_sources: bool = False) -> ResponseGenerationRequest:
    context = _context(page_id="candidate_profile", permissions=("candidate.view",))
    retrieval = (
        RetrievalResult(
            intent=RetrievalIntent.UNKNOWN_FEATURE,
            no_source_reason="No approved source matched.",
            candidate_count=0,
            permission_filtered_count=0,
        )
        if no_sources
        else _service().retrieve(_request("explain this page"))
    )
    return ResponseGenerationRequest(
        user_question="explain this page",
        context=context,
        retrieval=retrieval,
        intent=ResponseIntent.EXPLAIN_PAGE,
        response_id="response-provider-001",
        conversation_id="conversation-001",
    )


def test_deterministic_provider_output_is_stable() -> None:
    provider = DeterministicResponseProvider()

    assert provider.generate(_provider_request()) == provider.generate(_provider_request())
    assert provider.generate(_provider_request()).template_id == "explain_page_v1"


def test_no_source_response_cannot_claim_grounding() -> None:
    response = ResponseGenerationService(
        provider=DeterministicResponseProvider(), clock=lambda: NOW
    ).generate(_generation_request(no_sources=True))

    assert response.grounding_status.value == "unavailable"
    assert response.sources == ()
    assert response.content.kind == "unavailable_information"


def test_invented_feature_draft_is_downgraded_to_deterministic_guidance() -> None:
    unsafe = _DraftProvider(
        ProviderDraft(
            kind=DraftKind.GROUNDED_GUIDANCE,
            text="Use quantum candidate matching from this page.",
            cited_source_ids=("candidate_profile",),
            claims=(
                ProviderClaim(
                    kind=ClaimKind.PRODUCT_FACT,
                    output_field=ClaimOutputField.TEXT,
                    text="Use quantum candidate matching from this page.",
                    source_ids=("candidate_profile",),
                ),
            ),
            template_id="external_claim",
        )
    )
    response = ResponseGenerationService(provider=unsafe, clock=lambda: NOW).generate(
        _generation_request()
    )

    assert response.content.kind == "grounded_guidance"
    assert "quantum" not in response.content.text.lower()
    assert response.sources[0].source_id == "candidate_profile"


def test_missing_or_unknown_provider_citations_fall_back_safely() -> None:
    for citations in ((), ("unknown_source",)):
        claim_sources = citations or ("candidate_profile",)
        provider = _DraftProvider(
            ProviderDraft(
                kind=DraftKind.GROUNDED_GUIDANCE,
                text="Candidate profile guidance.",
                cited_source_ids=citations,
                claims=(
                    ProviderClaim(
                        kind=ClaimKind.PRODUCT_FACT,
                        output_field=ClaimOutputField.TEXT,
                        text="Candidate profile guidance.",
                        source_ids=claim_sources,
                    ),
                ),
                template_id="external_claim",
            )
        )
        response = ResponseGenerationService(provider=provider, clock=lambda: NOW).generate(
            _generation_request()
        )

        assert response.content.kind == "grounded_guidance"
        assert tuple(source.source_id for source in response.sources) == ("candidate_profile",)


def test_provider_errors_fall_back_to_deterministic_safe_output() -> None:
    response = ResponseGenerationService(provider=_ErrorProvider(), clock=lambda: NOW).generate(
        _generation_request()
    )

    assert response.content.kind == "grounded_guidance"
    assert response.content.text.startswith("Available approved guidance")
    assert "limited" in response.content.text
