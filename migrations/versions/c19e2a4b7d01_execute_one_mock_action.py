"""execute one confirmed mock action

Revision ID: c19e2a4b7d01
Revises: e7a1c4b92d10
Create Date: 2026-07-19 21:00:00
"""

from __future__ import annotations

from alembic import op

revision = "c19e2a4b7d01"
down_revision = "e7a1c4b92d10"
branch_labels = None
depends_on = None

_AUDIT_EVENT_CHECK = (
    "event_type IN ('identity_verified', 'identity_denied', 'candidate_read', "
    "'permission_denied', 'action_permission_checked', 'action_proposed', "
    "'action_confirmation_issued', 'action_confirmed', 'action_confirmation_rejected', "
    "'action_confirmation_expired', 'action_tampering_rejected', "
    "'action_execution_attempted', 'action_adapter_requested', "
    "'action_execution_succeeded', 'action_execution_failed', "
    "'action_execution_unknown', 'action_final_result')"
)
_OLD_AUDIT_EVENT_CHECK = (
    "event_type IN ('identity_verified', 'identity_denied', 'candidate_read', "
    "'permission_denied', 'action_permission_checked', 'action_proposed', "
    "'action_confirmation_issued', 'action_confirmed', 'action_confirmation_rejected', "
    "'action_confirmation_expired', 'action_tampering_rejected', "
    "'action_execution_attempted', 'action_execution_succeeded', "
    "'action_execution_failed', 'action_execution_unknown')"
)


def _drop_audit_triggers() -> None:
    op.execute("DROP TRIGGER IF EXISTS prevent_audit_records_delete")
    op.execute("DROP TRIGGER IF EXISTS prevent_audit_records_update")


def _create_audit_triggers() -> None:
    op.execute(
        "CREATE TRIGGER prevent_audit_records_update "
        "BEFORE UPDATE ON audit_records BEGIN "
        "SELECT RAISE(ABORT, 'audit_records are append-only'); END"
    )
    op.execute(
        "CREATE TRIGGER prevent_audit_records_delete "
        "BEFORE DELETE ON audit_records BEGIN "
        "SELECT RAISE(ABORT, 'audit_records are append-only'); END"
    )


def _replace_audit_event_check(expression: str) -> None:
    _drop_audit_triggers()
    with op.batch_alter_table("audit_records", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_audit_records_event_type", type_="check")
        batch_op.create_check_constraint("ck_audit_records_event_type", expression)
    _create_audit_triggers()


def upgrade() -> None:
    """Allow complete execution audits and enforce one result per proposal."""
    op.create_index(
        "uq_action_executions_proposal_id",
        "action_executions",
        ["proposal_id"],
        unique=True,
    )
    _replace_audit_event_check(_AUDIT_EVENT_CHECK)


def downgrade() -> None:
    """Restore the confirmation-only audit vocabulary and execution cardinality."""
    _replace_audit_event_check(_OLD_AUDIT_EVENT_CHECK)
    op.drop_index("uq_action_executions_proposal_id", table_name="action_executions")
