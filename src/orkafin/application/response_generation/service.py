"""Construct grounded responses from a provider draft without delegating authority."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime

from orkafin.application.retrieval.models import RetrievalResult
from orkafin.domain.base import DomainModel, Identifier, LowercaseIdentifier, ShortText
from orkafin.domain.candidate import CandidateFieldSensitivity
from orkafin.domain.context import ResolvedPageContext
from orkafin.domain.responses import (
    AssistantContent,
    AssistantResponse,
    GroundedGuidanceContent,
    GroundingStatus,
    RefusalContent,
    UnavailableInformationContent,
    VerifiedFactContent,
)
from orkafin.domain.sources import SourceType
from orkafin.providers.base import ResponseProvider
from orkafin.providers.contracts import (
    ApprovedProviderSource,
    DraftKind,
    ProviderDraft,
    ProviderRequest,
    ResponseIntent,
    SafeCandidateField,
    SafeResolvedContextSummary,
    SafeResponseConstraints,
)
from orkafin.providers.deterministic import DeterministicResponseProvider

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_SAFE_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "approved",
        "available",
        "candidate",
        "cannot",
        "for",
        "follow",
        "guidance",
        "i",
        "information",
        "is",
        "limited",
        "not",
        "on",
        "request",
        "summary",
        "that",
        "the",
        "this",
        "to",
        "with",
        "you",
        "your",
    }
)


class ResponseGenerationRequest(DomainModel):
    """Trusted orchestration inputs; raw context never crosses into a provider."""

    user_question: ShortText
    context: ResolvedPageContext
    retrieval: RetrievalResult
    intent: ResponseIntent
    response_id: Identifier
    conversation_id: Identifier
    refusal_reason_code: LowercaseIdentifier = "permission_denied"


class ProviderDraftRejected(ValueError):
    """A provider draft was structurally or lexically outside the approved boundary."""


class ResponseGenerationService:
    """Validate every provider result and use deterministic output as the safe fallback."""

    def __init__(
        self,
        *,
        provider: ResponseProvider,
        fallback_provider: ResponseProvider | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._provider = provider
        self._fallback_provider = fallback_provider or DeterministicResponseProvider()
        self._clock = clock or (lambda: datetime.now(UTC))

    def generate(self, request: ResponseGenerationRequest) -> AssistantResponse:
        """Return a schema-valid response, falling back on any unsafe provider result."""
        provider_request = self.build_provider_request(request)
        try:
            draft = self._provider.generate(provider_request)
            self._validate_draft(draft, provider_request)
        except Exception:  # Providers are untrusted dependencies; no error text is exposed.
            try:
                draft = self._fallback_provider.generate(provider_request)
                self._validate_draft(draft, provider_request)
            except Exception:
                draft = ProviderDraft(
                    kind=DraftKind.UNAVAILABLE_INFORMATION,
                    text="Approved information is not available for this request.",
                    template_id="provider_safe_failure",
                )
        return self._to_assistant_response(draft, request, provider_request)

    @staticmethod
    def build_provider_request(request: ResponseGenerationRequest) -> ProviderRequest:
        """Create the allowlist, excluding identity, permissions, notes, and hidden fields."""
        context = request.context
        candidate_fields: list[SafeCandidateField] = []
        if context.candidate_summary is not None:
            for field in context.candidate_summary.visible_fields:
                if field.sensitivity is CandidateFieldSensitivity.STANDARD:
                    candidate_fields.append(
                        SafeCandidateField(label=field.label, value=str(field.value.value))
                    )
        sources = tuple(
            ApprovedProviderSource(
                source_id=source.source_id,
                title=source.title,
                excerpt=source.excerpt[:500],
            )
            for source in request.retrieval.sources
        )
        return ProviderRequest(
            user_question=request.user_question,
            context=SafeResolvedContextSummary(
                app_name=context.app.display_name,
                page_id=context.page_id,
                selected_entity_type=(
                    context.selected_entity.entity_type
                    if context.selected_entity is not None
                    else None
                ),
                candidate_fields=tuple(candidate_fields),
            ),
            sources=sources,
            intent=request.intent,
            constraints=_constraints_for(
                request.intent,
                bool(sources),
                any(
                    source.source_type is SourceType.CANDIDATE_SUMMARY
                    for source in request.retrieval.sources
                ),
                request.refusal_reason_code,
            ),
        )

    @staticmethod
    def _validate_draft(draft: ProviderDraft, request: ProviderRequest) -> None:
        if draft.kind not in request.constraints.allowed_kinds:
            raise ProviderDraftRejected("provider chose a response kind outside server constraints")
        if len(draft.steps) > request.constraints.max_steps:
            raise ProviderDraftRejected("provider exceeded the step limit")
        approved_source_ids = {source.source_id for source in request.sources}
        cited_ids = set(draft.cited_source_ids)
        if len(cited_ids) != len(draft.cited_source_ids):
            raise ProviderDraftRejected("provider cited a source more than once")
        if not cited_ids.issubset(approved_source_ids):
            raise ProviderDraftRejected("provider cited an unknown source")
        if request.constraints.require_citations and not cited_ids:
            raise ProviderDraftRejected("grounded provider draft requires citations")
        if draft.kind in {DraftKind.GROUNDED_GUIDANCE, DraftKind.VERIFIED_FACT} and not cited_ids:
            raise ProviderDraftRejected("grounded provider draft requires citations")
        if draft.kind in {DraftKind.REFUSAL, DraftKind.UNAVAILABLE_INFORMATION} and cited_ids:
            raise ProviderDraftRejected("non-grounded provider draft cannot cite sources")
        ResponseGenerationService._reject_unsupported_terms(draft, request)

    @staticmethod
    def _reject_unsupported_terms(draft: ProviderDraft, request: ProviderRequest) -> None:
        """Reject novel substantive terms, a conservative guard against invented features."""
        if draft.kind not in {DraftKind.GROUNDED_GUIDANCE, DraftKind.VERIFIED_FACT}:
            return
        approved_text = " ".join(
            (
                request.user_question,
                request.context.app_name,
                request.context.page_id,
                *(f"{field.label} {field.value}" for field in request.context.candidate_fields),
                *(f"{source.title} {source.excerpt}" for source in request.sources),
            )
        )
        allowed_tokens = set(_TOKEN_PATTERN.findall(approved_text.lower())).union(_SAFE_WORDS)
        draft_tokens = set(_TOKEN_PATTERN.findall(f"{draft.text} {' '.join(draft.steps)}".lower()))
        unsupported = {
            token for token in draft_tokens if len(token) >= 4 and token not in allowed_tokens
        }
        if unsupported:
            raise ProviderDraftRejected("provider draft introduced unsupported substantive terms")

    def _to_assistant_response(
        self,
        draft: ProviderDraft,
        request: ResponseGenerationRequest,
        provider_request: ProviderRequest,
    ) -> AssistantResponse:
        source_lookup = {source.source_id: source for source in request.retrieval.sources}
        cited_sources = tuple(source_lookup[source_id] for source_id in draft.cited_source_ids)
        content: AssistantContent
        if draft.kind is DraftKind.GROUNDED_GUIDANCE:
            content = GroundedGuidanceContent(
                text=draft.text, steps=draft.steps, source_ids=draft.cited_source_ids
            )
            grounding_status = GroundingStatus.GROUNDED
        elif draft.kind is DraftKind.VERIFIED_FACT:
            content = VerifiedFactContent(text=draft.text, source_ids=draft.cited_source_ids)
            grounding_status = GroundingStatus.VERIFIED
        elif draft.kind is DraftKind.REFUSAL:
            content = RefusalContent(
                text=draft.text, reason_code=provider_request.constraints.fallback_reason_code
            )
            grounding_status = GroundingStatus.NOT_APPLICABLE
        else:
            content = UnavailableInformationContent(
                text=draft.text, reason_code=provider_request.constraints.fallback_reason_code
            )
            grounding_status = GroundingStatus.UNAVAILABLE
        return AssistantResponse(
            response_id=request.response_id,
            conversation_id=request.conversation_id,
            request_id=request.context.request_id,
            grounding_status=grounding_status,
            content=content,
            sources=cited_sources,
            created_at=self._clock(),
        )


def _constraints_for(
    intent: ResponseIntent,
    has_sources: bool,
    has_candidate_summary_source: bool,
    reason_code: LowercaseIdentifier,
) -> SafeResponseConstraints:
    if intent is ResponseIntent.REFUSAL:
        return SafeResponseConstraints(
            allowed_kinds=(DraftKind.REFUSAL,),
            require_citations=False,
            fallback_reason_code=reason_code,
        )
    if not has_sources:
        return SafeResponseConstraints(
            allowed_kinds=(DraftKind.UNAVAILABLE_INFORMATION,),
            require_citations=False,
            fallback_reason_code="source_missing",
        )
    if intent is ResponseIntent.CANDIDATE_SUMMARY:
        if has_candidate_summary_source:
            return SafeResponseConstraints(
                allowed_kinds=(DraftKind.VERIFIED_FACT, DraftKind.UNAVAILABLE_INFORMATION),
                require_citations=True,
                fallback_reason_code="candidate_summary_unavailable",
            )
        return SafeResponseConstraints(
            allowed_kinds=(DraftKind.UNAVAILABLE_INFORMATION,),
            require_citations=False,
            fallback_reason_code="candidate_summary_unavailable",
        )
    if intent is ResponseIntent.UNKNOWN:
        return SafeResponseConstraints(
            allowed_kinds=(DraftKind.UNAVAILABLE_INFORMATION,),
            require_citations=False,
            fallback_reason_code="source_missing",
        )
    return SafeResponseConstraints(
        allowed_kinds=(DraftKind.GROUNDED_GUIDANCE,),
        require_citations=True,
        fallback_reason_code="source_missing",
    )
