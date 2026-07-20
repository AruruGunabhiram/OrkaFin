"""Persistence regression tests for the Prompt 5 OrkaFin-only database."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from orkafin.domain.actions import (
    ActionConfirmation,
    ActionConfirmationStatus,
    ActionExecutionResult,
    ActionExecutionStatus,
    ActionPreview,
    ActionPreviewChange,
    ActionProposal,
    ActionProposalStatus,
    DateActionParameter,
)
from orkafin.domain.audit import AuditEventType, AuditOutcome, AuditRecord
from orkafin.domain.context import SelectedEntityRef, WorkspaceRef
from orkafin.domain.conversations import Conversation, ConversationStatus, Message, MessageRole
from orkafin.domain.events import EventSource, UserEvent, UserEventType
from orkafin.domain.identifiers import CorrelationId, IdempotencyKey, RequestId, Sha256Digest
from orkafin.domain.metadata import BoundedMetadata
from orkafin.domain.recommendations import (
    Recommendation,
    RecommendationFeedback,
    RecommendationFeedbackType,
    RecommendationKind,
    RecommendationStatus,
)
from orkafin.infrastructure.database.models import AuditRecordModel, MessageModel
from orkafin.infrastructure.database.repositories import OrkaFinRepository
from orkafin.infrastructure.database.serializers import action_confirmation_model, user_event_model
from orkafin.infrastructure.database.session import Database

NOW = datetime(2026, 7, 13, 20, 0, tzinfo=UTC)
LATER = NOW + timedelta(minutes=5)
REQUEST_ID = RequestId(root="00000000-0000-4000-8000-000000000001")
CORRELATION_ID = CorrelationId(root="00000000-0000-4000-8000-000000000002")
HASH = Sha256Digest(root="a" * 64)


def workspace() -> WorkspaceRef:
    return WorkspaceRef(workspace_id="workspace_001", app_id="orka_ats")


def target() -> SelectedEntityRef:
    return SelectedEntityRef(app_id="orka_ats", entity_type="candidate", entity_id="CAND-1001")


def conversation(*, status: ConversationStatus = ConversationStatus.ACTIVE) -> Conversation:
    return Conversation(
        conversation_id="conversation-001",
        owner_user_id="user_001",
        workspace=workspace(),
        title="Candidate workflow guidance",
        status=status,
        created_at=NOW,
        updated_at=LATER if status is ConversationStatus.CLOSED else NOW,
    )


def recommendation() -> Recommendation:
    return Recommendation(
        recommendation_id="recommendation-001",
        rule_id="show_candidate_pipeline",
        kind=RecommendationKind.FEATURE,
        status=RecommendationStatus.SHOWN,
        recipient_user_id="user_001",
        workspace=workspace(),
        title="Try the candidate pipeline",
        body="The pipeline may make stage review easier.",
        rationale="The current page is linked to this feature.",
        feature_id="candidate_pipeline",
        source_ids=("help_candidate_pipeline",),
        created_at=NOW,
        request_id=REQUEST_ID,
    )


def proposal() -> ActionProposal:
    return ActionProposal(
        proposal_id="proposal-001",
        action_id="candidate.update_start_date",
        action_version="1.0.0",
        owner_app_id="orka_ats",
        status=ActionProposalStatus.PROPOSED,
        proposed_by_user_id="user_001",
        workspace=workspace(),
        target=target(),
        parameters=(DateActionParameter(parameter_id="start_date", value=date(2026, 8, 1)),),
        parameter_hash=HASH,
        preview=ActionPreview(
            summary="Update the candidate start date.",
            changes=(ActionPreviewChange(field_label="Start date", new_value="2026-08-01"),),
            reversible=True,
        ),
        idempotency_key=IdempotencyKey(root="proposal-key-0001"),
        request_id=REQUEST_ID,
        created_at=NOW,
        expires_at=LATER,
    )


def audit_record() -> AuditRecord:
    return AuditRecord(
        audit_id="audit-001",
        event_type=AuditEventType.CANDIDATE_READ,
        outcome=AuditOutcome.ALLOWED,
        actor_user_id="user_001",
        workspace_id="workspace_001",
        app_id="orka_ats",
        target=target(),
        request_id=REQUEST_ID,
        correlation_id=CORRELATION_ID,
        details=BoundedMetadata(root={"reason_code": "permission_checked"}),
        occurred_at=NOW,
    )


@pytest.fixture()
def migrated_database(tmp_path: Path) -> Database:
    database_path = tmp_path / "orkafin-test.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")
    command.upgrade(config, "head")
    database = Database(f"sqlite:///{database_path}")
    yield database
    command.downgrade(config, "base")


def test_fresh_migration_creates_only_approved_orkafin_tables(tmp_path: Path) -> None:
    database_path = tmp_path / "fresh.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")

    command.upgrade(config, "head")
    inspector = inspect(Database(f"sqlite:///{database_path}").engine)
    table_names = set(inspector.get_table_names())

    assert "candidates" not in table_names
    assert {
        "conversations",
        "messages",
        "user_events",
        "recommendations",
        "recommendation_impressions",
        "recommendation_feedback",
        "action_proposals",
        "action_confirmations",
        "action_executions",
        "audit_records",
    } <= table_names
    confirmation_indexes = {
        index["name"]: index for index in inspector.get_indexes("action_confirmations")
    }
    assert confirmation_indexes["uq_action_confirmations_proposal_id"]["unique"] == 1
    assert confirmation_indexes["uq_action_confirmations_secret_hash"]["unique"] == 1
    execution_indexes = {
        index["name"]: index for index in inspector.get_indexes("action_executions")
    }
    assert execution_indexes["uq_action_executions_proposal_id"]["unique"] == 1
    command.downgrade(config, "base")


def test_repository_persists_validated_orkafin_records(migrated_database: Database) -> None:
    with migrated_database.session_factory.begin() as session:
        repository = OrkaFinRepository(session)
        repository.add_conversation(conversation())
        repository.add_message(
            Message(
                message_id="message-001",
                conversation_id="conversation-001",
                role=MessageRole.USER,
                content="Explain the approved candidate workflow.",
                source_ids=("help_candidate_pipeline",),
                request_id=REQUEST_ID,
                created_at=NOW,
            )
        )
        repository.append_user_event(
            UserEvent(
                event_id="event-001",
                event_type=UserEventType.CANDIDATE_SELECTED,
                source=EventSource.ORKAFIN,
                app_id="orka_ats",
                actor_user_id="user_001",
                workspace=workspace(),
                entity_ref=target(),
                metadata=BoundedMetadata(root={"page_id": "candidate_profile"}),
                occurred_at=NOW,
                received_at=LATER,
                request_id=REQUEST_ID,
                correlation_id=CORRELATION_ID,
            )
        )
        repository.add_recommendation(recommendation())
        repository.add_recommendation_feedback(
            RecommendationFeedback(
                feedback_id="feedback-001",
                recommendation_id="recommendation-001",
                user_id="user_001",
                workspace=workspace(),
                feedback_type=RecommendationFeedbackType.HELPFUL,
                comment="The guidance was clear.",
                submitted_at=NOW,
                request_id=REQUEST_ID,
            )
        )
        repository.add_action_proposal(proposal())
        repository.add_action_confirmation(
            ActionConfirmation(
                confirmation_id="confirmation-001",
                proposal_id="proposal-001",
                status=ActionConfirmationStatus.ISSUED,
                bound_user_id="user_001",
                bound_workspace_id="workspace_001",
                parameter_hash=HASH,
                confirmation_secret_hash=Sha256Digest(root="b" * 64),
                issued_at=NOW,
                expires_at=LATER,
            )
        )
        repository.add_action_execution(
            ActionExecutionResult(
                execution_id="execution-001",
                proposal_id="proposal-001",
                action_id="candidate.update_start_date",
                action_version="1.0.0",
                owner_app_id="orka_ats",
                target=target(),
                status=ActionExecutionStatus.UNKNOWN,
                request_id=REQUEST_ID,
                idempotency_key=IdempotencyKey(root="execution-key-0001"),
                safe_message="The adapter outcome could not be verified.",
                completed_at=LATER,
            )
        )
        repository.append_audit_record(audit_record())

    with migrated_database.session_factory() as session:
        repository = OrkaFinRepository(session)
        stored_conversation = repository.get_conversation("conversation-001")
        stored_execution = repository.get_action_execution_for_proposal("proposal-001")
        messages = repository.list_messages("conversation-001")
        assert stored_conversation is not None
        assert stored_conversation.workspace.display_name is None
        assert stored_conversation.status is ConversationStatus.ACTIVE
        assert [message.message_id for message in messages] == ["message-001"]
        assert stored_execution is not None
        assert stored_execution.status is ActionExecutionStatus.UNKNOWN
        assert session.scalar(select(AuditRecordModel.audit_id)) == "audit-001"

        repository.update_conversation(conversation(status=ConversationStatus.CLOSED))
        session.commit()

    with migrated_database.session_factory() as session:
        stored = OrkaFinRepository(session).get_conversation("conversation-001")
        assert stored is not None and stored.status is ConversationStatus.CLOSED


def test_foreign_keys_and_status_checks_are_enforced(migrated_database: Database) -> None:
    with migrated_database.session_factory() as session:
        session.add(
            MessageModel(
                message_id="message-unknown-parent",
                schema_version="v1",
                conversation_id="missing-conversation",
                role="user",
                content="Bounded content",
                source_ids=[],
                request_id=REQUEST_ID.root,
                created_at=NOW,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            MessageModel(
                message_id="message-invalid-role",
                schema_version="v1",
                conversation_id="missing-conversation",
                role="system",
                content="Bounded content",
                source_ids=[],
                request_id=REQUEST_ID.root,
                created_at=NOW,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_audit_records_are_append_only_in_repository_and_database(
    migrated_database: Database,
) -> None:
    with migrated_database.session_factory.begin() as session:
        OrkaFinRepository(session).append_audit_record(audit_record())

    with migrated_database.session_factory() as session:
        with pytest.raises(IntegrityError, match="append-only"):
            session.execute(
                text("UPDATE audit_records SET outcome = 'denied' WHERE audit_id = 'audit-001'")
            )
        session.rollback()
        with pytest.raises(IntegrityError, match="append-only"):
            session.execute(text("DELETE FROM audit_records WHERE audit_id = 'audit-001'"))


def test_serializers_exclude_untrusted_and_secret_fields() -> None:
    serialized_event = user_event_model(
        UserEvent(
            event_id="event-serialization",
            event_type=UserEventType.CANDIDATE_SELECTED,
            source=EventSource.ORKAFIN,
            app_id="orka_ats",
            actor_user_id="user_001",
            workspace=workspace(),
            entity_ref=target(),
            metadata=BoundedMetadata(root={"page_id": "candidate_profile"}),
            occurred_at=NOW,
            received_at=LATER,
            request_id=REQUEST_ID,
            correlation_id=CORRELATION_ID,
        )
    )
    confirmation = action_confirmation_model(
        ActionConfirmation(
            confirmation_id="confirmation-serialization",
            proposal_id="proposal-001",
            status=ActionConfirmationStatus.ISSUED,
            bound_user_id="user_001",
            bound_workspace_id="workspace_001",
            parameter_hash=HASH,
            confirmation_secret_hash=Sha256Digest(root="b" * 64),
            issued_at=NOW,
            expires_at=LATER,
        )
    )

    assert "claimed_permissions" not in serialized_event.__dict__
    assert "candidate_summary" not in serialized_event.__dict__
    assert "raw_prompt" not in serialized_event.__dict__
    assert "confirmation_secret" not in confirmation.__dict__
    assert confirmation.confirmation_secret_hash == "b" * 64
    with pytest.raises(ValueError, match="metadata key is not allowed"):
        BoundedMetadata(root={"api_token": "must-not-persist"})
