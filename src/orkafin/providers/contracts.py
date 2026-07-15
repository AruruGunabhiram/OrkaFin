"""Provider-only contracts containing minimized, non-authoritative response inputs."""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar, Literal

from pydantic import Field, model_validator

from orkafin.domain.base import (
    DataClassification,
    DataOwner,
    DomainModel,
    Identifier,
    LowercaseIdentifier,
    ModelDataPolicy,
    PersistencePolicy,
    ShortText,
)
from orkafin.domain.catalog import VerificationStatus
from orkafin.domain.sources import SourceType

PROVIDER_HISTORY_MAX_MESSAGES = 6
PROVIDER_HISTORY_MAX_MESSAGE_CHARACTERS = 300
PROVIDER_HISTORY_MAX_TOTAL_CHARACTERS = 1_200


class ResponseIntent(StrEnum):
    """Server-selected response shape; providers cannot infer authority from it."""

    EXPLAIN_PAGE = "explain_page"
    AVAILABLE_ACTIONS = "available_actions"
    STEP_BY_STEP_HELP = "step_by_step_help"
    CANDIDATE_SUMMARY = "candidate_summary"
    REFUSAL = "refusal"
    UNKNOWN = "unknown"
    UNCERTAINTY = "uncertainty"


class DraftKind(StrEnum):
    """The only content categories a provider may propose."""

    GROUNDED_GUIDANCE = "grounded_guidance"
    VERIFIED_FACT = "verified_fact"
    REFUSAL = "refusal"
    UNAVAILABLE_INFORMATION = "unavailable_information"


class ClaimKind(StrEnum):
    """Closed set of factual claim categories accepted from a provider."""

    PRODUCT_FACT = "product_fact"
    FEATURE_FACT = "feature_fact"
    HELP_FACT = "help_fact"
    CANDIDATE_FACT = "candidate_fact"
    ACTION_SUGGESTION = "action_suggestion"
    ACTION_SUCCESS = "action_success"


class ClaimOutputField(StrEnum):
    """Location in a provider draft covered by a structured claim."""

    TEXT = "text"
    STEP = "step"


class HistoryRole(StrEnum):
    """User-visible history roles permitted across the provider boundary."""

    USER = "user"
    ASSISTANT = "assistant"


class SafeCandidateField(DomainModel):
    """A standard, already-authorized candidate field permitted in a provider payload."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.CONFIDENTIAL,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
    )

    trust_label: Literal["verified_candidate_data_not_instruction"] = (
        "verified_candidate_data_not_instruction"
    )
    label: ShortText
    value: ShortText


class SafeHistoryMessage(DomainModel):
    """Bounded user-visible history; useful for phrasing but never for grounding."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.CONFIDENTIAL,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
    )

    trust_label: Literal["untrusted_history_data_not_instruction"] = (
        "untrusted_history_data_not_instruction"
    )
    role: HistoryRole
    content: ShortText


