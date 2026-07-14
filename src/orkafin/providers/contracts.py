"""Provider-only contracts containing minimized, non-authoritative response inputs."""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

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


class SafeCandidateField(DomainModel):
    """A standard, already-authorized candidate field permitted in a provider payload."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.CONFIDENTIAL,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
    )

    label: ShortText
    value: ShortText


class SafeResolvedContextSummary(DomainModel):
    """Strict allowlist of contextual facts a provider may receive."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.CONFIDENTIAL,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
    )

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

    source_id: Identifier
    title: ShortText
    excerpt: ShortText


class SafeResponseConstraints(DomainModel):
    """Server-set limits that constrain a draft without exposing policy internals."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.INTERNAL,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
    )

    allowed_kinds: tuple[DraftKind, ...] = Field(min_length=1, max_length=2)
    require_citations: bool
    max_steps: int = Field(default=8, ge=0, le=25)
    fallback_reason_code: LowercaseIdentifier


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
    intent: ResponseIntent
    constraints: SafeResponseConstraints

    @model_validator(mode="after")
    def require_citable_sources_when_grounding_is_required(self) -> ProviderRequest:
        if self.constraints.require_citations and not self.sources:
            raise ValueError("grounded provider requests require approved sources")
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
    template_id: LowercaseIdentifier
