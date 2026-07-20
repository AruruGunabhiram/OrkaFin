"""Typed relational models for the approved OrkaFin persistence boundary.

No model in this module represents a candidate or an OrkaATS record.  Candidate
identifiers are limited to ``target_*`` and ``entity_*`` reference columns.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from orkafin.infrastructure.database.base import Base

JsonObject = dict[str, Any]


class ConversationModel(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'closed')", name="ck_conversations_status"),
        Index("ix_conversations_owner_workspace", "owner_user_id", "workspace_id"),
    )

    conversation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(8), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    workspace_app_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    messages: Mapped[list[MessageModel]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class MessageModel(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="ck_messages_role"),
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
    )

    message_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(8), nullable=False)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.conversation_id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    conversation: Mapped[ConversationModel] = relationship(back_populates="messages")


class UserEventModel(Base):
    __tablename__ = "user_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('app_opened', 'page_viewed', 'candidate_selected', "
            "'assistant_query_submitted', 'recommendation_shown', 'recommendation_accepted', "
            "'recommendation_dismissed', 'feedback_submitted', 'action_proposed', "
            "'action_confirmed', 'action_succeeded', 'action_failed')",
            name="ck_user_events_type",
        ),
        CheckConstraint(
            "source IN ('orkafin', 'owning_application')", name="ck_user_events_source"
        ),
        Index("ix_user_events_actor_occurred", "actor_user_id", "occurred_at"),
        Index("ix_user_events_workspace_occurred", "workspace_id", "occurred_at"),
    )

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(8), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    app_id: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    workspace_app_id: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_app_id: Mapped[str | None] = mapped_column(String(64))
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    metadata_json: Mapped[JsonObject] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)


class RecommendationModel(Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('feature', 'next_step', 'productivity_nudge')", name="ck_recommendations_kind"
        ),
        CheckConstraint(
            "status IN ('proposed', 'shown', 'accepted', 'dismissed', 'expired')",
            name="ck_recommendations_status",
        ),
        Index("ix_recommendations_recipient_created", "recipient_user_id", "created_at"),
    )

    recommendation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(8), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    recipient_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    workspace_app_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(String(500), nullable=False)
    rationale: Mapped[str] = mapped_column(String(500), nullable=False)
    feature_id: Mapped[str | None] = mapped_column(String(64))
    action_id: Mapped[str | None] = mapped_column(String(64))
    source_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    source_references: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    impressions: Mapped[list[RecommendationImpressionModel]] = relationship(
        back_populates="recommendation", cascade="all, delete-orphan"
    )
    feedback: Mapped[list[RecommendationFeedbackModel]] = relationship(
        back_populates="recommendation", cascade="all, delete-orphan"
    )


class RecommendationImpressionModel(Base):
    __tablename__ = "recommendation_impressions"
    __table_args__ = (
        Index(
            "ix_recommendation_impressions_recommendation_shown", "recommendation_id", "shown_at"
        ),
    )

    impression_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    recommendation_id: Mapped[str] = mapped_column(
        ForeignKey("recommendations.recommendation_id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    shown_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    recommendation: Mapped[RecommendationModel] = relationship(back_populates="impressions")


class RecommendationFeedbackModel(Base):
    __tablename__ = "recommendation_feedback"
    __table_args__ = (
        CheckConstraint(
            "feedback_type IN ('helpful', 'not_helpful', 'accepted', 'dismissed')",
            name="ck_recommendation_feedback_type",
        ),
        Index("ix_recommendation_feedback_recommendation", "recommendation_id"),
    )

    feedback_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(8), nullable=False)
    recommendation_id: Mapped[str] = mapped_column(
        ForeignKey("recommendations.recommendation_id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    workspace_app_id: Mapped[str] = mapped_column(String(64), nullable=False)
    feedback_type: Mapped[str] = mapped_column(String(16), nullable=False)
    comment: Mapped[str | None] = mapped_column(String(500))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    recommendation: Mapped[RecommendationModel] = relationship(back_populates="feedback")


class RecommendationPreferenceModel(Base):
    __tablename__ = "recommendation_preferences"
    __table_args__ = (
        CheckConstraint(
            "preference IN ('enabled', 'reduced', 'disabled')",
            name="ck_recommendation_preferences_preference",
        ),
    )

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_app_id: Mapped[str] = mapped_column(String(64), nullable=False)
    preference: Mapped[str] = mapped_column(String(16), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ActionProposalModel(Base):
    __tablename__ = "action_proposals"
    __table_args__ = (
        CheckConstraint(
            "status IN ('proposed', 'confirmed', 'cancelled', 'expired', 'executed', 'failed')",
            name="ck_action_proposals_status",
        ),
        Index("ix_action_proposals_user_created", "proposed_by_user_id", "created_at"),
    )

    proposal_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(8), nullable=False)
    action_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action_version: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_app_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    proposed_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    workspace_app_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_app_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters_json: Mapped[list[JsonObject]] = mapped_column(JSON, nullable=False)
    parameter_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    preview_json: Mapped[JsonObject] = mapped_column(JSON, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    confirmations: Mapped[list[ActionConfirmationModel]] = relationship(back_populates="proposal")
    executions: Mapped[list[ActionExecutionModel]] = relationship(back_populates="proposal")


class ActionConfirmationModel(Base):
    __tablename__ = "action_confirmations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('issued', 'accepted', 'rejected', 'expired', 'consumed')",
            name="ck_action_confirmations_status",
        ),
        Index("ix_action_confirmations_proposal", "proposal_id"),
        UniqueConstraint("proposal_id", name="uq_action_confirmations_proposal_id"),
        UniqueConstraint("confirmation_secret_hash", name="uq_action_confirmations_secret_hash"),
    )

    confirmation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(8), nullable=False)
    proposal_id: Mapped[str] = mapped_column(
        ForeignKey("action_proposals.proposal_id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    bound_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    bound_workspace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    parameter_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    confirmation_secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    proposal: Mapped[ActionProposalModel] = relationship(back_populates="confirmations")


class ActionExecutionModel(Base):
    __tablename__ = "action_executions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('succeeded', 'failed', 'unknown', 'conflict', 'rejected')",
            name="ck_action_executions_status",
        ),
        Index("ix_action_executions_proposal", "proposal_id"),
        UniqueConstraint("proposal_id", name="uq_action_executions_proposal_id"),
    )

    execution_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(8), nullable=False)
    proposal_id: Mapped[str] = mapped_column(
        ForeignKey("action_proposals.proposal_id", ondelete="RESTRICT"), nullable=False
    )
    action_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action_version: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_app_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_app_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    adapter_receipt_json: Mapped[JsonObject | None] = mapped_column(JSON)
    safe_message: Mapped[str] = mapped_column(String(500), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    proposal: Mapped[ActionProposalModel] = relationship(back_populates="executions")


class AuditRecordModel(Base):
    __tablename__ = "audit_records"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('identity_verified', 'identity_denied', 'candidate_read', "
            "'permission_denied', 'action_permission_checked', 'action_proposed', "
            "'action_confirmation_issued', "
            "'action_confirmed', 'action_confirmation_rejected', 'action_confirmation_expired', "
            "'action_tampering_rejected', 'action_execution_attempted', "
            "'action_adapter_requested', 'action_execution_succeeded', "
            "'action_execution_failed', 'action_execution_unknown', 'action_final_result')",
            name="ck_audit_records_event_type",
        ),
        CheckConstraint(
            "outcome IN ('allowed', 'denied', 'succeeded', 'failed', 'unknown')",
            name="ck_audit_records_outcome",
        ),
        Index("ix_audit_records_occurred", "occurred_at"),
        Index("ix_audit_records_correlation", "correlation_id"),
    )

    audit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(8), nullable=False)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(String(64))
    workspace_id: Mapped[str | None] = mapped_column(String(64))
    app_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_app_id: Mapped[str | None] = mapped_column(String(64))
    target_entity_type: Mapped[str | None] = mapped_column(String(64))
    target_entity_id: Mapped[str | None] = mapped_column(String(64))
    action_id: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    details_json: Mapped[JsonObject] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
