"""Explainable recommendation and feedback contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, ClassVar

from pydantic import Field, StringConstraints, model_validator

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
from orkafin.domain.context import WorkspaceRef
from orkafin.domain.identifiers import RequestId, SafeReference

FeedbackComment = Annotated[
    str,
    StringConstraints(min_length=1, max_length=500, strip_whitespace=True, strict=True),
]


class RecommendationKind(StrEnum):
    """Supported V1 recommendation categories."""

    FEATURE = "feature"
    NEXT_STEP = "next_step"
    PRODUCTIVITY_NUDGE = "productivity_nudge"


class RecommendationStatus(StrEnum):
    """Recommendation lifecycle state."""

    PROPOSED = "proposed"
    SHOWN = "shown"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"
    EXPIRED = "expired"


class Recommendation(DomainModel):
    """OrkaFin-owned, rule-derived recommendation tied to approved sources."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.CONFIDENTIAL,
        persistence=PersistencePolicy.ORKAFIN_ALLOWED,
    )

    recommendation_id: Identifier
    rule_id: LowercaseIdentifier
    kind: RecommendationKind
    status: RecommendationStatus
    recipient_user_id: Identifier
    workspace: WorkspaceRef
    title: ShortText
    body: ShortText
    rationale: ShortText
    feature_id: LowercaseIdentifier | None = None
    action_id: LowercaseIdentifier | None = None
    source_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=20)
    source_references: tuple[SafeReference, ...] = Field(default=(), max_length=20)
    created_at: UtcDatetime
    expires_at: UtcDatetime | None = None
    request_id: RequestId

    @model_validator(mode="after")
    def validate_target_and_expiry(self) -> Recommendation:
        if self.feature_id is None and self.action_id is None:
            raise ValueError("recommendation must reference a feature or action")
        if self.expires_at is not None and self.expires_at < self.created_at:
            raise ValueError("expires_at must not precede created_at")
        return self


class RecommendationFeedbackType(StrEnum):
    """Allowlisted user feedback values."""

    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"


class RecommendationFeedback(DomainModel):
    """OrkaFin-owned feedback with optional bounded sensitive commentary."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.CONFIDENTIAL,
        persistence=PersistencePolicy.ORKAFIN_ALLOWED,
        sensitive_fields=(
            SensitiveFieldPolicy(
                field_name="comment",
                classification=DataClassification.CONFIDENTIAL,
                rules=(HandlingRule.MINIMIZE, HandlingRule.REDACT_FROM_LOGS),
            ),
        ),
    )

    feedback_id: Identifier
    recommendation_id: Identifier
    user_id: Identifier
    workspace: WorkspaceRef
    feedback_type: RecommendationFeedbackType
    comment: FeedbackComment | None = None
    submitted_at: UtcDatetime
    request_id: RequestId


class RecommendationPreference(StrEnum):
    """A user-controlled delivery preference for deterministic recommendations."""

    ENABLED = "enabled"
    REDUCED = "reduced"
    DISABLED = "disabled"
