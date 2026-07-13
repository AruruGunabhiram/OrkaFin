"""Grounding-aware assistant response contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, ClassVar, Literal

from pydantic import Field, StringConstraints, model_validator

from orkafin.domain.actions import ActionProposal
from orkafin.domain.base import (
    DataClassification,
    DataOwner,
    DomainModel,
    HandlingRule,
    Identifier,
    LowercaseIdentifier,
    ModelDataPolicy,
    PersistencePolicy,
    SensitiveFieldPolicy,
    ShortText,
    UtcDatetime,
)
from orkafin.domain.identifiers import RequestId
from orkafin.domain.recommendations import Recommendation
from orkafin.domain.sources import RetrievedSource

AssistantText = Annotated[
    str,
    StringConstraints(min_length=1, max_length=8_000, strip_whitespace=True, strict=True),
]


class GroundingStatus(StrEnum):
    """Mechanical grounding state, separate from response wording."""

    VERIFIED = "verified"
    GROUNDED = "grounded"
    NOT_APPLICABLE = "not_applicable"
    UNAVAILABLE = "unavailable"


_CONTENT_POLICY = ModelDataPolicy(
    owner=DataOwner.ORKAFIN,
    classification=DataClassification.CONFIDENTIAL,
    persistence=PersistencePolicy.ORKAFIN_ALLOWED,
    sensitive_fields=(
        SensitiveFieldPolicy(
            field_name="text",
            classification=DataClassification.CONFIDENTIAL,
            rules=(HandlingRule.MINIMIZE, HandlingRule.REDACT_FROM_LOGS),
        ),
    ),
)


class VerifiedFactContent(DomainModel):
    """Fact copied or summarized from a verified application/source payload."""

    data_policy: ClassVar[ModelDataPolicy] = _CONTENT_POLICY

    kind: Literal["verified_fact"] = "verified_fact"
    text: AssistantText
    source_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=20)


class GroundedGuidanceContent(DomainModel):
    """Instructions grounded in approved versioned product knowledge."""

    data_policy: ClassVar[ModelDataPolicy] = _CONTENT_POLICY

    kind: Literal["grounded_guidance"] = "grounded_guidance"
    text: AssistantText
    steps: tuple[ShortText, ...] = Field(default=(), max_length=25)
    source_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=20)


class RecommendationContent(DomainModel):
    """Explainable recommendation referencing its OrkaFin recommendation record."""

    data_policy: ClassVar[ModelDataPolicy] = _CONTENT_POLICY

    kind: Literal["recommendation"] = "recommendation"
    text: AssistantText
    recommendation: Recommendation
    source_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def match_recommendation_sources(self) -> RecommendationContent:
        if not set(self.recommendation.source_ids).issubset(self.source_ids):
            raise ValueError("assistant recommendation must cite recommendation sources")
        return self


class RefusalContent(DomainModel):
    """Safe refusal caused by identity, permission, or policy constraints."""

    data_policy: ClassVar[ModelDataPolicy] = _CONTENT_POLICY

    kind: Literal["refusal"] = "refusal"
    text: AssistantText
    reason_code: LowercaseIdentifier


class UnavailableInformationContent(DomainModel):
    """Honest no-answer response for missing context, source, or dependency."""

    data_policy: ClassVar[ModelDataPolicy] = _CONTENT_POLICY

    kind: Literal["unavailable_information"] = "unavailable_information"
    text: AssistantText
    reason_code: LowercaseIdentifier


class ActionProposalContent(DomainModel):
    """Explicit action preview; it does not claim that execution occurred."""

    data_policy: ClassVar[ModelDataPolicy] = _CONTENT_POLICY

    kind: Literal["action_proposal"] = "action_proposal"
    text: AssistantText
    proposal: ActionProposal
    source_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=20)


AssistantContent = Annotated[
    VerifiedFactContent
    | GroundedGuidanceContent
    | RecommendationContent
    | RefusalContent
    | UnavailableInformationContent
    | ActionProposalContent,
    Field(discriminator="kind"),
]


class AssistantResponse(DomainModel):
    """Versioned response envelope with discriminated content and checked citations."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.CONFIDENTIAL,
        persistence=PersistencePolicy.ORKAFIN_ALLOWED,
        sensitive_fields=(
            SensitiveFieldPolicy(
                field_name="content",
                classification=DataClassification.CONFIDENTIAL,
                rules=(HandlingRule.MINIMIZE, HandlingRule.REDACT_FROM_LOGS),
            ),
            SensitiveFieldPolicy(
                field_name="sources",
                classification=DataClassification.RESTRICTED,
                rules=(HandlingRule.MINIMIZE,),
            ),
        ),
    )
    model_config = {
        **DomainModel.model_config,
        "json_schema_extra": {
            "examples": [
                {
                    "schema_version": "v1",
                    "response_id": "response-001",
                    "conversation_id": "conversation-001",
                    "request_id": "00000000-0000-4000-8000-000000000001",
                    "grounding_status": "unavailable",
                    "content": {
                        "schema_version": "v1",
                        "kind": "unavailable_information",
                        "text": "Approved information is not available for this request.",
                        "reason_code": "source_missing",
                    },
                    "sources": [],
                    "created_at": "2026-07-13T20:00:00Z",
                }
            ]
        },
    }

    response_id: Identifier
    conversation_id: Identifier
    request_id: RequestId
    grounding_status: GroundingStatus
    content: AssistantContent
    sources: tuple[RetrievedSource, ...] = Field(default=(), max_length=20)
    created_at: UtcDatetime

    @model_validator(mode="after")
    def validate_grounding(self) -> AssistantResponse:
        expected_status: dict[str, GroundingStatus] = {
            "verified_fact": GroundingStatus.VERIFIED,
            "grounded_guidance": GroundingStatus.GROUNDED,
            "recommendation": GroundingStatus.GROUNDED,
            "action_proposal": GroundingStatus.GROUNDED,
            "refusal": GroundingStatus.NOT_APPLICABLE,
            "unavailable_information": GroundingStatus.UNAVAILABLE,
        }
        if self.grounding_status is not expected_status[self.content.kind]:
            raise ValueError("grounding status does not match assistant response kind")

        source_ids = [source.source_id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("assistant response sources must be unique")
        cited_ids = getattr(self.content, "source_ids", ())
        if not set(cited_ids).issubset(source_ids):
            raise ValueError("assistant response cites a source that was not supplied")
        if (
            self.content.kind
            in {
                "verified_fact",
                "grounded_guidance",
                "recommendation",
                "action_proposal",
            }
            and not self.sources
        ):
            raise ValueError("grounded assistant response requires at least one source")
        return self
