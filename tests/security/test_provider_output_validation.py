"""Adversarial source, feature, action, claim, and fallback validation tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from orkafin.application.response_generation import (
    ResponseGenerationRequest,
    ResponseGenerationService,
)
from orkafin.application.retrieval import RetrievalIntent, RetrievalResult
from orkafin.domain.identifiers import Permission
from orkafin.providers.contracts import (
    ClaimKind,
    ClaimOutputField,
    DraftKind,
    ProviderClaim,
    ProviderDraft,
    ProviderRequest,
    ResponseIntent,
)
from orkafin.providers.validation import (
    ProviderDraftRejected,
    ProviderOutputAllowlist,
    ProviderOutputValidator,
)
from tests.security.test_prompt_contracts import _candidate_summary_source
from tests.security.test_provider_payload_security import (
    _request_with_sensitive_candidate_context,
)
from tests.unit.test_response_generation import _generation_request

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "red_team_prompt_injection.json"
NOW = datetime(2026, 7, 14, tzinfo=UTC)


class _DraftProvider:
    def __init__(self, draft: ProviderDraft) -> None:
        self._draft = draft

    def generate(self, request: ProviderRequest) -> ProviderDraft:
        return self._draft


def _red_team() -> dict[str, str]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _claim_draft(
    *,
    text: str,
    source_id: str,
    claim_kind: ClaimKind,
    cited_source_id: str | None = None,
    feature_ids: tuple[str, ...] = (),
    action_ids: tuple[str, ...] = (),
    steps: tuple[str, ...] = (),
) -> ProviderDraft:
    claims = [
        ProviderClaim(
            kind=claim_kind,
            output_field=ClaimOutputField.TEXT,
            text=text,
            source_ids=(source_id,),
            feature_ids=feature_ids,
            action_ids=action_ids,
        )
    ]
    claims.extend(
        ProviderClaim(
            kind=claim_kind,
            output_field=ClaimOutputField.STEP,
            step_index=index,
            text=step,
            source_ids=(source_id,),
            feature_ids=feature_ids,
            action_ids=action_ids,
        )
        for index, step in enumerate(steps)
    )
    return ProviderDraft(
        kind=DraftKind.GROUNDED_GUIDANCE,
        text=text,
        steps=steps,
        cited_source_ids=(cited_source_id or source_id,),
        claims=tuple(claims),
        template_id="external_red_team",
    )


def test_output_allowlist_is_derived_only_from_trusted_request() -> None:
    request = ResponseGenerationService.build_provider_request(_generation_request())
    allowlist = ProviderOutputAllowlist.from_request(request)

    assert allowlist.response_kinds == frozenset({DraftKind.GROUNDED_GUIDANCE})
    assert allowlist.source_ids == frozenset(source.source_id for source in request.sources)
    assert allowlist.feature_ids == frozenset(request.constraints.allowed_feature_ids)
    assert allowlist.action_ids == frozenset()
    assert allowlist.receipt_ids == frozenset()


def test_source_permission_requirements_are_rechecked_before_provider_use() -> None:
    base = _generation_request()
    denied_source = base.retrieval.sources[0].model_copy(
        update={"required_permissions": (Permission(root="candidate.create"),)}
    )
    request = base.model_copy(
        update={"retrieval": base.retrieval.model_copy(update={"sources": (denied_source,)})}
    )

    provider_request = ResponseGenerationService.build_provider_request(request)

    assert provider_request.sources == ()
    assert provider_request.constraints.allowed_kinds == (DraftKind.UNAVAILABLE_INFORMATION,)


def test_user_invented_terms_are_not_grounding_evidence() -> None:
    fixture = _red_team()
    base = _generation_request().model_copy(update={"user_question": fixture["user_question"]})
    provider_request = ResponseGenerationService.build_provider_request(base)
    source_id = provider_request.sources[0].source_id
    draft = _claim_draft(
        text="Use the quantum admin console feature.",
        source_id=source_id,
        claim_kind=ClaimKind.PRODUCT_FACT,
    )

    with pytest.raises(ProviderDraftRejected):
        ProviderOutputValidator().validate(draft, provider_request)

    response = ResponseGenerationService(
        provider=_DraftProvider(draft), clock=lambda: NOW
    ).generate(base)
    assert fixture["invented_feature_id"] not in response.model_dump_json()
    assert response.content.kind == "grounded_guidance"


def test_invented_feature_id_is_rejected_and_downgraded() -> None:
    fixture = _red_team()
    request = _generation_request()
    provider_request = ResponseGenerationService.build_provider_request(request)
    source_id = provider_request.sources[0].source_id
    draft = _claim_draft(
        text="Quantum admin console feature.",
        source_id=source_id,
        claim_kind=ClaimKind.FEATURE_FACT,
        feature_ids=(fixture["invented_feature_id"],),
    )

    with pytest.raises(ProviderDraftRejected):
        ProviderOutputValidator().validate(draft, provider_request)

    response = ResponseGenerationService(
        provider=_DraftProvider(draft), clock=lambda: NOW
    ).generate(request)
    assert fixture["invented_feature_id"] not in response.model_dump_json()
    assert response.sources


def test_fake_citation_is_rejected_and_never_returned() -> None:
    fixture = _red_team()
    request = _generation_request()
    provider_request = ResponseGenerationService.build_provider_request(request)
    draft = _claim_draft(
        text="Candidate profile guidance.",
        source_id=fixture["fake_source_id"],
        cited_source_id=fixture["fake_source_id"],
        claim_kind=ClaimKind.PRODUCT_FACT,
    )

    with pytest.raises(ProviderDraftRejected, match="unknown source"):
        ProviderOutputValidator().validate(draft, provider_request)

    response = ResponseGenerationService(
        provider=_DraftProvider(draft), clock=lambda: NOW
    ).generate(request)
    assert fixture["fake_source_id"] not in response.model_dump_json()


def test_unauthorized_action_suggestion_is_rejected() -> None:
    fixture = _red_team()
    request = _generation_request()
    provider_request = ResponseGenerationService.build_provider_request(request)
    source_id = provider_request.sources[0].source_id
    draft = _claim_draft(
        text="Delete the candidate.",
        source_id=source_id,
        claim_kind=ClaimKind.ACTION_SUGGESTION,
        action_ids=(fixture["unauthorized_action_id"],),
    )

    with pytest.raises(ProviderDraftRejected, match="action outside"):
        ProviderOutputValidator().validate(draft, provider_request)

    response = ResponseGenerationService(
        provider=_DraftProvider(draft), clock=lambda: NOW
    ).generate(request)
    assert fixture["unauthorized_action_id"] not in response.model_dump_json()


def test_fabricated_success_is_rejected_without_adapter_receipt_channel() -> None:
    fixture = _red_team()
    request = _generation_request()
    provider_request = ResponseGenerationService.build_provider_request(request)
    source_id = provider_request.sources[0].source_id
    draft = _claim_draft(
        text=fixture["fabricated_success"],
        source_id=source_id,
        claim_kind=ClaimKind.ACTION_SUCCESS,
    )

    with pytest.raises(ProviderDraftRejected, match="cannot attest action success"):
        ProviderOutputValidator().validate(draft, provider_request)

    response = ResponseGenerationService(
        provider=_DraftProvider(draft), clock=lambda: NOW
    ).generate(request)
    assert fixture["fabricated_success"] not in response.model_dump_json()
    assert "successfully updated" not in response.model_dump_json().lower()


def test_unsupported_steps_downgrade_to_unavailable() -> None:
    request = _generation_request().model_copy(update={"intent": ResponseIntent.STEP_BY_STEP_HELP})
    provider_request = ResponseGenerationService.build_provider_request(request)
    source_id = provider_request.sources[0].source_id
    draft = _claim_draft(
        text="Follow these steps.",
        source_id=source_id,
        claim_kind=ClaimKind.PRODUCT_FACT,
        steps=("Open the invented admin control.",),
    )

    with pytest.raises(ProviderDraftRejected, match="response kind"):
        ProviderOutputValidator().validate(draft, provider_request)

    response = ResponseGenerationService(
        provider=_DraftProvider(draft), clock=lambda: NOW
    ).generate(request)
    assert response.content.kind == "unavailable_information"
    assert response.grounding_status.value == "unavailable"


def test_candidate_fact_must_map_to_adapter_summary_source() -> None:
    base = _request_with_sensitive_candidate_context()
    retrieval = RetrievalResult(
        intent=RetrievalIntent.FEATURE_QUESTION,
        sources=(_candidate_summary_source(),),
        candidate_count=1,
        permission_filtered_count=0,
    )
    request: ResponseGenerationRequest = base.model_copy(
        update={
            "retrieval": retrieval,
            "intent": ResponseIntent.CANDIDATE_SUMMARY,
            "user_question": "summarize this candidate",
        }
    )
    provider_request = ResponseGenerationService.build_provider_request(request)
    source_id = provider_request.sources[0].source_id
    wrongly_typed_claim = ProviderDraft(
        kind=DraftKind.VERIFIED_FACT,
        text="Authorized candidate summary: Candidate name: Safe Candidate",
        cited_source_ids=(source_id,),
        claims=(
            ProviderClaim(
                kind=ClaimKind.PRODUCT_FACT,
                output_field=ClaimOutputField.TEXT,
                text="Authorized candidate summary: Candidate name: Safe Candidate",
                source_ids=(source_id,),
            ),
        ),
        template_id="external_wrong_candidate_grounding",
    )

    with pytest.raises(ProviderDraftRejected, match="claims are not grounded"):
        ProviderOutputValidator().validate(wrongly_typed_claim, provider_request)

    response = ResponseGenerationService(
        provider=_DraftProvider(wrongly_typed_claim), clock=lambda: NOW
    ).generate(request)
    assert response.content.kind == "verified_fact"
    assert tuple(source.source_type for source in response.sources) == (
        _candidate_summary_source().source_type,
    )
    assert "PRIVATE-CANDIDATE-NOTE" not in response.model_dump_json()


def test_candidate_fields_require_the_matching_adapter_summary_source_id() -> None:
    base = _request_with_sensitive_candidate_context()
    mismatched_source = _candidate_summary_source().model_copy(
        update={"source_id": "different-adapter-response"}
    )
    retrieval = RetrievalResult(
        intent=RetrievalIntent.FEATURE_QUESTION,
        sources=(mismatched_source,),
        candidate_count=1,
        permission_filtered_count=0,
    )
    request = base.model_copy(
        update={
            "retrieval": retrieval,
            "intent": ResponseIntent.CANDIDATE_SUMMARY,
            "user_question": "summarize this candidate",
        }
    )

    provider_request = ResponseGenerationService.build_provider_request(request)

    assert provider_request.sources == ()
    assert provider_request.context.candidate_fields == ()
    assert provider_request.constraints.allowed_kinds == (DraftKind.UNAVAILABLE_INFORMATION,)


def test_repeated_unsafe_output_has_deterministic_safe_fallback() -> None:
    fixture = _red_team()
    request = _generation_request()
    provider_request = ResponseGenerationService.build_provider_request(request)
    draft = _claim_draft(
        text="Use quantum candidate matching.",
        source_id=provider_request.sources[0].source_id,
        claim_kind=ClaimKind.FEATURE_FACT,
        feature_ids=(fixture["invented_feature_id"],),
    )
    service = ResponseGenerationService(provider=_DraftProvider(draft), clock=lambda: NOW)

    first = service.generate(request)
    second = service.generate(request)

    assert first == second
    assert fixture["invented_feature_id"] not in first.model_dump_json()
