"""Construct grounded responses from a provider draft without delegating authority."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from pydantic import Field

from orkafin.application.retrieval.models import RetrievalResult
from orkafin.domain.base import DomainModel, Identifier, LowercaseIdentifier, ShortText
from orkafin.domain.candidate import CandidateFieldSensitivity
from orkafin.domain.catalog import VerificationStatus
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
from orkafin.domain.sources import RetrievedSource, SourceType
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
from orkafin.providers.history import (
    BoundedConversationHistoryPolicy,
    ConversationHistoryEntry,
)
from orkafin.providers.validation import ProviderDraftRejected, ProviderOutputValidator


class ResponseGenerationRequest(DomainModel):
    """Trusted orchestration inputs; raw context never crosses into a provider."""

    user_question: ShortText
    context: ResolvedPageContext
    retrieval: RetrievalResult
    intent: ResponseIntent
    response_id: Identifier
    conversation_id: Identifier
    conversation_history: tuple[ConversationHistoryEntry, ...] = Field(default=(), max_length=50)
    refusal_reason_code: LowercaseIdentifier = "permission_denied"


class ResponseGenerationService:
    """Validate every provider result and use deterministic output as the safe fallback."""

    def __init__(
        self,
        *,
        provider: ResponseProvider,
        fallback_provider: ResponseProvider | None = None,
        output_validator: ProviderOutputValidator | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._provider = provider
        self._fallback_provider = fallback_provider or DeterministicResponseProvider()
        self._output_validator = output_validator or ProviderOutputValidator()
        self._clock = clock or (lambda: datetime.now(UTC))

    def generate(self, request: ResponseGenerationRequest) -> AssistantResponse:
        """Return a schema-valid response, falling back on any unsafe provider result."""
        provider_request = self.build_provider_request(request)
        try:
            draft = self._provider.generate(provider_request)
            self._output_validator.validate(draft, provider_request)
        except Exception:  # Providers are untrusted dependencies; no error text is exposed.
            try:
                draft = self._fallback_provider.generate(provider_request)
                self._output_validator.validate(draft, provider_request)
            except Exception:
                draft = ProviderDraft(
                    kind=DraftKind.UNAVAILABLE_INFORMATION,
                    text="Approved information is not available for this request.",
                    template_id="provider_safe_failure",
                )
        return self._to_assistant_response(draft, request, provider_request)

    @staticmethod
    def build_provider_request(request: ResponseGenerationRequest) -> ProviderRequest:
        """Create allowlists while excluding identity, permissions, notes, and hidden fields."""
        context = request.context
        sources = tuple(
            approved
            for source in request.retrieval.sources
            if (approved := _minimize_source(source, request)) is not None
        )
        has_candidate_source = any(
            source.source_type is SourceType.CANDIDATE_SUMMARY for source in sources
        )
        candidate_fields: list[SafeCandidateField] = []
        if (
            request.intent is ResponseIntent.CANDIDATE_SUMMARY
            and has_candidate_source
            and context.candidate_summary is not None
        ):
            for field in context.candidate_summary.visible_fields:
                if field.sensitivity is CandidateFieldSensitivity.STANDARD:
                    candidate_fields.append(
                        SafeCandidateField(
                            label=_bounded_text(field.label, 120),
                            value=_bounded_text(str(field.value.value), 240),
                        )
                    )
        provider_intent = _effective_intent(request.intent, sources)
        constraints = _constraints_for(
            intent=provider_intent,
            sources=sources,
            has_candidate_fields=bool(candidate_fields),
            reason_code=request.refusal_reason_code,
        )
        history = BoundedConversationHistoryPolicy().minimize(request.conversation_history)
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
            history=history,
            intent=provider_intent,
            constraints=constraints,
        )

    @staticmethod
    def _validate_draft(draft: ProviderDraft, request: ProviderRequest) -> None:
        """Compatibility wrapper for the Prompt 13 internal validation hook."""
        ProviderOutputValidator().validate(draft, request)

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


def _minimize_source(
    source: RetrievedSource, request: ResponseGenerationRequest
) -> ApprovedProviderSource | None:
    context = request.context
    if source.app_id != context.app.app_id or not set(source.required_permissions).issubset(
        context.permissions
    ):
        return None
    if source.source_type is SourceType.CANDIDATE_SUMMARY and (
        request.intent is not ResponseIntent.CANDIDATE_SUMMARY
        or context.candidate_summary is None
        or source.source_id != context.candidate_summary.source_adapter_response_id
    ):
        return None
    action_ids: tuple[str, ...] = ()
    if source.source_type is SourceType.ACTION_DEFINITION:
        if (
            source.source_id not in context.available_action_ids
            or source.verification_status is not VerificationStatus.VERIFIED
        ):
            return None
        action_ids = (source.source_id,)
    feature_ids = (source.source_id,) if source.source_type is SourceType.FEATURE_CATALOG else ()
    return ApprovedProviderSource(
        source_id=source.source_id,
        source_type=source.source_type,
        title=source.title,
        excerpt=source.excerpt[:500],
        verification_status=source.verification_status,
        approved_steps=source.instruction_steps[:8],
        feature_ids=feature_ids,
        action_ids=action_ids,
    )


def _constraints_for(
    *,
    intent: ResponseIntent,
    sources: tuple[ApprovedProviderSource, ...],
    has_candidate_fields: bool,
    reason_code: LowercaseIdentifier,
) -> SafeResponseConstraints:
    allowed_feature_ids = tuple(
        sorted({feature_id for source in sources for feature_id in source.feature_ids})
    )
    allowed_action_ids = tuple(
        sorted({action_id for source in sources for action_id in source.action_ids})
    )
    if intent is ResponseIntent.REFUSAL:
        return SafeResponseConstraints(
            allowed_kinds=(DraftKind.REFUSAL,),
            allowed_feature_ids=allowed_feature_ids,
            allowed_action_ids=allowed_action_ids,
            require_citations=False,
            fallback_reason_code=reason_code,
        )
    if not sources:
        return SafeResponseConstraints(
            allowed_kinds=(DraftKind.UNAVAILABLE_INFORMATION,),
            allowed_feature_ids=allowed_feature_ids,
            allowed_action_ids=allowed_action_ids,
            require_citations=False,
            fallback_reason_code="source_missing",
        )
    if intent is ResponseIntent.CANDIDATE_SUMMARY:
        has_candidate_source = any(
            source.source_type is SourceType.CANDIDATE_SUMMARY for source in sources
        )
        return SafeResponseConstraints(
            allowed_kinds=(
                (DraftKind.VERIFIED_FACT, DraftKind.UNAVAILABLE_INFORMATION)
                if has_candidate_source and has_candidate_fields
                else (DraftKind.UNAVAILABLE_INFORMATION,)
            ),
            allowed_feature_ids=allowed_feature_ids,
            allowed_action_ids=allowed_action_ids,
            require_citations=has_candidate_source and has_candidate_fields,
            fallback_reason_code="candidate_summary_unavailable",
        )
    if intent is ResponseIntent.STEP_BY_STEP_HELP and not any(
        source.approved_steps for source in sources
    ):
        return SafeResponseConstraints(
            allowed_kinds=(DraftKind.UNAVAILABLE_INFORMATION,),
            allowed_feature_ids=allowed_feature_ids,
            allowed_action_ids=allowed_action_ids,
            require_citations=False,
            fallback_reason_code="verified_steps_unavailable",
        )
    if intent is ResponseIntent.AVAILABLE_ACTIONS and not allowed_action_ids:
        return SafeResponseConstraints(
            allowed_kinds=(DraftKind.UNAVAILABLE_INFORMATION,),
            allowed_feature_ids=allowed_feature_ids,
            allowed_action_ids=allowed_action_ids,
            require_citations=False,
            fallback_reason_code="authorized_actions_unavailable",
        )
    if intent is ResponseIntent.UNKNOWN:
        return SafeResponseConstraints(
            allowed_kinds=(DraftKind.UNAVAILABLE_INFORMATION,),
            allowed_feature_ids=allowed_feature_ids,
            allowed_action_ids=allowed_action_ids,
            require_citations=False,
            fallback_reason_code="source_missing",
        )
    return SafeResponseConstraints(
        allowed_kinds=(DraftKind.GROUNDED_GUIDANCE,),
        allowed_feature_ids=allowed_feature_ids,
        allowed_action_ids=allowed_action_ids,
        require_citations=True,
        fallback_reason_code="source_missing",
    )


def _effective_intent(
    requested: ResponseIntent, sources: tuple[ApprovedProviderSource, ...]
) -> ResponseIntent:
    grounded_intents = {ResponseIntent.EXPLAIN_PAGE}
    if (
        requested in grounded_intents
        and sources
        and not any(source.verification_status is VerificationStatus.VERIFIED for source in sources)
    ):
        return ResponseIntent.UNCERTAINTY
    return requested


def _bounded_text(value: str, limit: int) -> str:
    return value[:limit].strip()


__all__ = [
    "ProviderDraftRejected",
    "ResponseGenerationRequest",
    "ResponseGenerationService",
]
