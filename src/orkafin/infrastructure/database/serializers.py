"""Explicit persistence serialization for validated OrkaFin domain objects.

These functions deliberately do not accept request dictionaries.  The domain
models have already enforced field bounds, UTC timestamps, metadata policy, and
the absence of browser-only or candidate-summary fields before this boundary.
"""

from __future__ import annotations

import json
from typing import Any, cast

from pydantic import TypeAdapter

from orkafin.domain.actions import (
    ActionConfirmation,
    ActionExecutionResult,
    ActionParameter,
    ActionPreview,
    ActionProposal,
)
from orkafin.domain.audit import AuditRecord
from orkafin.domain.base import SchemaVersion
from orkafin.domain.conversations import Conversation, Message
from orkafin.domain.events import UserEvent
from orkafin.domain.recommendations import Recommendation, RecommendationFeedback
from orkafin.infrastructure.database.models import (
    ActionConfirmationModel,
    ActionExecutionModel,
    ActionProposalModel,
    AuditRecordModel,
    ConversationModel,
    MessageModel,
    RecommendationFeedbackModel,
    RecommendationModel,
    UserEventModel,
)


def _json(value: Any) -> Any:
    """Use Pydantic's validated JSON mode for bounded JSON columns."""
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


def _target_values(target: Any | None) -> tuple[str | None, str | None, str | None]:
    if target is None:
        return None, None, None
    return target.app_id, target.entity_type, target.entity_id


