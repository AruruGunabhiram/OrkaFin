"""Privacy-minimized meaningful user event contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

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
    UtcDatetime,
)
from orkafin.domain.context import SelectedEntityRef, WorkspaceRef
from orkafin.domain.identifiers import CorrelationId, RequestId
from orkafin.domain.metadata import BoundedMetadata


class UserEventType(StrEnum):
    """Allowlisted meaningful events; keystrokes and arbitrary clicks are absent."""

    APP_OPENED = "app_opened"
    PAGE_VIEWED = "page_viewed"
    CANDIDATE_SELECTED = "candidate_selected"
    ASSISTANT_QUERY_SUBMITTED = "assistant_query_submitted"
    RECOMMENDATION_SHOWN = "recommendation_shown"
    RECOMMENDATION_ACCEPTED = "recommendation_accepted"
    RECOMMENDATION_DISMISSED = "recommendation_dismissed"
    FEEDBACK_SUBMITTED = "feedback_submitted"
    ACTION_PROPOSED = "action_proposed"
    ACTION_CONFIRMED = "action_confirmed"
    ACTION_SUCCEEDED = "action_succeeded"
    ACTION_FAILED = "action_failed"


class EventSource(StrEnum):
    """Origin of a meaningful event."""

    ORKAFIN = "orkafin"
    OWNING_APPLICATION = "owning_application"


class UserEvent(DomainModel):
    """OrkaFin-owned, bounded event referencing but never copying app records."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.CONFIDENTIAL,
        persistence=PersistencePolicy.ORKAFIN_ALLOWED,
        sensitive_fields=(
            SensitiveFieldPolicy(
                field_name="metadata",
                classification=DataClassification.CONFIDENTIAL,
                rules=(HandlingRule.MINIMIZE, HandlingRule.REDACT_FROM_LOGS),
            ),
        ),
    )

    event_id: Identifier
    event_type: UserEventType
    source: EventSource
    app_id: LowercaseIdentifier
    actor_user_id: Identifier
    workspace: WorkspaceRef
    entity_ref: SelectedEntityRef | None = None
    metadata: BoundedMetadata
    occurred_at: UtcDatetime
    received_at: UtcDatetime
    request_id: RequestId
    correlation_id: CorrelationId