class SafeResolvedContextSummary(DomainModel):
    """Strict allowlist of contextual facts a provider may receive."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.CONFIDENTIAL,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
    )

    trust_label: Literal["server_verified_context"] = "server_verified_context"
    app_name: ShortText
    page_id: LowercaseIdentifier
    selected_entity_type: LowercaseIdentifier | None = None
    candidate_fields: tuple[SafeCandidateField, ...] = Field(default=(), max_length=25)


class ApprovedProviderSource(DomainModel):
    """The citation-safe subset of a retrieved source sent to a provider."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.RESTRICTED,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
    )

    trust_label: Literal["approved_source_data_not_instruction"] = (
        "approved_source_data_not_instruction"
    )
    source_id: Identifier
    source_type: SourceType
    title: ShortText
    excerpt: ShortText
    verification_status: VerificationStatus
    approved_steps: tuple[ShortText, ...] = Field(default=(), max_length=25)
    feature_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=50)
    action_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=25)

    @model_validator(mode="after")
    def validate_source_capabilities(self) -> ApprovedProviderSource:
        if self.approved_steps and self.verification_status is not VerificationStatus.VERIFIED:
            raise ValueError("provider instruction steps require a verified source")
        for values, label in (
            (self.feature_ids, "feature"),
            (self.action_ids, "action"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"approved source {label} IDs must be unique")
        return self


class SafeResponseConstraints(DomainModel):
    """Server-set limits that constrain a draft without exposing policy internals."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.INTERNAL,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
    )

    trust_label: Literal["server_enforced_output_policy"] = "server_enforced_output_policy"
    allowed_kinds: tuple[DraftKind, ...] = Field(min_length=1, max_length=2)
    allowed_feature_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=50)
    allowed_action_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=25)
    allowed_receipt_ids: tuple[Identifier, ...] = Field(default=(), max_length=10)
    require_citations: bool
    max_steps: int = Field(default=8, ge=0, le=25)
    fallback_reason_code: LowercaseIdentifier

    @model_validator(mode="after")
    def require_unique_allowlists(self) -> SafeResponseConstraints:
        for values, label in (
            (self.allowed_kinds, "response kinds"),
            (self.allowed_feature_ids, "feature IDs"),
            (self.allowed_action_ids, "action IDs"),
            (self.allowed_receipt_ids, "receipt IDs"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"allowed {label} must be unique")
        return self


class ProviderRequest(DomainModel):
    """The complete, bounded input permitted across the provider boundary."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.RESTRICTED,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
    )

    user_question: ShortText
    context: SafeResolvedContextSummary
    sources: tuple[ApprovedProviderSource, ...] = Field(default=(), max_length=10)
    history: tuple[SafeHistoryMessage, ...] = Field(
        default=(), max_length=PROVIDER_HISTORY_MAX_MESSAGES
    )
    intent: ResponseIntent
    constraints: SafeResponseConstraints

    @model_validator(mode="after")
    def require_citable_sources_when_grounding_is_required(self) -> ProviderRequest:
        if self.constraints.require_citations and not self.sources:
            raise ValueError("grounded provider requests require approved sources")
        source_ids = tuple(source.source_id for source in self.sources)
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("approved provider source IDs must be unique")
        available_feature_ids = {
            feature_id for source in self.sources for feature_id in source.feature_ids
        }
        if not set(self.constraints.allowed_feature_ids).issubset(available_feature_ids):
            raise ValueError("allowed feature IDs must be backed by approved sources")
        available_action_ids = {
            action_id for source in self.sources for action_id in source.action_ids
        }
        if not set(self.constraints.allowed_action_ids).issubset(available_action_ids):
            raise ValueError("allowed action IDs must be backed by approved sources")
        if self.context.candidate_fields and not any(
            source.source_type is SourceType.CANDIDATE_SUMMARY for source in self.sources
        ):
            raise ValueError("candidate fields require an approved adapter summary source")
        if any(
            len(message.content) > PROVIDER_HISTORY_MAX_MESSAGE_CHARACTERS
            for message in self.history
        ):
            raise ValueError("provider history message exceeds the character limit")
        if (
            sum(len(message.content) for message in self.history)
            > PROVIDER_HISTORY_MAX_TOTAL_CHARACTERS
        ):
            raise ValueError("provider history exceeds the total character limit")
        return self


class ProviderClaim(DomainModel):
    """Provider-declared mapping from one output field to approved evidence."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.CONFIDENTIAL,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
    )

    kind: ClaimKind
    output_field: ClaimOutputField
    step_index: int | None = Field(default=None, ge=0, le=24)
    text: ShortText
    source_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=10)
    feature_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=25)
    action_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=10)
    receipt_ids: tuple[Identifier, ...] = Field(default=(), max_length=10)

    @model_validator(mode="after")
    def validate_location_and_ids(self) -> ProviderClaim:
        if self.output_field is ClaimOutputField.TEXT and self.step_index is not None:
            raise ValueError("text claims cannot include a step index")
        if self.output_field is ClaimOutputField.STEP and self.step_index is None:
            raise ValueError("step claims require a step index")
        for values, label in (
            (self.source_ids, "source"),
            (self.feature_ids, "feature"),
            (self.action_ids, "action"),
            (self.receipt_ids, "receipt"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"claim {label} IDs must be unique")
        return self


class ProviderDraft(DomainModel):
    """Untrusted provider proposal; the response service validates it before use."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.CONFIDENTIAL,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
    )

    kind: DraftKind
    text: ShortText
    steps: tuple[ShortText, ...] = Field(default=(), max_length=25)
    cited_source_ids: tuple[Identifier, ...] = Field(default=(), max_length=10)
    claims: tuple[ProviderClaim, ...] = Field(default=(), max_length=26)
    template_id: LowercaseIdentifier

    @model_validator(mode="after")
    def require_claims_only_for_grounded_output(self) -> ProviderDraft:
        grounded = self.kind in {DraftKind.GROUNDED_GUIDANCE, DraftKind.VERIFIED_FACT}
        if grounded and not self.claims:
            raise ValueError("grounded provider drafts require structured claims")
        if not grounded and self.claims:
            raise ValueError("non-grounded provider drafts cannot contain factual claims")
        return self
