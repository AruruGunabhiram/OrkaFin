"""Small repositories that accept domain contracts, never request payloads."""

from __future__ import annotations

from collections.abc import Sequence

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
