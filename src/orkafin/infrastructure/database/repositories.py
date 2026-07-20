"""Small repositories that accept domain contracts, never request payloads."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from orkafin.domain.actions import ActionConfirmation, ActionExecutionResult, ActionProposal
from orkafin.domain.audit import AuditRecord
from orkafin.domain.conversations import Conversation, Message
from orkafin.domain.events import UserEvent
from orkafin.domain.recommendations import Recommendation, RecommendationFeedback
from orkafin.infrastructure.database.models import (
    AuditRecordModel,
    ConversationModel,
    MessageModel,
    RecommendationFeedbackModel,
    RecommendationImpressionModel,
    RecommendationModel,
    RecommendationPreferenceModel,
    UserEventModel,
)
from orkafin.infrastructure.database.serializers import (
    action_confirmation_model,
    action_execution_model,
    action_proposal_model,
    audit_record_model,
    conversation_domain,
    conversation_model,
    message_domain,
    message_model,
    recommendation_domain,
    recommendation_feedback_model,
    recommendation_model,
    user_event_model,
)


class OrkaFinRepository:
    """Transaction-bound persistence access for only the approved record set."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add_conversation(self, value: Conversation) -> None:
        self._session.add(conversation_model(value))

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        stored = self._session.get(ConversationModel, conversation_id)
        return conversation_domain(stored) if stored else None

    def update_conversation(self, value: Conversation) -> None:
        stored = self._session.get(ConversationModel, value.conversation_id)
        if stored is None:
            raise KeyError(f"conversation not found: {value.conversation_id}")
        stored.title = value.title
        stored.status = value.status.value
        stored.updated_at = value.updated_at

    def add_message(self, value: Message) -> None:
        self._session.add(message_model(value))

    def list_messages(self, conversation_id: str) -> Sequence[Message]:
        rows = self._session.scalars(
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at, MessageModel.message_id)
        )
        return tuple(message_domain(row) for row in rows)

    def append_user_event(self, value: UserEvent) -> None:
        self._session.add(user_event_model(value))

    def add_recommendation(self, value: Recommendation) -> None:
        self._session.add(recommendation_model(value))

    def add_recommendation_feedback(self, value: RecommendationFeedback) -> None:
        self._session.add(recommendation_feedback_model(value))

    def get_recommendation(self, recommendation_id: str) -> Recommendation | None:
        stored = self._session.get(RecommendationModel, recommendation_id)
        return recommendation_domain(stored) if stored is not None else None

    def get_recommendation_model(self, recommendation_id: str) -> RecommendationModel | None:
        return self._session.get(RecommendationModel, recommendation_id)

    def list_recommendations_for_rule(
        self, *, rule_id: str, user_id: str, workspace_id: str
    ) -> Sequence[RecommendationModel]:
        return tuple(
            self._session.scalars(
                select(RecommendationModel)
                .where(
                    RecommendationModel.rule_id == rule_id,
                    RecommendationModel.recipient_user_id == user_id,
                    RecommendationModel.workspace_id == workspace_id,
                )
                .order_by(RecommendationModel.created_at.desc())
            )
        )

    def add_recommendation_impression(
        self,
        *,
        impression_id: str,
        recommendation_id: str,
        user_id: str,
        workspace_id: str,
        request_id: str,
        shown_at: datetime,
    ) -> None:
        self._session.add(
            RecommendationImpressionModel(
                impression_id=impression_id,
                recommendation_id=recommendation_id,
                user_id=user_id,
                workspace_id=workspace_id,
                request_id=request_id,
                shown_at=shown_at,
            )
        )

    def latest_impression_at(
        self, *, rule_id: str, user_id: str, workspace_id: str
    ) -> datetime | None:
        return self._session.scalar(
            select(RecommendationImpressionModel.shown_at)
            .join(RecommendationModel)
            .where(
                RecommendationModel.rule_id == rule_id,
                RecommendationImpressionModel.user_id == user_id,
                RecommendationImpressionModel.workspace_id == workspace_id,
            )
            .order_by(RecommendationImpressionModel.shown_at.desc())
            .limit(1)
        )

    def has_feedback_type(
        self, *, rule_id: str, user_id: str, workspace_id: str, feedback_type: str
    ) -> bool:
        return (
            self._session.scalar(
                select(RecommendationFeedbackModel.feedback_id)
                .join(RecommendationModel)
                .where(
                    RecommendationModel.rule_id == rule_id,
                    RecommendationFeedbackModel.user_id == user_id,
                    RecommendationFeedbackModel.workspace_id == workspace_id,
                    RecommendationFeedbackModel.feedback_type == feedback_type,
                )
                .limit(1)
            )
            is not None
        )

    def get_recommendation_preference(self, *, user_id: str, workspace_id: str) -> str | None:
        stored = self._session.get(RecommendationPreferenceModel, (user_id, workspace_id))
        return stored.preference if stored is not None else None

    def set_recommendation_preference(
        self,
        *,
        user_id: str,
        workspace_id: str,
        workspace_app_id: str,
        preference: str,
        updated_at: datetime,
    ) -> None:
        stored = self._session.get(RecommendationPreferenceModel, (user_id, workspace_id))
        if stored is None:
            self._session.add(
                RecommendationPreferenceModel(
                    user_id=user_id,
                    workspace_id=workspace_id,
                    workspace_app_id=workspace_app_id,
                    preference=preference,
                    updated_at=updated_at,
                )
            )
            return
        stored.preference = preference
        stored.workspace_app_id = workspace_app_id
        stored.updated_at = updated_at

    def list_recent_user_event_types(
        self, *, user_id: str, workspace_id: str, occurred_after: datetime
    ) -> tuple[str, ...]:
        return tuple(
            self._session.scalars(
                select(UserEventModel.event_type)
                .where(
                    UserEventModel.actor_user_id == user_id,
                    UserEventModel.workspace_id == workspace_id,
                    UserEventModel.occurred_at >= occurred_after,
                )
                .order_by(UserEventModel.occurred_at.desc())
            )
        )

    def add_action_proposal(self, value: ActionProposal) -> None:
        self._session.add(action_proposal_model(value))

    def add_action_confirmation(self, value: ActionConfirmation) -> None:
        self._session.add(action_confirmation_model(value))

    def add_action_execution(self, value: ActionExecutionResult) -> None:
        self._session.add(action_execution_model(value))

    def append_audit_record(self, value: AuditRecord) -> None:
        """Append a validated audit fact; there is intentionally no update/delete API."""
        self._session.add(audit_record_model(value))

    def list_audit_records(self) -> Sequence[AuditRecordModel]:
        """Expose stored audit rows for internal review without an edit surface."""
        return tuple(
            self._session.scalars(
                select(AuditRecordModel).order_by(
                    AuditRecordModel.occurred_at, AuditRecordModel.audit_id
                )
            )
        )
