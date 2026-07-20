"""harden action confirmation state

Revision ID: e7a1c4b92d10
Revises: 9c2e4f6a1b73
Create Date: 2026-07-19 18:00:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "e7a1c4b92d10"
down_revision = "9c2e4f6a1b73"
branch_labels = None
depends_on = None

_AUDIT_EVENT_CHECK = (
    "event_type IN ('identity_verified', 'identity_denied', 'candidate_read', "
    "'permission_denied', 'action_permission_checked', 'action_proposed', "
    "'action_confirmation_issued', 'action_confirmed', 'action_confirmation_rejected', "
    "'action_confirmation_expired', 'action_tampering_rejected', "
    "'action_execution_attempted', 'action_execution_succeeded', "
    "'action_execution_failed', 'action_execution_unknown')"
)
_OLD_AUDIT_EVENT_CHECK = (
    "event_type IN ('identity_verified', 'identity_denied', 'candidate_read', "
    "'permission_denied', 'action_proposed', 'action_confirmation_issued', "
    "'action_confirmed', 'action_confirmation_rejected', "
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
    """Enforce one challenge per proposal and record allowed permission checks."""
    op.create_index(
        "uq_action_confirmations_proposal_id",
        "action_confirmations",
        ["proposal_id"],
        unique=True,
    )
    op.create_index(
        "uq_action_confirmations_secret_hash",
        "action_confirmations",
        ["confirmation_secret_hash"],
        unique=True,
    )
    _replace_audit_event_check(_AUDIT_EVENT_CHECK)


def downgrade() -> None:
    """Remove Prompt 18 hardening after first restoring the old audit vocabulary."""
    _replace_audit_event_check(_OLD_AUDIT_EVENT_CHECK)
    op.drop_index(
        "uq_action_confirmations_secret_hash",
        table_name="action_confirmations",
    )
    op.drop_index(
        "uq_action_confirmations_proposal_id",
        table_name="action_confirmations",
    )