def conversation_model(value: Conversation) -> ConversationModel:
    return ConversationModel(
        conversation_id=value.conversation_id,
        schema_version=value.schema_version,
        owner_user_id=value.owner_user_id,
        workspace_id=value.workspace.workspace_id,
        workspace_app_id=value.workspace.app_id,
        title=value.title,
        status=value.status.value,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def conversation_domain(value: ConversationModel) -> Conversation:
    from orkafin.domain.context import WorkspaceRef
    from orkafin.domain.conversations import ConversationStatus

    return Conversation(
        schema_version=cast(SchemaVersion, value.schema_version),
        conversation_id=value.conversation_id,
        owner_user_id=value.owner_user_id,
        workspace=WorkspaceRef(workspace_id=value.workspace_id, app_id=value.workspace_app_id),
        title=value.title,
        status=ConversationStatus(value.status),
        created_at=_utc(value.created_at),
        updated_at=_utc(value.updated_at),
    )


def message_model(value: Message) -> MessageModel:
    return MessageModel(
        message_id=value.message_id,
        schema_version=value.schema_version,
        conversation_id=value.conversation_id,
        role=value.role.value,
        content=value.content,
        source_ids=list(value.source_ids),
        request_id=value.request_id.root,
        created_at=value.created_at,
    )


def message_domain(value: MessageModel) -> Message:
    from orkafin.domain.conversations import MessageRole
    from orkafin.domain.identifiers import RequestId

    return Message(
        schema_version=cast(SchemaVersion, value.schema_version),
        message_id=value.message_id,
        conversation_id=value.conversation_id,
        role=MessageRole(value.role),
        content=value.content,
        source_ids=tuple(value.source_ids),
        request_id=RequestId(root=value.request_id),
        created_at=_utc(value.created_at),
    )


def user_event_model(value: UserEvent) -> UserEventModel:
    entity_app_id, entity_type, entity_id = _target_values(value.entity_ref)
    return UserEventModel(
        event_id=value.event_id,
        schema_version=value.schema_version,
        event_type=value.event_type.value,
        source=value.source.value,
        app_id=value.app_id,
        actor_user_id=value.actor_user_id,
        workspace_id=value.workspace.workspace_id,
        workspace_app_id=value.workspace.app_id,
        entity_app_id=entity_app_id,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_json=_json(value.metadata),
        occurred_at=value.occurred_at,
        received_at=value.received_at,
        request_id=value.request_id.root,
        correlation_id=value.correlation_id.root,
    )


def recommendation_model(value: Recommendation) -> RecommendationModel:
    return RecommendationModel(
        recommendation_id=value.recommendation_id,
        schema_version=value.schema_version,
        rule_id=value.rule_id,
        kind=value.kind.value,
        status=value.status.value,
        recipient_user_id=value.recipient_user_id,
        workspace_id=value.workspace.workspace_id,
        workspace_app_id=value.workspace.app_id,
        title=value.title,
        body=value.body,
        rationale=value.rationale,
        feature_id=value.feature_id,
        action_id=value.action_id,
        source_ids=list(value.source_ids),
        source_references=[reference.root for reference in value.source_references],
        created_at=value.created_at,
        expires_at=value.expires_at,
        request_id=value.request_id.root,
    )


def recommendation_domain(value: RecommendationModel) -> Recommendation:
    from orkafin.domain.context import WorkspaceRef
    from orkafin.domain.identifiers import RequestId, SafeReference
    from orkafin.domain.recommendations import RecommendationKind, RecommendationStatus

    return Recommendation(
        schema_version=cast(SchemaVersion, value.schema_version),
        recommendation_id=value.recommendation_id,
        rule_id=value.rule_id,
        kind=RecommendationKind(value.kind),
        status=RecommendationStatus(value.status),
        recipient_user_id=value.recipient_user_id,
        workspace=WorkspaceRef(workspace_id=value.workspace_id, app_id=value.workspace_app_id),
        title=value.title,
        body=value.body,
        rationale=value.rationale,
        feature_id=value.feature_id,
        action_id=value.action_id,
        source_ids=tuple(value.source_ids),
        source_references=tuple(SafeReference(root=item) for item in value.source_references),
        created_at=_utc(value.created_at),
        expires_at=_utc(value.expires_at) if value.expires_at is not None else None,
        request_id=RequestId(root=value.request_id),
    )


def recommendation_feedback_model(value: RecommendationFeedback) -> RecommendationFeedbackModel:
    return RecommendationFeedbackModel(
        feedback_id=value.feedback_id,
        schema_version=value.schema_version,
        recommendation_id=value.recommendation_id,
        user_id=value.user_id,
        workspace_id=value.workspace.workspace_id,
        workspace_app_id=value.workspace.app_id,
        feedback_type=value.feedback_type.value,
        comment=value.comment,
        submitted_at=value.submitted_at,
        request_id=value.request_id.root,
    )


def action_proposal_model(value: ActionProposal) -> ActionProposalModel:
    return ActionProposalModel(
        proposal_id=value.proposal_id,
        schema_version=value.schema_version,
        action_id=value.action_id,
        action_version=value.action_version,
        owner_app_id=value.owner_app_id,
        status=value.status.value,
        proposed_by_user_id=value.proposed_by_user_id,
        workspace_id=value.workspace.workspace_id,
        workspace_app_id=value.workspace.app_id,
        target_app_id=value.target.app_id,
        target_entity_type=value.target.entity_type,
        target_entity_id=value.target.entity_id,
        parameters_json=[_json(parameter) for parameter in value.parameters],
        parameter_hash=value.parameter_hash.root,
        preview_json=_json(value.preview),
        idempotency_key=value.idempotency_key.root,
        request_id=value.request_id.root,
        created_at=value.created_at,
        expires_at=value.expires_at,
    )


def action_proposal_domain(value: ActionProposalModel) -> ActionProposal:
    from orkafin.domain.actions import ActionProposalStatus
    from orkafin.domain.context import SelectedEntityRef, WorkspaceRef
    from orkafin.domain.identifiers import IdempotencyKey, RequestId, Sha256Digest

    parameters = TypeAdapter(tuple[ActionParameter, ...]).validate_json(
        json.dumps(value.parameters_json)
    )
    preview = ActionPreview.model_validate_json(json.dumps(value.preview_json))
    return ActionProposal(
        schema_version=cast(SchemaVersion, value.schema_version),
        proposal_id=value.proposal_id,
        action_id=value.action_id,
        action_version=value.action_version,
        owner_app_id=value.owner_app_id,
        status=ActionProposalStatus(value.status),
        proposed_by_user_id=value.proposed_by_user_id,
        workspace=WorkspaceRef(
            workspace_id=value.workspace_id,
            app_id=value.workspace_app_id,
        ),
        target=SelectedEntityRef(
            app_id=value.target_app_id,
            entity_type=value.target_entity_type,
            entity_id=value.target_entity_id,
        ),
        parameters=parameters,
        parameter_hash=Sha256Digest(root=value.parameter_hash),
        preview=preview,
        idempotency_key=IdempotencyKey(root=value.idempotency_key),
        request_id=RequestId(root=value.request_id),
        created_at=_utc(value.created_at),
        expires_at=_utc(value.expires_at),
    )


def action_confirmation_model(value: ActionConfirmation) -> ActionConfirmationModel:
    return ActionConfirmationModel(
        confirmation_id=value.confirmation_id,
        schema_version=value.schema_version,
        proposal_id=value.proposal_id,
        status=value.status.value,
        bound_user_id=value.bound_user_id,
        bound_workspace_id=value.bound_workspace_id,
        parameter_hash=value.parameter_hash.root,
        confirmation_secret_hash=value.confirmation_secret_hash.root,
        issued_at=value.issued_at,
        expires_at=value.expires_at,
        responded_at=value.responded_at,
    )


def action_confirmation_domain(value: ActionConfirmationModel) -> ActionConfirmation:
    from orkafin.domain.actions import ActionConfirmationStatus
    from orkafin.domain.identifiers import Sha256Digest

    return ActionConfirmation(
        schema_version=cast(SchemaVersion, value.schema_version),
        confirmation_id=value.confirmation_id,
        proposal_id=value.proposal_id,
        status=ActionConfirmationStatus(value.status),
        bound_user_id=value.bound_user_id,
        bound_workspace_id=value.bound_workspace_id,
        parameter_hash=Sha256Digest(root=value.parameter_hash),
        confirmation_secret_hash=Sha256Digest(root=value.confirmation_secret_hash),
        issued_at=_utc(value.issued_at),
        expires_at=_utc(value.expires_at),
        responded_at=_utc(value.responded_at) if value.responded_at is not None else None,
    )


def action_execution_model(value: ActionExecutionResult) -> ActionExecutionModel:
    return ActionExecutionModel(
        execution_id=value.execution_id,
        schema_version=value.schema_version,
        proposal_id=value.proposal_id,
        action_id=value.action_id,
        action_version=value.action_version,
        owner_app_id=value.owner_app_id,
        target_app_id=value.target.app_id,
        target_entity_type=value.target.entity_type,
        target_entity_id=value.target.entity_id,
        status=value.status.value,
        request_id=value.request_id.root,
        idempotency_key=value.idempotency_key.root,
        adapter_receipt_json=_json(value.adapter_receipt) if value.adapter_receipt else None,
        safe_message=value.safe_message,
        completed_at=value.completed_at,
    )


def audit_record_model(value: AuditRecord) -> AuditRecordModel:
    target_app_id, target_entity_type, target_entity_id = _target_values(value.target)
    return AuditRecordModel(
        audit_id=value.audit_id,
        schema_version=value.schema_version,
        event_type=value.event_type.value,
        outcome=value.outcome.value,
        actor_user_id=value.actor_user_id,
        workspace_id=value.workspace_id,
        app_id=value.app_id,
        target_app_id=target_app_id,
        target_entity_type=target_entity_type,
        target_entity_id=target_entity_id,
        action_id=value.action_id,
        request_id=value.request_id.root,
        correlation_id=value.correlation_id.root,
        details_json=_json(value.details),
        occurred_at=value.occurred_at,
    )


def _utc(value: Any) -> Any:
    """SQLite may return naive values despite a timezone-aware SQLAlchemy type."""
    from datetime import UTC

    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
