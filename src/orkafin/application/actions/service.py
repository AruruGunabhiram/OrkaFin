"""Audited preparation and confirmation for one mock action, with no execution path."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from orkafin.adapters import AdapterCapability, AdapterRegistry
from orkafin.adapters.orka_ats import MOCK_ORKA_ATS_ADAPTER_ID
from orkafin.application.actions.errors import (
    ActionAccessDeniedError,
    ActionConfirmationExpiredError,
    ActionConfirmationInvalidError,
    ActionInputInvalidError,
    ActionNotAvailableError,
    ActionProposalNotFoundError,
    ActionStateConflictError,
)
from orkafin.application.actions.models import (
    ActionConfirmationChallenge,
    ActionConfirmationDecision,
    ActionConfirmationRequest,
    ActionConfirmationResponse,
    ActionProposalPreview,
    ActionProposalRequest,
    ActionProposalResponse,
    UpdateStartDateParameters,
)
from orkafin.application.context import TrustedContextResolutionService
from orkafin.core.settings import Settings
from orkafin.domain.actions import (
    ActionConfirmation,
    ActionConfirmationStatus,
    ActionDefinition,
    ActionParameterType,
    ActionPreview,
    ActionPreviewChange,
    ActionProposal,
    ActionProposalStatus,
    DateActionParameter,
)
from orkafin.domain.audit import AuditEventType, AuditOutcome, AuditRecord
from orkafin.domain.candidate import CandidateDateValue
from orkafin.domain.catalog import CatalogStatus
from orkafin.domain.context import ResolvedPageContext, SelectedEntityRef
from orkafin.domain.identifiers import (
    CorrelationId,
    IdempotencyKey,
    RequestId,
    Sha256Digest,
)
from orkafin.domain.metadata import BoundedMetadata, MetadataValue
from orkafin.infrastructure.database.repositories import OrkaFinRepository
from orkafin.infrastructure.database.session import Database
from orkafin.knowledge import KnowledgeIndex

UPDATE_START_DATE_ACTION_ID = "candidate.update_start_date"
_START_DATE_PARAMETER_ID = "start_date"
_TOKEN_BYTES = 32
_PREVIEW_WARNINGS = (
    "Mock confirmation only: confirming does not update OrkaATS or candidate data.",
    "Execution stays disabled until a separate Prompt 19 human approval.",
    (
        "OrkaATS must revalidate current permissions, state, and business rules before "
        "any future execution."
    ),
)


class ActionProposalService:
    """Prepare and confirm only ``candidate.update_start_date`` without executing it."""

    def __init__(
        self,
        *,
        database: Database,
        context_service: TrustedContextResolutionService,
        adapter_registry: AdapterRegistry,
        knowledge_index: KnowledgeIndex,
        settings: Settings,
        clock: Callable[[], datetime] | None = None,
        token_factory: Callable[[int], str] | None = None,
    ) -> None:
        self._database = database
        self._context_service = context_service
        self._adapter_registry = adapter_registry
        self._knowledge_index = knowledge_index
        self._settings = settings
        self._clock = clock or (lambda: datetime.now(UTC))
        self._token_factory = token_factory or secrets.token_urlsafe

    async def propose(
        self, value: ActionProposalRequest, *, request_id: RequestId
    ) -> ActionProposalResponse:
        """Create an exact preview and issue one hash-only persisted challenge."""
        definition = self._active_definition(value.action_id, value.context.app_id)
        self._require_mock_adapter(definition, request_id)
        context = await self._context_service.resolve(
            client_hint=value.context,
            request_id=request_id,
            include_candidate_summary=True,
        )
        target = context.selected_entity
        access_allowed = self._has_action_access(context, definition, target)
        now = self._now()
        permission_audit = self._audit_record(
            event_type=AuditEventType.ACTION_PERMISSION_CHECKED,
            outcome=AuditOutcome.ALLOWED if access_allowed else AuditOutcome.DENIED,
            request_id=request_id,
            actor_user_id=context.identity.user_id,
            workspace_id=context.workspace.workspace_id,
            app_id=definition.owner_app_id,
            target=target,
            action_id=definition.action_id,
            details={
                "phase": "proposal",
                "check": "action",
                "decision_code": "allowed" if access_allowed else "action_access_denied",
                "action_version": definition.action_version,
            },
            occurred_at=now,
        )
        self._append_audit(permission_audit)
        if not access_allowed or target is None:
            raise ActionAccessDeniedError

        current_start_date = self._current_start_date(context)
        if current_start_date is None:
            raise ActionAccessDeniedError
        if value.parameters.date_value == current_start_date:
            raise ActionInputInvalidError

        parameters = (
            DateActionParameter(
                parameter_id=_START_DATE_PARAMETER_ID,
                value=value.parameters.date_value,
            ),
        )
        parameter_hash = self._parameter_hash(value.parameters)
        expires_at = now + timedelta(seconds=self._settings.confirmation_ttl_seconds)
        proposal_id = f"proposal-{uuid4()}"
        confirmation_id = f"confirmation-{uuid4()}"
        confirmation_token = self._token_factory(_TOKEN_BYTES)
        token_hash = self._secret_hash(confirmation_token)
        preview = ActionPreview(
            summary="Prepare a candidate start-date update for confirmation.",
            changes=(
                ActionPreviewChange(
                    field_label="Start date",
                    old_value=current_start_date.isoformat(),
                    new_value=value.parameters.start_date,
                ),
            ),
            warnings=_PREVIEW_WARNINGS,
            reversible=definition.reversible,
        )
        proposal = ActionProposal(
            proposal_id=proposal_id,
            action_id=definition.action_id,
            action_version=definition.action_version,
            owner_app_id=definition.owner_app_id,
            status=ActionProposalStatus.PROPOSED,
            proposed_by_user_id=context.identity.user_id,
            workspace=context.workspace,
            target=target,
            parameters=parameters,
            parameter_hash=parameter_hash,
            preview=preview,
            idempotency_key=IdempotencyKey(root=f"action-{uuid4()}"),
            request_id=request_id,
            created_at=now,
            expires_at=expires_at,
        )
        confirmation = ActionConfirmation(
            confirmation_id=confirmation_id,
            proposal_id=proposal_id,
            status=ActionConfirmationStatus.ISSUED,
            bound_user_id=context.identity.user_id,
            bound_workspace_id=context.workspace.workspace_id,
            parameter_hash=parameter_hash,
            confirmation_secret_hash=token_hash,
            issued_at=now,
            expires_at=expires_at,
        )
        proposal_audit = self._audit_record(
            event_type=AuditEventType.ACTION_PROPOSED,
            outcome=AuditOutcome.ALLOWED,
            request_id=request_id,
            actor_user_id=context.identity.user_id,
            workspace_id=context.workspace.workspace_id,
            app_id=definition.owner_app_id,
            target=target,
            action_id=definition.action_id,
            details={
                "proposal_id": proposal_id,
                "action_version": definition.action_version,
                "status": ActionProposalStatus.PROPOSED.value,
            },
            occurred_at=now,
        )
        issued_audit = self._audit_record(
            event_type=AuditEventType.ACTION_CONFIRMATION_ISSUED,
            outcome=AuditOutcome.ALLOWED,
            request_id=request_id,
            actor_user_id=context.identity.user_id,
            workspace_id=context.workspace.workspace_id,
            app_id=definition.owner_app_id,
            target=target,
            action_id=definition.action_id,
            details={
                "proposal_id": proposal_id,
                "confirmation_id": confirmation_id,
                "ttl_seconds": self._settings.confirmation_ttl_seconds,
            },
            occurred_at=now,
        )
        with self._database.session_factory.begin() as session:
            repository = OrkaFinRepository(session)
            repository.add_action_proposal(proposal)
            repository.add_action_confirmation(confirmation)
            repository.append_audit_record(proposal_audit)
            repository.append_audit_record(issued_audit)

        return ActionProposalResponse(
            proposal_id=proposal_id,
            preview=ActionProposalPreview(
                action_id=definition.action_id,
                action_version=definition.action_version,
                owning_app_id=definition.owner_app_id,
                owning_app_display_name=context.app.display_name,
                target_candidate_id=target.entity_id,
                affected_user_id=context.identity.user_id,
                affected_user_display_name=context.identity.display_name,
                affected_workspace_id=context.workspace.workspace_id,
                affected_workspace_display_name=context.workspace.display_name,
                summary=preview.summary,
                changes=preview.changes,
                reversible=preview.reversible,
                warnings=preview.warnings,
            ),
            confirmation=ActionConfirmationChallenge(
                confirmation_token=confirmation_token,
                expires_at=expires_at,
            ),
            expires_at=expires_at,
        )

    async def confirm(
        self,
        proposal_id: str,
        value: ActionConfirmationRequest,
        *,
        request_id: RequestId,
    ) -> ActionConfirmationResponse:
        """Accept or reject a challenge and stop before any execution operation."""
        proposal, confirmation = self._load_confirmation_state(proposal_id)
        now = self._now()
        if (
            proposal.status is not ActionProposalStatus.PROPOSED
            or confirmation.status is not ActionConfirmationStatus.ISSUED
        ):
            reason_code = (
                "confirmation_replayed"
                if confirmation.status is ActionConfirmationStatus.ACCEPTED
                else "proposal_not_confirmable"
            )
            self._append_tampering_audit(
                proposal=proposal,
                request_id=request_id,
                actor_user_id=None,
                workspace_id=proposal.workspace.workspace_id,
                reason_code=reason_code,
                occurred_at=now,
            )
            raise ActionStateConflictError

        if now >= proposal.expires_at or now >= confirmation.expires_at:
            self._expire(proposal, confirmation, request_id=request_id, occurred_at=now)
            raise ActionConfirmationExpiredError

        supplied_parameter_hash = self._parameter_hash(value.parameters)
        if not (
            hmac.compare_digest(supplied_parameter_hash.root, proposal.parameter_hash.root)
            and hmac.compare_digest(supplied_parameter_hash.root, confirmation.parameter_hash.root)
        ):
            self._append_tampering_audit(
                proposal=proposal,
                request_id=request_id,
                actor_user_id=None,
                workspace_id=proposal.workspace.workspace_id,
                reason_code="parameter_mismatch",
                occurred_at=now,
            )
            raise ActionConfirmationInvalidError

        supplied_token_hash = self._secret_hash(value.confirmation_token)
        if not hmac.compare_digest(
            supplied_token_hash.root, confirmation.confirmation_secret_hash.root
        ):
            self._append_tampering_audit(
                proposal=proposal,
                request_id=request_id,
                actor_user_id=None,
                workspace_id=proposal.workspace.workspace_id,
                reason_code="confirmation_mismatch",
                occurred_at=now,
            )
            raise ActionConfirmationInvalidError

        context = await self._context_service.resolve(
            client_hint=value.context,
            request_id=request_id,
            include_candidate_summary=value.decision == ActionConfirmationDecision.ACCEPT.value,
        )
        if not self._matches_binding(context, proposal, confirmation):
            self._append_tampering_audit(
                proposal=proposal,
                request_id=request_id,
                actor_user_id=context.identity.user_id,
                workspace_id=context.workspace.workspace_id,
                reason_code="identity_workspace_or_target_mismatch",
                occurred_at=now,
            )
            raise ActionConfirmationInvalidError

        if value.decision == ActionConfirmationDecision.REJECT.value:
            self._reject(
                proposal,
                confirmation,
                request_id=request_id,
                actor_user_id=context.identity.user_id,
                reason_code="user_cancelled",
                occurred_at=now,
            )
            return ActionConfirmationResponse(
                proposal_id=proposal.proposal_id,
                proposal_status=ActionProposalStatus.CANCELLED,
                confirmation_status=ActionConfirmationStatus.REJECTED,
                execution_ready=False,
                message="Confirmation was cancelled. No action was executed.",
            )

        definition = self._active_definition(proposal.action_id, proposal.owner_app_id)
        self._require_mock_adapter(definition, request_id)
        if definition.action_version != proposal.action_version:
            self._reject(
                proposal,
                confirmation,
                request_id=request_id,
                actor_user_id=context.identity.user_id,
                reason_code="catalog_version_changed",
                occurred_at=now,
            )
            raise ActionStateConflictError
        access_allowed = self._has_action_access(context, definition, context.selected_entity)
        permission_audit = self._audit_record(
            event_type=AuditEventType.ACTION_PERMISSION_CHECKED,
            outcome=AuditOutcome.ALLOWED if access_allowed else AuditOutcome.DENIED,
            request_id=request_id,
            actor_user_id=context.identity.user_id,
            workspace_id=context.workspace.workspace_id,
            app_id=proposal.owner_app_id,
            target=proposal.target,
            action_id=proposal.action_id,
            details={
                "phase": "confirmation",
                "check": "action",
                "decision_code": "allowed" if access_allowed else "action_access_denied",
                "action_version": proposal.action_version,
                "proposal_id": proposal.proposal_id,
            },
            occurred_at=now,
        )
        self._append_audit(permission_audit)
        if not access_allowed:
            self._reject(
                proposal,
                confirmation,
                request_id=request_id,
                actor_user_id=context.identity.user_id,
                reason_code="authorization_unavailable",
                occurred_at=now,
            )
            raise ActionAccessDeniedError

        current_start_date = self._current_start_date(context)
        stored_old_value = proposal.preview.changes[0].old_value
        if current_start_date is None or stored_old_value != current_start_date.isoformat():
            self._reject(
                proposal,
                confirmation,
                request_id=request_id,
                actor_user_id=context.identity.user_id,
                reason_code="preview_stale",
                occurred_at=now,
            )
            raise ActionStateConflictError

        self._accept(
            proposal,
            confirmation,
            request_id=request_id,
            actor_user_id=context.identity.user_id,
            occurred_at=now,
        )
        return ActionConfirmationResponse(
            proposal_id=proposal.proposal_id,
            proposal_status=ActionProposalStatus.CONFIRMED,
            confirmation_status=ActionConfirmationStatus.ACCEPTED,
            execution_ready=True,
            message=(
                "Confirmation accepted and execution-ready. Execution is disabled; "
                "no action was executed."
            ),
        )

    def _active_definition(self, action_id: str, app_id: str) -> ActionDefinition:
        item = self._knowledge_index.actions_by_id.get(action_id)
        if (
            action_id != UPDATE_START_DATE_ACTION_ID
            or item is None
            or item.action.status is not CatalogStatus.ACTIVE
            or item.provenance.status is not CatalogStatus.ACTIVE
            or item.action.owner_app_id != app_id
        ):
            raise ActionNotAvailableError
        definition = item.action
        parameters = definition.parameters
        if (
            len(parameters) != 1
            or parameters[0].parameter_id != _START_DATE_PARAMETER_ID
            or parameters[0].parameter_type is not ActionParameterType.DATE
            or not parameters[0].required
            or definition.target_entity_type != "candidate"
            or not definition.confirmation_required
            or definition.execution_mode != "mock_only"
            or definition.failure_behavior != "fail_closed_without_execution"
            or not definition.validation_rules
            or not parameters[0].validation_rules
            or not definition.audit_field_ids
        ):
            raise ActionNotAvailableError
        return definition

    def _require_mock_adapter(self, definition: ActionDefinition, request_id: RequestId) -> None:
        adapter = self._adapter_registry.resolve(
            definition.owner_app_id,
            required_capability=AdapterCapability.GET_AVAILABLE_ACTIONS,
            request_id=request_id,
        )
        if (
            not self._settings.fixture_mode
            or adapter.metadata.adapter_id != MOCK_ORKA_ATS_ADAPTER_ID
        ):
            raise ActionNotAvailableError

    @staticmethod
    def _has_action_access(
        context: ResolvedPageContext,
        definition: ActionDefinition,
        target: SelectedEntityRef | None,
    ) -> bool:
        permission_ids = {permission.root for permission in context.permissions}
        summary = context.candidate_summary
        return bool(
            context.app.app_id == definition.owner_app_id
            and context.page_id == "candidate_profile"
            and target is not None
            and target.app_id == definition.owner_app_id
            and target.entity_type == definition.target_entity_type
            and summary is not None
            and summary.candidate_id == target.entity_id
            and definition.required_permission.root in permission_ids
            and definition.action_id in context.available_action_ids
        )

    @staticmethod
    def _current_start_date(context: ResolvedPageContext) -> date | None:
        summary = context.candidate_summary
        if summary is None:
            return None
        for field in summary.visible_fields:
            if field.field_id == _START_DATE_PARAMETER_ID and isinstance(
                field.value, CandidateDateValue
            ):
                return field.value.value
        return None

    @staticmethod
    def _matches_binding(
        context: ResolvedPageContext,
        proposal: ActionProposal,
        confirmation: ActionConfirmation,
    ) -> bool:
        return bool(
            context.identity.user_id == proposal.proposed_by_user_id
            and context.identity.user_id == confirmation.bound_user_id
            and context.workspace.workspace_id == proposal.workspace.workspace_id
            and context.workspace.workspace_id == confirmation.bound_workspace_id
            and context.workspace.app_id == proposal.owner_app_id
            and context.selected_entity == proposal.target
            and proposal.parameter_hash == confirmation.parameter_hash
        )

    def _load_confirmation_state(
        self, proposal_id: str
    ) -> tuple[ActionProposal, ActionConfirmation]:
        with self._database.session_factory() as session:
            repository = OrkaFinRepository(session)
            proposal = repository.get_action_proposal(proposal_id)
            confirmation = repository.get_action_confirmation_for_proposal(proposal_id)
        if proposal is None or confirmation is None:
            raise ActionProposalNotFoundError
        if proposal.action_id != UPDATE_START_DATE_ACTION_ID:
            raise ActionProposalNotFoundError
        return proposal, confirmation

    def _accept(
        self,
        proposal: ActionProposal,
        confirmation: ActionConfirmation,
        *,
        request_id: RequestId,
        actor_user_id: str,
        occurred_at: datetime,
    ) -> None:
        audit = self._audit_record(
            event_type=AuditEventType.ACTION_CONFIRMED,
            outcome=AuditOutcome.ALLOWED,
            request_id=request_id,
            actor_user_id=actor_user_id,
            workspace_id=proposal.workspace.workspace_id,
            app_id=proposal.owner_app_id,
            target=proposal.target,
            action_id=proposal.action_id,
            details={
                "proposal_id": proposal.proposal_id,
                "confirmation_id": confirmation.confirmation_id,
                "status": ActionConfirmationStatus.ACCEPTED.value,
                "execution_state": "not_started",
            },
            occurred_at=occurred_at,
        )
        self._transition(
            proposal,
            confirmation,
            proposal_status=ActionProposalStatus.CONFIRMED,
            confirmation_status=ActionConfirmationStatus.ACCEPTED,
            audit=audit,
            occurred_at=occurred_at,
        )

    def _reject(
        self,
        proposal: ActionProposal,
        confirmation: ActionConfirmation,
        *,
        request_id: RequestId,
        actor_user_id: str,
        reason_code: str,
        occurred_at: datetime,
    ) -> None:
        audit = self._audit_record(
            event_type=AuditEventType.ACTION_CONFIRMATION_REJECTED,
            outcome=AuditOutcome.DENIED,
            request_id=request_id,
            actor_user_id=actor_user_id,
            workspace_id=proposal.workspace.workspace_id,
            app_id=proposal.owner_app_id,
            target=proposal.target,
            action_id=proposal.action_id,
            details={
                "proposal_id": proposal.proposal_id,
                "confirmation_id": confirmation.confirmation_id,
                "reason_code": reason_code,
            },
            occurred_at=occurred_at,
        )
        self._transition(
            proposal,
            confirmation,
            proposal_status=ActionProposalStatus.CANCELLED,
            confirmation_status=ActionConfirmationStatus.REJECTED,
            audit=audit,
            occurred_at=occurred_at,
        )

    def _expire(
        self,
        proposal: ActionProposal,
        confirmation: ActionConfirmation,
        *,
        request_id: RequestId,
        occurred_at: datetime,
    ) -> None:
        audit = self._audit_record(
            event_type=AuditEventType.ACTION_CONFIRMATION_EXPIRED,
            outcome=AuditOutcome.DENIED,
            request_id=request_id,
            actor_user_id=None,
            workspace_id=proposal.workspace.workspace_id,
            app_id=proposal.owner_app_id,
            target=proposal.target,
            action_id=proposal.action_id,
            details={
                "proposal_id": proposal.proposal_id,
                "confirmation_id": confirmation.confirmation_id,
                "reason_code": "ttl_elapsed",
            },
            occurred_at=occurred_at,
        )
        self._transition(
            proposal,
            confirmation,
            proposal_status=ActionProposalStatus.EXPIRED,
            confirmation_status=ActionConfirmationStatus.EXPIRED,
            audit=audit,
            occurred_at=occurred_at,
        )

    def _transition(
        self,
        proposal: ActionProposal,
        confirmation: ActionConfirmation,
        *,
        proposal_status: ActionProposalStatus,
        confirmation_status: ActionConfirmationStatus,
        audit: AuditRecord,
        occurred_at: datetime,
    ) -> None:
        with self._database.session_factory.begin() as session:
            repository = OrkaFinRepository(session)
            proposal_changed = repository.transition_action_proposal(
                proposal_id=proposal.proposal_id,
                expected_status=ActionProposalStatus.PROPOSED,
                new_status=proposal_status,
            )
            confirmation_changed = repository.transition_action_confirmation(
                confirmation_id=confirmation.confirmation_id,
                expected_status=ActionConfirmationStatus.ISSUED,
                new_status=confirmation_status,
                responded_at=occurred_at,
            )
            if not proposal_changed or not confirmation_changed:
                raise ActionStateConflictError
            repository.append_audit_record(audit)

    def _append_tampering_audit(
        self,
        *,
        proposal: ActionProposal,
        request_id: RequestId,
        actor_user_id: str | None,
        workspace_id: str,
        reason_code: str,
        occurred_at: datetime,
    ) -> None:
        self._append_audit(
            self._audit_record(
                event_type=AuditEventType.ACTION_TAMPERING_REJECTED,
                outcome=AuditOutcome.DENIED,
                request_id=request_id,
                actor_user_id=actor_user_id,
                workspace_id=workspace_id,
                app_id=proposal.owner_app_id,
                target=proposal.target,
                action_id=proposal.action_id,
                details={
                    "proposal_id": proposal.proposal_id,
                    "reason_code": reason_code,
                },
                occurred_at=occurred_at,
            )
        )

    def _append_audit(self, record: AuditRecord) -> None:
        with self._database.session_factory.begin() as session:
            OrkaFinRepository(session).append_audit_record(record)

    @staticmethod
    def _audit_record(
        *,
        event_type: AuditEventType,
        outcome: AuditOutcome,
        request_id: RequestId,
        actor_user_id: str | None,
        workspace_id: str | None,
        app_id: str,
        target: SelectedEntityRef | None,
        action_id: str,
        details: Mapping[str, MetadataValue],
        occurred_at: datetime,
    ) -> AuditRecord:
        return AuditRecord(
            audit_id=f"audit-{uuid4()}",
            event_type=event_type,
            outcome=outcome,
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            app_id=app_id,
            target=target,
            action_id=action_id,
            request_id=request_id,
            correlation_id=CorrelationId(root=request_id.root),
            details=BoundedMetadata(root=dict(details)),
            occurred_at=occurred_at,
        )

    @staticmethod
    def _parameter_hash(parameters: UpdateStartDateParameters) -> Sha256Digest:
        typed_parameter = DateActionParameter(
            parameter_id=_START_DATE_PARAMETER_ID,
            value=parameters.date_value,
        )
        canonical = json.dumps(
            [typed_parameter.model_dump(mode="json")],
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return Sha256Digest(root=hashlib.sha256(canonical).hexdigest())

    @staticmethod
    def _secret_hash(secret: str) -> Sha256Digest:
        return Sha256Digest(root=hashlib.sha256(secret.encode("utf-8")).hexdigest())

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() != timedelta(0):
            raise ValueError("action service clock must return a UTC datetime")
        return now.astimezone(UTC)
