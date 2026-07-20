"""Append-oriented, privacy-minimized audit record contract."""

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
from orkafin.domain.context import SelectedEntityRef
from orkafin.domain.identifiers import CorrelationId, RequestId
from orkafin.domain.metadata import BoundedMetadata


class AuditEventType(StrEnum):
    """Security-relevant event classes supported by the V1 contract."""

    IDENTITY_VERIFIED = "identity_verified"
    IDENTITY_DENIED = "identity_denied"
    CANDIDATE_READ = "candidate_read"
    PERMISSION_DENIED = "permission_denied"
    ACTION_PERMISSION_CHECKED = "action_permission_checked"
    ACTION_PROPOSED = "action_proposed"
    ACTION_CONFIRMATION_ISSUED = "action_confirmation_issued"
    ACTION_CONFIRMED = "action_confirmed"
    ACTION_CONFIRMATION_REJECTED = "action_confirmation_rejected"
    ACTION_CONFIRMATION_EXPIRED = "action_confirmation_expired"
    ACTION_TAMPERING_REJECTED = "action_tampering_rejected"
    ACTION_EXECUTION_ATTEMPTED = "action_execution_attempted"
    ACTION_ADAPTER_REQUESTED = "action_adapter_requested"
    ACTION_EXECUTION_SUCCEEDED = "action_execution_succeeded"
    ACTION_EXECUTION_FAILED = "action_execution_failed"
    ACTION_EXECUTION_UNKNOWN = "action_execution_unknown"
    ACTION_FINAL_RESULT = "action_final_result"


class AuditOutcome(StrEnum):
    """Safe outcome classification without raw exception content."""

    ALLOWED = "allowed"
    DENIED = "denied"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNKNOWN = "unknown"


class AuditRecord(DomainModel):
    """Immutable structured audit fact; persistence must expose append-only operations."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.RESTRICTED,
        persistence=PersistencePolicy.ORKAFIN_ALLOWED,
        sensitive_fields=(
            SensitiveFieldPolicy(
                field_name="actor_user_id",
                classification=DataClassification.RESTRICTED,
                rules=(HandlingRule.REDACT_FROM_LOGS, HandlingRule.INTERNAL_ONLY),
            ),
            SensitiveFieldPolicy(
                field_name="target",
                classification=DataClassification.RESTRICTED,
                rules=(HandlingRule.REDACT_FROM_LOGS, HandlingRule.MINIMIZE),
            ),
            SensitiveFieldPolicy(
                field_name="details",
                classification=DataClassification.CONFIDENTIAL,
                rules=(HandlingRule.MINIMIZE, HandlingRule.REDACT_FROM_LOGS),
            ),
        ),
    )

    audit_id: Identifier
    event_type: AuditEventType
    outcome: AuditOutcome
    actor_user_id: Identifier | None = None
    workspace_id: Identifier | None = None
    app_id: LowercaseIdentifier
    target: SelectedEntityRef | None = None
    action_id: LowercaseIdentifier | None = None
    request_id: RequestId
    correlation_id: CorrelationId
    details: BoundedMetadata
    occurred_at: UtcDatetime
