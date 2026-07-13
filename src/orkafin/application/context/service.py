"""Trusted context orchestration over untrusted browser hints."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable
from uuid import uuid4

from orkafin.adapters import (
    AdapterCapability,
    AdapterRegistry,
    EntityBooleanValue,
    EntityDateValue,
    EntityIntegerValue,
    EntityNumberValue,
    EntityReferenceValue,
    EntityTextValue,
    EntityTimestampValue,
    GetAvailableActionsRequest,
    GetPageMetadataRequest,
    GetSelectedEntitySummaryRequest,
    GetUserPermissionsRequest,
    ResolveContextRequest,
    ResolveCurrentUserRequest,
    SelectedEntitySummary,
    VisibleEntityField,
)
from orkafin.application.auth import TrustedSessionResolver
from orkafin.application.context.errors import (
    CandidateAccessDeniedError,
    ContextAccessDeniedError,
    ContextUnavailableError,
    IdentityUnverifiedContextError,
)
from orkafin.application.permissions import AuthorizationContext, PermissionEvaluator
from orkafin.domain.audit import AuditEventType, AuditOutcome, AuditRecord
from orkafin.domain.candidate import (
    CandidateBooleanValue,
    CandidateDateValue,
    CandidateFieldSensitivity,
    CandidateFieldValue,
    CandidateIntegerValue,
    CandidateNumberValue,
    CandidateReferenceValue,
    CandidateSummary,
    CandidateTextValue,
    CandidateTimestampValue,
    CandidateVisibilitySummary,
    VisibleCandidateField,
)
from orkafin.domain.context import (
    ClientContextHint,
    ContextComponentTrust,
    ContextVerificationSource,
    IdentityVerificationStatus,
    ResolvedContextTrust,
    ResolvedPageContext,
    SelectedEntityRef,
    UserIdentity,
)
from orkafin.domain.identifiers import CorrelationId, Permission, RequestId
from orkafin.domain.metadata import BoundedMetadata

_CANDIDATE_VIEW_PERMISSION = Permission(root="candidate.view")
_CANDIDATE_SUMMARY_FIELD_IDS = (
    "display_name",
    "email",
    "recruiter",
    "recruitment_stage",
    "resume_link",
    "start_date",
    "created_at",
    "updated_at",
)


@runtime_checkable
class AuditRecorder(Protocol):
    """Append one validated audit record in a committed transaction."""

    def append(self, record: AuditRecord) -> None:
        """Persist a security-relevant fact without logging its protected fields."""
        ...


class TrustedContextResolutionService:
    """Resolve trusted adapter facts while treating the entire request body as hints."""

    def __init__(
        self,
        *,
        adapter_registry: AdapterRegistry,
        trusted_session_resolver: TrustedSessionResolver,
        audit_recorder: AuditRecorder,
        permission_evaluator: PermissionEvaluator | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._adapter_registry = adapter_registry
        self._trusted_session_resolver = trusted_session_resolver
        self._audit_recorder = audit_recorder
        self._permission_evaluator = permission_evaluator or PermissionEvaluator(
            known_permissions=(_CANDIDATE_VIEW_PERMISSION,)
        )
        self._clock = clock or (lambda: datetime.now(UTC))

    async def resolve(
        self, *, client_hint: ClientContextHint, request_id: RequestId
    ) -> ResolvedPageContext:
        """Resolve identity, page, authorization, actions, and an allowed candidate summary."""
        app_id = client_hint.app_id_hint
        adapter = self._adapter_registry.resolve(
            app_id,
            required_capability=AdapterCapability.GET_AVAILABLE_ACTIONS,
            request_id=request_id,
        )
        trusted_subject = self._trusted_session_resolver.resolve_subject_reference(
            app_id=app_id,
            request_id=request_id,
        )
        identity_response = await adapter.resolve_current_user(
            ResolveCurrentUserRequest(
                request_id=request_id,
                app_id=app_id,
                trusted_subject_reference=trusted_subject,
                client_hint=client_hint,
            )
        )
        identity = identity_response.identity
        if identity.verification_status is IdentityVerificationStatus.UNVERIFIED:
            self._append_identity_denial(app_id=app_id, request_id=request_id)
            raise IdentityUnverifiedContextError
        if identity.role is None or identity.role.owner_app_id != app_id:
            raise ContextUnavailableError

        context_response = await adapter.resolve_context(
            ResolveContextRequest(
                request_id=request_id,
                app_id=app_id,
                trusted_identity=identity,
                client_hint=client_hint,
            )
        )
        application_context = context_response.context
        page_response = await adapter.get_page_metadata(
            GetPageMetadataRequest(
                request_id=request_id,
                app_id=app_id,
                trusted_identity=identity,
                context=application_context,
            )
        )
        if page_response.page_metadata.page_id != application_context.page_id:
            raise ContextUnavailableError

        permissions_response = await adapter.get_user_permissions(
            GetUserPermissionsRequest(
                request_id=request_id,
                app_id=app_id,
                trusted_identity=identity,
                context=application_context,
            )
        )
        authorization = AuthorizationContext(
            identity=identity,
            facts=permissions_response.authorization_facts,
        )
        app_decision = self._permission_evaluator.check_app(authorization, app_id=app_id)
        if not app_decision.allowed:
            self._append_permission_denial(
                app_id=app_id,
                request_id=request_id,
                identity=identity,
                workspace_id=application_context.workspace.workspace_id,
                target=None,
                check=app_decision.check.value,
                decision_code=app_decision.code.value,
            )
            raise ContextAccessDeniedError
        page_decision = self._permission_evaluator.check_page(
            authorization,
            app_id=app_id,
            page_id=application_context.page_id,
        )
        if not page_decision.allowed:
            self._append_permission_denial(
                app_id=app_id,
                request_id=request_id,
                identity=identity,
                workspace_id=application_context.workspace.workspace_id,
                target=None,
                check=page_decision.check.value,
                decision_code=page_decision.code.value,
            )
            raise ContextAccessDeniedError

        actions_response = await adapter.get_available_actions(
            GetAvailableActionsRequest(
                request_id=request_id,
                app_id=app_id,
                trusted_identity=identity,
                context=application_context,
            )
        )
        fact_action_ids = frozenset(permissions_response.authorization_facts.available_action_ids)
        available_action_ids = tuple(
            action_id for action_id in actions_response.action_ids if action_id in fact_action_ids
        )

        candidate_summary: CandidateSummary | None = None
        candidate_response_id: str | None = None
        selected_entity = application_context.selected_entity
        if selected_entity is not None and selected_entity.entity_type == "candidate":
            record_decision = self._permission_evaluator.check_record(
                authorization,
                record=selected_entity,
                required_permission=_CANDIDATE_VIEW_PERMISSION,
            )
            if not record_decision.allowed:
                self._append_permission_denial(
                    app_id=app_id,
                    request_id=request_id,
                    identity=identity,
                    workspace_id=application_context.workspace.workspace_id,
                    target=selected_entity,
                    check=record_decision.check.value,
                    decision_code=record_decision.code.value,
                )
                raise CandidateAccessDeniedError
            adapter = self._adapter_registry.resolve(
                app_id,
                required_capability=AdapterCapability.GET_SELECTED_ENTITY_SUMMARY,
                request_id=request_id,
            )
            summary_response = await adapter.get_selected_entity_summary(
                GetSelectedEntitySummaryRequest(
                    request_id=request_id,
                    app_id=app_id,
                    trusted_identity=identity,
                    context=application_context,
                    requested_field_ids=_CANDIDATE_SUMMARY_FIELD_IDS,
                )
            )
            if summary_response.summary.entity != selected_entity:
                raise ContextUnavailableError
            candidate_summary = _candidate_summary(summary_response.summary)
            candidate_response_id = summary_response.adapter_response_id
            self._append_candidate_read(
                app_id=app_id,
                request_id=request_id,
                identity=identity,
                workspace_id=application_context.workspace.workspace_id,
                target=selected_entity,
                summary=candidate_summary,
            )

        context_trust = _resolved_trust(
            identity_response_id=identity_response.adapter_response_id,
            context_response_id=context_response.adapter_response_id,
            page_response_id=page_response.adapter_response_id,
            permissions_response_id=permissions_response.adapter_response_id,
            actions_response_id=actions_response.adapter_response_id,
            selected_entity=selected_entity,
            candidate_response_id=candidate_response_id,
        )
        return ResolvedPageContext(
            verification_source=ContextVerificationSource.APPLICATION_ADAPTER,
            adapter_response_id=context_response.adapter_response_id,
            component_trust=context_trust,
            request_id=request_id,
            app=application_context.app,
            page_id=application_context.page_id,
            identity=identity,
            workspace=application_context.workspace,
            selected_entity=selected_entity,
            permissions=permissions_response.authorization_facts.permissions,
            available_action_ids=available_action_ids,
            candidate_summary=candidate_summary,
            resolved_at=application_context.resolved_at,
            valid_until=application_context.valid_until,
        )

    def _append_identity_denial(self, *, app_id: str, request_id: RequestId) -> None:
        self._audit_recorder.append(
            self._audit_record(
                event_type=AuditEventType.IDENTITY_DENIED,
                outcome=AuditOutcome.DENIED,
                app_id=app_id,
                request_id=request_id,
                identity=None,
                workspace_id=None,
                target=None,
                details=BoundedMetadata(root={"decision_code": "identity_unverified"}),
            )
        )

    def _append_permission_denial(
        self,
        *,
        app_id: str,
        request_id: RequestId,
        identity: UserIdentity,
        workspace_id: str,
        target: SelectedEntityRef | None,
        check: str,
        decision_code: str,
    ) -> None:
        self._audit_recorder.append(
            self._audit_record(
                event_type=AuditEventType.PERMISSION_DENIED,
                outcome=AuditOutcome.DENIED,
                app_id=app_id,
                request_id=request_id,
                identity=identity,
                workspace_id=workspace_id,
                target=target,
                details=BoundedMetadata(root={"check": check, "decision_code": decision_code}),
            )
        )

    def _append_candidate_read(
        self,
        *,
        app_id: str,
        request_id: RequestId,
        identity: UserIdentity,
        workspace_id: str,
        target: SelectedEntityRef,
        summary: CandidateSummary,
    ) -> None:
        self._audit_recorder.append(
            self._audit_record(
                event_type=AuditEventType.CANDIDATE_READ,
                outcome=AuditOutcome.ALLOWED,
                app_id=app_id,
                request_id=request_id,
                identity=identity,
                workspace_id=workspace_id,
                target=target,
                details=BoundedMetadata(
                    root={
                        "visible_field_count": summary.visibility.visible_field_count,
                        "redacted_field_count": summary.visibility.redacted_field_count,
                        "redaction_applied": summary.visibility.redaction_applied,
                        "source": "application_adapter",
                    }
                ),
            )
        )

    def _audit_record(
        self,
        *,
        event_type: AuditEventType,
        outcome: AuditOutcome,
        app_id: str,
        request_id: RequestId,
        identity: UserIdentity | None,
        workspace_id: str | None,
        target: SelectedEntityRef | None,
        details: BoundedMetadata,
    ) -> AuditRecord:
        return AuditRecord(
            audit_id=f"audit-{uuid4()}",
            event_type=event_type,
            outcome=outcome,
            actor_user_id=identity.user_id if identity is not None else None,
            workspace_id=workspace_id,
            app_id=app_id,
            target=target,
            request_id=request_id,
            correlation_id=CorrelationId(root=request_id.root),
            details=details,
            occurred_at=self._clock(),
        )


def _resolved_trust(
    *,
    identity_response_id: str,
    context_response_id: str,
    page_response_id: str,
    permissions_response_id: str,
    actions_response_id: str,
    selected_entity: SelectedEntityRef | None,
    candidate_response_id: str | None,
) -> ResolvedContextTrust:
    def trusted(response_id: str) -> ContextComponentTrust:
        return ContextComponentTrust(
            verification_source=ContextVerificationSource.APPLICATION_ADAPTER,
            source_response_id=response_id,
        )

    return ResolvedContextTrust(
        app=trusted(context_response_id),
        identity=trusted(identity_response_id),
        page=trusted(page_response_id),
        workspace=trusted(context_response_id),
        selected_entity=trusted(context_response_id) if selected_entity is not None else None,
        permissions=trusted(permissions_response_id),
        available_actions=trusted(actions_response_id),
        candidate_summary=(
            trusted(candidate_response_id) if candidate_response_id is not None else None
        ),
    )


def _candidate_summary(summary: SelectedEntitySummary) -> CandidateSummary:
    return CandidateSummary(
        candidate_id=summary.entity.entity_id,
        visible_fields=tuple(_candidate_field(field) for field in summary.visible_fields),
        visibility=CandidateVisibilitySummary(
            visible_field_count=summary.visibility.visible_field_count,
            redacted_field_count=summary.visibility.redacted_field_count,
            redaction_applied=summary.visibility.redaction_applied,
            explanation_code=summary.visibility.explanation_code,
        ),
        source_adapter_response_id=summary.source_adapter_response_id,
        valid_for_request_id=summary.valid_for_request_id,
        retrieved_at=summary.retrieved_at,
    )


def _candidate_field(field: VisibleEntityField) -> VisibleCandidateField:
    value = field.value
    candidate_value: CandidateFieldValue
    if isinstance(value, EntityTextValue):
        candidate_value = CandidateTextValue(value=value.value)
    elif isinstance(value, EntityDateValue):
        candidate_value = CandidateDateValue(value=value.value)
    elif isinstance(value, EntityTimestampValue):
        candidate_value = CandidateTimestampValue(value=value.value)
    elif isinstance(value, EntityIntegerValue):
        candidate_value = CandidateIntegerValue(value=value.value)
    elif isinstance(value, EntityNumberValue):
        candidate_value = CandidateNumberValue(value=value.value)
    elif isinstance(value, EntityBooleanValue):
        candidate_value = CandidateBooleanValue(value=value.value)
    elif isinstance(value, EntityReferenceValue):
        candidate_value = CandidateReferenceValue(value=value.value)
    else:
        raise ContextUnavailableError
    return VisibleCandidateField(
        field_id=field.field_id,
        label=field.label,
        sensitivity=CandidateFieldSensitivity(field.sensitivity.value),
        value=candidate_value,
    )
