"""One-time execution of the single confirmed mock-only action."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from orkafin.adapters import (
    AdapterCapability,
    AdapterError,
    AdapterInternalFailureError,
    AdapterRegistry,
    AdapterTimeoutError,
    AdapterUnavailableError,
    ExecuteApprovedActionRequest,
    ExecuteApprovedActionResponse,
)
from orkafin.adapters.orka_ats import MOCK_ORKA_ATS_ADAPTER_ID
from orkafin.application.actions.errors import (
    ActionConfirmationExpiredError,
    ActionConfirmationInvalidError,
    ActionExecutionAccessDeniedError,
    ActionExecutionStateConflictError,
    ActionProposalNotFoundError,
)
from orkafin.application.actions.models import (
    ActionExecutionRequest,
    ActionExecutionResponse,
)
from orkafin.application.actions.service import UPDATE_START_DATE_ACTION_ID
from orkafin.application.context import TrustedContextResolutionService
from orkafin.core.settings import Settings
from orkafin.domain.actions import (
    ActionConfirmation,
    ActionConfirmationStatus,
    ActionDefinition,
    ActionExecutionResult,
    ActionExecutionStatus,
    ActionParameterType,
    ActionProposal,
    ActionProposalStatus,
    AdapterExecutionReceipt,
    AdapterReceiptOutcome,
    DateActionParameter,
)
from orkafin.domain.audit import AuditEventType, AuditOutcome, AuditRecord
from orkafin.domain.candidate import CandidateDateValue
from orkafin.domain.catalog import CatalogStatus
from orkafin.domain.context import ResolvedPageContext, SelectedEntityRef
from orkafin.domain.identifiers import CorrelationId, RequestId, Sha256Digest
from orkafin.domain.metadata import BoundedMetadata, MetadataValue
from orkafin.infrastructure.database.repositories import OrkaFinRepository
from orkafin.infrastructure.database.session import Database
from orkafin.knowledge import KnowledgeIndex

_START_DATE_PARAMETER_ID = "start_date"
_SUCCESS_MESSAGE = "Mock OrkaATS confirmed the candidate start date was updated."
_FAILED_MESSAGE = "OrkaATS could not complete the request. No changes were made."
_UNKNOWN_MESSAGE = (
    "OrkaATS did not confirm the outcome. Do not retry this action; reconcile it using "
    "the returned idempotency key."
)


class ActionExecutionService:
    """Execute only ``candidate.update_start_date`` through the configured mock adapter."""

    def __init__(
        self,
        *,
        database: Database,
        context_service: TrustedContextResolutionService,
        adapter_registry: AdapterRegistry,
        knowledge_index: KnowledgeIndex,
        settings: Settings,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._database = database
        self._context_service = context_service
        self._adapter_registry = adapter_registry
        self._knowledge_index = knowledge_index
        self._settings = settings
        self._clock = clock or (lambda: datetime.now(UTC))

    async def execute(
        self,
        proposal_id: str,
        value: ActionExecutionRequest,
        *,
        request_id: RequestId,
    ) -> ActionExecutionResponse:
        """Revalidate, reserve once, call the adapter once, and persist an honest result."""
        proposal, confirmation, existing = self._load_state(proposal_id)
        now = self._now()
        self._append_audit(
            self._audit_record(
                event_type=AuditEventType.ACTION_EXECUTION_ATTEMPTED,
                outcome=AuditOutcome.ALLOWED,
                request_id=request_id,
                actor_user_id=None,
                workspace_id=proposal.workspace.workspace_id,
                app_id=proposal.owner_app_id,
                target=proposal.target,
                action_id=proposal.action_id,
                details={
                    "proposal_id": proposal.proposal_id,
                    "idempotency_key": proposal.idempotency_key.root,
                },
                occurred_at=now,
            )
        )

        resolution = await self._context_service.resolve_for_action_execution(
            client_hint=value.context,
            request_id=request_id,
            include_candidate_summary=True,
        )
        context = resolution.page_context
        if not self._matches_binding(context, proposal, confirmation):
            self._append_tampering_audit(
                proposal=proposal,
                request_id=request_id,
                actor_user_id=context.identity.user_id,
                workspace_id=context.workspace.workspace_id,
                reason_code="execution_binding_mismatch",
                occurred_at=now,
            )
            raise ActionConfirmationInvalidError

        if existing is not None:
            return self._replay(
                proposal=proposal,
                existing=existing,
                context=context,
                request_id=request_id,
                occurred_at=now,
            )

        if (
            proposal.status is not ActionProposalStatus.CONFIRMED
            or confirmation.status is not ActionConfirmationStatus.ACCEPTED
        ):
            self._append_tampering_audit(
                proposal=proposal,
                request_id=request_id,
                actor_user_id=context.identity.user_id,
                workspace_id=context.workspace.workspace_id,
                reason_code="confirmation_reused_for_execution",
                occurred_at=now,
            )
            raise ActionExecutionStateConflictError

        if now >= proposal.expires_at or now >= confirmation.expires_at:
            self._record_precheck_result(
                proposal=proposal,
                confirmation=confirmation,
                request_id=request_id,
                actor_user_id=context.identity.user_id,
                status=ActionExecutionStatus.REJECTED,
                reason_code="confirmation_expired_before_execution",
                occurred_at=now,
            )
            raise ActionConfirmationExpiredError

        definition = self._active_definition(proposal.action_id, proposal.owner_app_id)
        if definition.action_version != proposal.action_version:
            self._record_precheck_result(
                proposal=proposal,
                confirmation=confirmation,
                request_id=request_id,
                actor_user_id=context.identity.user_id,
                status=ActionExecutionStatus.CONFLICT,
                reason_code="catalog_version_changed",
                occurred_at=now,
            )
            raise ActionExecutionStateConflictError

        if not self._valid_parameter_binding(proposal, confirmation):
            self._record_precheck_result(
                proposal=proposal,
                confirmation=confirmation,
                request_id=request_id,
                actor_user_id=context.identity.user_id,
                status=ActionExecutionStatus.CONFLICT,
                reason_code="parameter_hash_changed",
                occurred_at=now,
            )
            raise ActionExecutionStateConflictError

        candidate_access_denied = resolution.candidate_access_denied
        access_allowed = not candidate_access_denied and self._has_action_access(
            context, definition, context.selected_entity
        )
        permission_check = "candidate_visibility" if candidate_access_denied else "action"
        permission_decision = (
            "candidate_access_denied"
            if candidate_access_denied
            else "allowed"
            if access_allowed
            else "action_access_denied"
        )
        self._append_audit(
            self._audit_record(
                event_type=AuditEventType.ACTION_PERMISSION_CHECKED,
                outcome=AuditOutcome.ALLOWED if access_allowed else AuditOutcome.DENIED,
                request_id=request_id,
                actor_user_id=context.identity.user_id,
                workspace_id=context.workspace.workspace_id,
                app_id=proposal.owner_app_id,
                target=proposal.target,
                action_id=proposal.action_id,
                details={
                    "phase": "execution",
                    "check": permission_check,
                    "decision_code": permission_decision,
                    "action_version": proposal.action_version,
                    "proposal_id": proposal.proposal_id,
                },
                occurred_at=now,
            )
        )
        if not access_allowed:
            self._record_precheck_result(
                proposal=proposal,
                confirmation=confirmation,
                request_id=request_id,
                actor_user_id=context.identity.user_id,
                status=ActionExecutionStatus.REJECTED,
                reason_code=(
                    "candidate_visibility_revoked_before_execution"
                    if candidate_access_denied
                    else "permission_revoked_before_execution"
                ),
                occurred_at=now,
            )
            raise ActionExecutionAccessDeniedError

        current_start_date = self._current_start_date(context)
        old_value = proposal.preview.changes[0].old_value
        if current_start_date is None or old_value != current_start_date.isoformat():
            self._record_precheck_result(
                proposal=proposal,
                confirmation=confirmation,
                request_id=request_id,
                actor_user_id=context.identity.user_id,
                status=ActionExecutionStatus.CONFLICT,
                reason_code="candidate_state_changed_before_execution",
                occurred_at=now,
            )
            raise ActionExecutionStateConflictError

        try:
            adapter = self._adapter_registry.resolve(
                definition.owner_app_id,
                required_capability=AdapterCapability.EXECUTE_APPROVED_ACTION,
                request_id=request_id,
            )
        except AdapterError:
            result = self._record_precheck_result(
                proposal=proposal,
                confirmation=confirmation,
                request_id=request_id,
                actor_user_id=context.identity.user_id,
                status=ActionExecutionStatus.FAILED,
                reason_code="adapter_execution_unavailable",
                occurred_at=now,
            )
            return ActionExecutionResponse(execution=result)
        if (
            not self._settings.fixture_mode
            or adapter.metadata.adapter_id != MOCK_ORKA_ATS_ADAPTER_ID
        ):
            result = self._record_precheck_result(
                proposal=proposal,
                confirmation=confirmation,
                request_id=request_id,
                actor_user_id=context.identity.user_id,
                status=ActionExecutionStatus.REJECTED,
                reason_code="non_mock_execution_denied",
                occurred_at=now,
            )
            return ActionExecutionResponse(execution=result)

        reservation = self._reservation(proposal, request_id=request_id, occurred_at=now)
        try:
            self._reserve(
                proposal=proposal,
                confirmation=confirmation,
                reservation=reservation,
                actor_user_id=context.identity.user_id,
                request_id=request_id,
                occurred_at=now,
            )
        except (IntegrityError, ActionExecutionStateConflictError):
            replay = self._load_execution(proposal)
            if replay is None:
                raise ActionExecutionStateConflictError from None
            return self._replay(
                proposal=proposal,
                existing=replay,
                context=context,
                request_id=request_id,
                occurred_at=now,
            )

        adapter_request = ExecuteApprovedActionRequest(
            request_id=request_id,
            app_id=proposal.owner_app_id,
            trusted_identity=resolution.trusted_identity,
            context=resolution.application_context,
            action_definition=definition,
            proposal=proposal,
            confirmation=confirmation,
            idempotency_key=proposal.idempotency_key,
        )
        try:
            adapter_response = await adapter.execute_approved_action(adapter_request)
        except Exception as error:
            result = self._result_from_adapter_error(
                reservation=reservation,
                error=error,
                occurred_at=self._now(),
            )
        else:
            result = self._result_from_response(
                reservation=reservation,
                response=adapter_response,
                adapter_id=adapter.metadata.adapter_id,
                occurred_at=self._now(),
            )
        self._finalize(
            proposal=proposal,
            result=result,
            actor_user_id=context.identity.user_id,
        )
        return ActionExecutionResponse(execution=result)

    def _active_definition(self, action_id: str, app_id: str) -> ActionDefinition:
        item = self._knowledge_index.actions_by_id.get(action_id)
        if (
            action_id != UPDATE_START_DATE_ACTION_ID
            or item is None
            or item.action.status is not CatalogStatus.ACTIVE
            or item.provenance.status is not CatalogStatus.ACTIVE
            or item.action.owner_app_id != app_id
        ):
            raise ActionExecutionStateConflictError
        definition = item.action
        parameters = definition.parameters
        if (
            len(parameters) != 1
            or parameters[0].parameter_id != _START_DATE_PARAMETER_ID
            or parameters[0].parameter_type is not ActionParameterType.DATE
            or not parameters[0].required
            or definition.target_entity_type != "candidate"
            or definition.execution_mode != "mock_only"
        ):
            raise ActionExecutionStateConflictError
        return definition

    def _load_state(
        self, proposal_id: str
    ) -> tuple[ActionProposal, ActionConfirmation, ActionExecutionResult | None]:
        with self._database.session_factory() as session:
            repository = OrkaFinRepository(session)
            proposal = repository.get_action_proposal(proposal_id)
            confirmation = repository.get_action_confirmation_for_proposal(proposal_id)
            execution = repository.get_action_execution_for_proposal(proposal_id)
        if proposal is None or confirmation is None:
            raise ActionProposalNotFoundError
        if proposal.action_id != UPDATE_START_DATE_ACTION_ID:
            raise ActionProposalNotFoundError
        return proposal, confirmation, execution

    def _load_execution(self, proposal: ActionProposal) -> ActionExecutionResult | None:
        with self._database.session_factory() as session:
            repository = OrkaFinRepository(session)
            execution = repository.get_action_execution_for_proposal(proposal.proposal_id)
            by_key = repository.get_action_execution_by_idempotency_key(
                proposal.idempotency_key.root
            )
        if execution != by_key:
            raise ActionExecutionStateConflictError
        return execution

    def _reserve(
        self,
        *,
        proposal: ActionProposal,
        confirmation: ActionConfirmation,
        reservation: ActionExecutionResult,
        actor_user_id: str,
        request_id: RequestId,
        occurred_at: datetime,
    ) -> None:
        adapter_audit = self._audit_record(
            event_type=AuditEventType.ACTION_ADAPTER_REQUESTED,
            outcome=AuditOutcome.ALLOWED,
            request_id=request_id,
            actor_user_id=actor_user_id,
            workspace_id=proposal.workspace.workspace_id,
            app_id=proposal.owner_app_id,
            target=proposal.target,
            action_id=proposal.action_id,
            details={
                "proposal_id": proposal.proposal_id,
                "execution_id": reservation.execution_id,
                "adapter_operation": AdapterCapability.EXECUTE_APPROVED_ACTION.value,
                "action_version": proposal.action_version,
            },
            occurred_at=occurred_at,
        )
        with self._database.session_factory.begin() as session:
            repository = OrkaFinRepository(session)
            confirmation_changed = repository.transition_action_confirmation(
                confirmation_id=confirmation.confirmation_id,
                expected_status=ActionConfirmationStatus.ACCEPTED,
                new_status=ActionConfirmationStatus.CONSUMED,
                responded_at=confirmation.responded_at or occurred_at,
            )
            if not confirmation_changed:
                raise ActionExecutionStateConflictError
            repository.add_action_execution(reservation)
            repository.append_audit_record(adapter_audit)

    def _record_precheck_result(
        self,
        *,
        proposal: ActionProposal,
        confirmation: ActionConfirmation,
        request_id: RequestId,
        actor_user_id: str,
        status: ActionExecutionStatus,
        reason_code: str,
        occurred_at: datetime,
    ) -> ActionExecutionResult:
        result = ActionExecutionResult(
            execution_id=f"execution-{uuid4()}",
            proposal_id=proposal.proposal_id,
            action_id=proposal.action_id,
            action_version=proposal.action_version,
            owner_app_id=proposal.owner_app_id,
            target=proposal.target,
            status=status,
            request_id=request_id,
            idempotency_key=proposal.idempotency_key,
            safe_message=_FAILED_MESSAGE,
            completed_at=occurred_at,
        )
        outcome_audit, final_audit = self._result_audits(
            proposal=proposal,
            result=result,
            actor_user_id=actor_user_id,
            reason_code=reason_code,
        )
        try:
            with self._database.session_factory.begin() as session:
                repository = OrkaFinRepository(session)
                proposal_changed = repository.transition_action_proposal(
                    proposal_id=proposal.proposal_id,
                    expected_status=ActionProposalStatus.CONFIRMED,
                    new_status=ActionProposalStatus.FAILED,
                )
                confirmation_changed = repository.transition_action_confirmation(
                    confirmation_id=confirmation.confirmation_id,
                    expected_status=ActionConfirmationStatus.ACCEPTED,
                    new_status=ActionConfirmationStatus.CONSUMED,
                    responded_at=confirmation.responded_at or occurred_at,
                )
                if not proposal_changed or not confirmation_changed:
                    raise ActionExecutionStateConflictError
                repository.add_action_execution(result)
                repository.append_audit_record(outcome_audit)
                repository.append_audit_record(final_audit)
        except (IntegrityError, ActionExecutionStateConflictError):
            existing = self._load_execution(proposal)
            if existing is None:
                raise
            return existing
        return result

    def _finalize(
        self,
        *,
        proposal: ActionProposal,
        result: ActionExecutionResult,
        actor_user_id: str,
    ) -> None:
        reason_code = {
            ActionExecutionStatus.SUCCEEDED: "adapter_receipt_succeeded",
            ActionExecutionStatus.FAILED: "adapter_rejected_or_failed",
            ActionExecutionStatus.UNKNOWN: "adapter_outcome_ambiguous",
        }[result.status]
        outcome_audit, final_audit = self._result_audits(
            proposal=proposal,
            result=result,
            actor_user_id=actor_user_id,
            reason_code=reason_code,
        )
        proposal_status = (
            ActionProposalStatus.EXECUTED
            if result.status is ActionExecutionStatus.SUCCEEDED
            else ActionProposalStatus.FAILED
        )
        with self._database.session_factory.begin() as session:
            repository = OrkaFinRepository(session)
            proposal_changed = repository.transition_action_proposal(
                proposal_id=proposal.proposal_id,
                expected_status=ActionProposalStatus.CONFIRMED,
                new_status=proposal_status,
            )
            if not proposal_changed:
                raise ActionExecutionStateConflictError
            repository.update_action_execution(result)
            repository.append_audit_record(outcome_audit)
            repository.append_audit_record(final_audit)

    def _result_from_response(
        self,
        *,
        reservation: ActionExecutionResult,
        response: object,
        adapter_id: str,
        occurred_at: datetime,
    ) -> ActionExecutionResult:
        if not isinstance(response, ExecuteApprovedActionResponse):
            return self._replace_result(
                reservation,
                status=ActionExecutionStatus.UNKNOWN,
                receipt=None,
                safe_message=_UNKNOWN_MESSAGE,
                occurred_at=occurred_at,
            )
        receipt = response.receipt
        if not self._receipt_matches(
            receipt,
            reservation=reservation,
            adapter_id=adapter_id,
            response=response,
        ):
            return self._replace_result(
                reservation,
                status=ActionExecutionStatus.UNKNOWN,
                receipt=None,
                safe_message=_UNKNOWN_MESSAGE,
                occurred_at=occurred_at,
            )
        if receipt.outcome is AdapterReceiptOutcome.SUCCEEDED:
            return self._replace_result(
                reservation,
                status=ActionExecutionStatus.SUCCEEDED,
                receipt=receipt,
                safe_message=_SUCCESS_MESSAGE,
                occurred_at=occurred_at,
            )
        return self._replace_result(
            reservation,
            status=ActionExecutionStatus.FAILED,
            receipt=receipt,
            safe_message=_FAILED_MESSAGE,
            occurred_at=occurred_at,
        )

    def _result_from_adapter_error(
        self,
        *,
        reservation: ActionExecutionResult,
        error: Exception,
        occurred_at: datetime,
    ) -> ActionExecutionResult:
        ambiguous = isinstance(
            error,
            (
                AdapterTimeoutError,
                AdapterUnavailableError,
                AdapterInternalFailureError,
            ),
        ) or not isinstance(error, AdapterError)
        return self._replace_result(
            reservation,
            status=(ActionExecutionStatus.UNKNOWN if ambiguous else ActionExecutionStatus.FAILED),
            receipt=None,
            safe_message=_UNKNOWN_MESSAGE if ambiguous else _FAILED_MESSAGE,
            occurred_at=occurred_at,
        )

    @staticmethod
    def _replace_result(
        reservation: ActionExecutionResult,
        *,
        status: ActionExecutionStatus,
        receipt: AdapterExecutionReceipt | None,
        safe_message: str,
        occurred_at: datetime,
    ) -> ActionExecutionResult:
        payload = reservation.model_dump(mode="python")
        payload.update(
            {
                "status": status,
                "adapter_receipt": receipt,
                "safe_message": safe_message,
                "completed_at": occurred_at,
            }
        )
        return ActionExecutionResult.model_validate(payload)

    @staticmethod
    def _receipt_matches(
        receipt: AdapterExecutionReceipt,
        *,
        reservation: ActionExecutionResult,
        adapter_id: str,
        response: ExecuteApprovedActionResponse,
    ) -> bool:
        return bool(
            response.request_id == reservation.request_id
            and response.app_id == reservation.owner_app_id
            and response.responded_at >= receipt.received_at
            and receipt.adapter_id == adapter_id
            and receipt.owner_app_id == reservation.owner_app_id
            and receipt.action_id == reservation.action_id
            and receipt.action_version == reservation.action_version
            and receipt.target == reservation.target
            and receipt.request_id == reservation.request_id
            and receipt.idempotency_key == reservation.idempotency_key
        )

    @staticmethod
    def _reservation(
        proposal: ActionProposal,
        *,
        request_id: RequestId,
        occurred_at: datetime,
    ) -> ActionExecutionResult:
        return ActionExecutionResult(
            execution_id=f"execution-{uuid4()}",
            proposal_id=proposal.proposal_id,
            action_id=proposal.action_id,
            action_version=proposal.action_version,
            owner_app_id=proposal.owner_app_id,
            target=proposal.target,
            status=ActionExecutionStatus.UNKNOWN,
            request_id=request_id,
            idempotency_key=proposal.idempotency_key,
            safe_message=_UNKNOWN_MESSAGE,
            completed_at=occurred_at,
        )

    def _replay(
        self,
        *,
        proposal: ActionProposal,
        existing: ActionExecutionResult,
        context: ResolvedPageContext,
        request_id: RequestId,
        occurred_at: datetime,
    ) -> ActionExecutionResponse:
        if (
            existing.proposal_id != proposal.proposal_id
            or existing.idempotency_key != proposal.idempotency_key
            or existing.target != proposal.target
            or existing.action_id != proposal.action_id
            or existing.action_version != proposal.action_version
        ):
            raise ActionExecutionStateConflictError
        self._append_audit(
            self._audit_record(
                event_type=AuditEventType.ACTION_FINAL_RESULT,
                outcome=self._audit_outcome(existing.status),
                request_id=request_id,
                actor_user_id=context.identity.user_id,
                workspace_id=context.workspace.workspace_id,
                app_id=proposal.owner_app_id,
                target=proposal.target,
                action_id=proposal.action_id,
                details={
                    "proposal_id": proposal.proposal_id,
                    "execution_id": existing.execution_id,
                    "status": existing.status.value,
                    "idempotent_replay": True,
                },
                occurred_at=occurred_at,
            )
        )
        return ActionExecutionResponse(execution=existing, idempotent_replay=True)

    def _result_audits(
        self,
        *,
        proposal: ActionProposal,
        result: ActionExecutionResult,
        actor_user_id: str,
        reason_code: str,
    ) -> tuple[AuditRecord, AuditRecord]:
        event_type = {
            ActionExecutionStatus.SUCCEEDED: AuditEventType.ACTION_EXECUTION_SUCCEEDED,
            ActionExecutionStatus.UNKNOWN: AuditEventType.ACTION_EXECUTION_UNKNOWN,
            ActionExecutionStatus.FAILED: AuditEventType.ACTION_EXECUTION_FAILED,
            ActionExecutionStatus.CONFLICT: AuditEventType.ACTION_EXECUTION_FAILED,
            ActionExecutionStatus.REJECTED: AuditEventType.ACTION_EXECUTION_FAILED,
        }[result.status]
        outcome = self._audit_outcome(result.status)
        details: dict[str, MetadataValue] = {
            "proposal_id": proposal.proposal_id,
            "execution_id": result.execution_id,
            "status": result.status.value,
            "reason_code": reason_code,
        }
        if result.adapter_receipt is not None:
            details["receipt_id"] = result.adapter_receipt.receipt_id
        outcome_audit = self._audit_record(
            event_type=event_type,
            outcome=outcome,
            request_id=result.request_id,
            actor_user_id=actor_user_id,
            workspace_id=proposal.workspace.workspace_id,
            app_id=proposal.owner_app_id,
            target=proposal.target,
            action_id=proposal.action_id,
            details=details,
            occurred_at=result.completed_at,
        )
        final_audit = self._audit_record(
            event_type=AuditEventType.ACTION_FINAL_RESULT,
            outcome=outcome,
            request_id=result.request_id,
            actor_user_id=actor_user_id,
            workspace_id=proposal.workspace.workspace_id,
            app_id=proposal.owner_app_id,
            target=proposal.target,
            action_id=proposal.action_id,
            details={
                "proposal_id": proposal.proposal_id,
                "execution_id": result.execution_id,
                "status": result.status.value,
                "safe_result_code": reason_code,
            },
            occurred_at=result.completed_at,
        )
        return outcome_audit, final_audit

    @staticmethod
    def _audit_outcome(status: ActionExecutionStatus) -> AuditOutcome:
        return {
            ActionExecutionStatus.SUCCEEDED: AuditOutcome.SUCCEEDED,
            ActionExecutionStatus.UNKNOWN: AuditOutcome.UNKNOWN,
            ActionExecutionStatus.FAILED: AuditOutcome.FAILED,
            ActionExecutionStatus.CONFLICT: AuditOutcome.FAILED,
            ActionExecutionStatus.REJECTED: AuditOutcome.DENIED,
        }[status]

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

    @staticmethod
    def _valid_parameter_binding(
        proposal: ActionProposal,
        confirmation: ActionConfirmation,
    ) -> bool:
        if (
            len(proposal.parameters) != 1
            or not isinstance(proposal.parameters[0], DateActionParameter)
            or proposal.parameters[0].parameter_id != _START_DATE_PARAMETER_ID
        ):
            return False
        canonical = json.dumps(
            [proposal.parameters[0].model_dump(mode="json")],
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        calculated = Sha256Digest(root=hashlib.sha256(canonical).hexdigest())
        return bool(
            hmac.compare_digest(calculated.root, proposal.parameter_hash.root)
            and hmac.compare_digest(calculated.root, confirmation.parameter_hash.root)
        )

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

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() != timedelta(0):
            raise ValueError("action execution service clock must return a UTC datetime")
        return now.astimezone(UTC)
