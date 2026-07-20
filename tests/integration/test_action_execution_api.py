"""End-to-end safety coverage for the one approved mock action execution."""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select

from orkafin.adapters import AdapterCapability, AdapterErrorCode
from orkafin.adapters.orka_ats import (
    MockFailureSimulation,
    MockOrkaATSAdapter,
    MockOrkaATSStateStore,
)
from orkafin.core.dependencies import ApplicationDependencies
from orkafin.infrastructure.database.models import (
    ActionConfirmationModel,
    ActionExecutionModel,
    ActionProposalModel,
)
from orkafin.infrastructure.database.repositories import OrkaFinRepository
from orkafin.knowledge import KnowledgeIndex, load_knowledge
from orkafin.knowledge.models import ActionCatalogItem

from ..context_support import build_context_application, context_hint

PROPOSE_ID = "00000000-0000-4000-8000-000000001901"
CONFIRM_ID = "00000000-0000-4000-8000-000000001902"
EXECUTE_ID = "00000000-0000-4000-8000-000000001903"
REPLAY_ID = "00000000-0000-4000-8000-000000001904"
NEW_START_DATE = "2026-10-06"


async def _post(
    application: FastAPI,
    path: str,
    body: dict[str, object],
    *,
    request_id: str,
) -> Response:
    transport = ASGITransport(app=application, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post(path, json=body, headers={"X-Request-ID": request_id})


def _build(
    tmp_path: Path,
    *,
    simulation: MockFailureSimulation | None = None,
    adapter_type: type[MockOrkaATSAdapter] = MockOrkaATSAdapter,
    knowledge_index: KnowledgeIndex | None = None,
) -> tuple[FastAPI, ApplicationDependencies, MockOrkaATSAdapter, MockOrkaATSStateStore]:
    state = MockOrkaATSStateStore(tmp_path / "mock-state.json")
    state.reset()
    adapter = adapter_type(state_path=state.path, simulation=simulation)
    application, dependencies = build_context_application(
        tmp_path / "orkafin.db",
        subject_reference="admin",
        adapter_factory=lambda: adapter,
        knowledge_index=knowledge_index,
    )
    return application, dependencies, adapter, state


def _propose(application: FastAPI) -> dict[str, Any]:
    proposal_response = asyncio.run(
        _post(
            application,
            "/api/v1/action-proposals",
            {
                "action_id": "candidate.update_start_date",
                "parameters": {"start_date": NEW_START_DATE},
                "context": context_hint(),
            },
            request_id=PROPOSE_ID,
        )
    )
    assert proposal_response.status_code == 201
    return proposal_response.json()


def _prepare(application: FastAPI) -> dict[str, Any]:
    proposal = _propose(application)
    confirmation_response = asyncio.run(
        _post(
            application,
            f"/api/v1/action-proposals/{proposal['proposal_id']}/confirmations",
            {
                "decision": "accept",
                "confirmation_token": proposal["confirmation"]["confirmation_token"],
                "parameters": {"start_date": NEW_START_DATE},
                "context": context_hint(),
            },
            request_id=CONFIRM_ID,
        )
    )
    assert confirmation_response.status_code == 200
    assert confirmation_response.json()["execution_state"] == "ready"
    return proposal


def _execute(
    application: FastAPI,
    proposal: dict[str, Any],
    *,
    request_id: str = EXECUTE_ID,
) -> Response:
    return asyncio.run(
        _post(
            application,
            f"/api/v1/action-proposals/{proposal['proposal_id']}:execute",
            {"context": context_hint()},
            request_id=request_id,
        )
    )


def _stored_statuses(
    dependencies: ApplicationDependencies, proposal_id: str
) -> tuple[str, str, ActionExecutionModel]:
    with dependencies.database.session_factory() as session:
        proposal = session.get(ActionProposalModel, proposal_id)
        confirmation = session.scalar(
            select(ActionConfirmationModel).where(
                ActionConfirmationModel.proposal_id == proposal_id
            )
        )
        execution = session.scalar(
            select(ActionExecutionModel).where(ActionExecutionModel.proposal_id == proposal_id)
        )
        assert proposal is not None and confirmation is not None and execution is not None
        return proposal.status, confirmation.status, execution


def _action_audits(dependencies: ApplicationDependencies) -> tuple[object, ...]:
    with dependencies.database.session_factory() as session:
        return tuple(
            row
            for row in OrkaFinRepository(session).list_audit_records()
            if row.event_type.startswith("action_")
        )


def test_execution_before_explicit_confirmation_is_rejected_without_adapter_dispatch(
    tmp_path: Path,
) -> None:
    application, dependencies, _, state = _build(tmp_path)
    proposal = _propose(application)

    response = _execute(application, proposal)

    assert response.status_code == 409
    assert response.json()["code"] == "action_state_conflict"
    assert "No changes were made" in response.json()["message"]
    with dependencies.database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ActionExecutionModel)) == 0
    assert state.snapshot().candidate_start_dates == {}
    assert state.snapshot().executions == {}
    events = [row.event_type for row in _action_audits(dependencies)]
    assert events.count("action_execution_attempted") == 1
    assert "action_tampering_rejected" in events
    assert "action_adapter_requested" not in events


def test_success_requires_receipt_mutates_only_mock_state_and_writes_complete_audit(
    tmp_path: Path,
) -> None:
    application, dependencies, _, state = _build(tmp_path)
    proposal = _prepare(application)

    response = _execute(application, proposal)

    assert response.status_code == 200
    payload = response.json()
    execution = payload["execution"]
    assert payload["idempotent_replay"] is False
    assert execution["status"] == "succeeded"
    assert execution["safe_message"] == (
        "Mock OrkaATS confirmed the candidate start date was updated."
    )
    receipt = execution["adapter_receipt"]
    assert receipt["outcome"] == "succeeded"
    assert receipt["adapter_id"] == "mock_orka_ats"
    assert receipt["action_id"] == "candidate.update_start_date"
    assert receipt["action_version"] == "1.0.0"
    assert receipt["request_id"] == EXECUTE_ID
    assert receipt["idempotency_key"] == execution["idempotency_key"]

    proposal_status, confirmation_status, stored = _stored_statuses(
        dependencies, proposal["proposal_id"]
    )
    assert (proposal_status, confirmation_status, stored.status) == (
        "executed",
        "consumed",
        "succeeded",
    )
    assert stored.adapter_receipt_json == receipt
    snapshot = state.snapshot()
    assert snapshot.candidate_start_dates["CAND-1042"] == date.fromisoformat(NEW_START_DATE)
    assert len(snapshot.executions) == 1

    context_response = asyncio.run(
        _post(
            application,
            "/api/v1/contexts:resolve",
            context_hint(),
            request_id="00000000-0000-4000-8000-000000001905",
        )
    )
    fields = context_response.json()["candidate_summary"]["visible_fields"]
    start_date = next(field for field in fields if field["field_id"] == "start_date")
    assert start_date["value"]["value"] == NEW_START_DATE

    event_counts = Counter(row.event_type for row in _action_audits(dependencies))
    assert event_counts["action_execution_attempted"] == 1
    assert event_counts["action_permission_checked"] == 3
    assert event_counts["action_adapter_requested"] == 1
    assert event_counts["action_execution_succeeded"] == 1
    assert event_counts["action_final_result"] == 1


def test_mock_state_reset_rolls_back_values_and_clears_receipts(tmp_path: Path) -> None:
    application, _, _, state = _build(tmp_path)
    proposal = _prepare(application)
    response = _execute(application, proposal)
    assert response.json()["execution"]["status"] == "succeeded"
    assert state.snapshot().candidate_start_dates
    assert state.snapshot().executions

    state.reset()

    assert state.snapshot().candidate_start_dates == {}
    assert state.snapshot().executions == {}


class RevocablePermissionAdapter(MockOrkaATSAdapter):
    def revoke_execution_permission(self) -> None:
        user = self._fixtures["users"]["admin"]
        user["permissions"] = [
            value for value in user["permissions"] if value != "candidate.update_start_date"
        ]
        user["available_action_ids"] = []


class RevocableVisibilityAdapter(MockOrkaATSAdapter):
    execution_call_count = 0

    def revoke_candidate_visibility(self) -> None:
        self._fixtures["users"]["admin"]["record_grants"].pop("CAND-1042")

    async def execute_approved_action(self, request: Any) -> Any:
        self.execution_call_count += 1
        return await super().execute_approved_action(request)


class LastMomentConflictAdapter(MockOrkaATSAdapter):
    async def execute_approved_action(self, request: Any) -> Any:
        self._state.set_candidate_start_date("CAND-1042", date(2026, 9, 29))
        return await super().execute_approved_action(request)


class RecordingExecutionAdapter(MockOrkaATSAdapter):
    last_execution_request: Any = None

    async def execute_approved_action(self, request: Any) -> Any:
        self.last_execution_request = request
        return await super().execute_approved_action(request)


def test_permission_revoked_after_confirmation_is_rejected_without_adapter_write(
    tmp_path: Path,
) -> None:
    application, dependencies, adapter, state = _build(
        tmp_path, adapter_type=RevocablePermissionAdapter
    )
    assert isinstance(adapter, RevocablePermissionAdapter)
    proposal = _prepare(application)
    adapter.revoke_execution_permission()

    response = _execute(application, proposal)

    assert response.status_code == 403
    assert response.json()["code"] == "action_access_denied"
    assert "No changes were made" in response.json()["message"]
    proposal_status, confirmation_status, execution = _stored_statuses(
        dependencies, proposal["proposal_id"]
    )
    assert (proposal_status, confirmation_status, execution.status) == (
        "failed",
        "consumed",
        "rejected",
    )
    assert state.snapshot().candidate_start_dates == {}
    events = [row.event_type for row in _action_audits(dependencies)]
    assert "action_adapter_requested" not in events
    assert "action_execution_failed" in events
    assert "action_final_result" in events


def test_candidate_visibility_revocation_is_terminal_once_without_adapter_dispatch(
    tmp_path: Path,
) -> None:
    application, dependencies, adapter, state = _build(
        tmp_path, adapter_type=RevocableVisibilityAdapter
    )
    assert isinstance(adapter, RevocableVisibilityAdapter)
    proposal = _prepare(application)
    adapter.revoke_candidate_visibility()

    response = _execute(application, proposal)
    confirmation_reuse = asyncio.run(
        _post(
            application,
            f"/api/v1/action-proposals/{proposal['proposal_id']}/confirmations",
            {
                "decision": "accept",
                "confirmation_token": proposal["confirmation"]["confirmation_token"],
                "parameters": {"start_date": NEW_START_DATE},
                "context": context_hint(),
            },
            request_id="00000000-0000-4000-8000-000000001907",
        )
    )

    assert response.status_code == 403
    assert response.json()["schema_version"] == "v1"
    assert response.json()["code"] == "action_access_denied"
    assert response.json()["message"] == (
        "Execution permission is no longer available. No changes were made."
    )
    assert confirmation_reuse.status_code == 409
    assert confirmation_reuse.json()["code"] == "action_state_conflict"
    proposal_status, confirmation_status, execution = _stored_statuses(
        dependencies, proposal["proposal_id"]
    )
    assert (proposal_status, confirmation_status, execution.status) == (
        "failed",
        "consumed",
        "rejected",
    )
    assert execution.adapter_receipt_json is None
    assert execution.safe_message == (
        "OrkaATS could not complete the request. No changes were made."
    )
    assert adapter.execution_call_count == 0
    assert state.snapshot().candidate_start_dates == {}
    assert state.snapshot().executions == {}
    with dependencies.database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ActionExecutionModel)) == 1
    event_counts = Counter(row.event_type for row in _action_audits(dependencies))
    assert event_counts["action_execution_attempted"] == 1
    assert event_counts["action_permission_checked"] == 3
    assert event_counts["action_adapter_requested"] == 0
    assert event_counts["action_execution_succeeded"] == 0
    assert event_counts["action_execution_failed"] == 1
    assert event_counts["action_final_result"] == 1
    with dependencies.database.session_factory() as session:
        audits = OrkaFinRepository(session).list_audit_records()
    all_event_counts = Counter(row.event_type for row in audits)
    assert all_event_counts["permission_denied"] == 1
    execution_permission = next(
        row
        for row in audits
        if row.event_type == "action_permission_checked"
        and row.details_json.get("phase") == "execution"
    )
    assert execution_permission.details_json["check"] == "candidate_visibility"
    assert execution_permission.details_json["decision_code"] == "candidate_access_denied"
    execution_failure = next(row for row in audits if row.event_type == "action_execution_failed")
    assert execution_failure.details_json["reason_code"] == (
        "candidate_visibility_revoked_before_execution"
    )


def test_candidate_change_between_confirmation_and_execution_conflicts(tmp_path: Path) -> None:
    application, dependencies, _, state = _build(tmp_path)
    proposal = _prepare(application)
    externally_changed = date(2026, 9, 30)
    state.set_candidate_start_date("CAND-1042", externally_changed)

    response = _execute(application, proposal)

    assert response.status_code == 409
    assert response.json()["code"] == "action_state_conflict"
    _, confirmation_status, execution = _stored_statuses(dependencies, proposal["proposal_id"])
    assert confirmation_status == "consumed"
    assert execution.status == "conflict"
    assert state.snapshot().candidate_start_dates["CAND-1042"] == externally_changed


def test_mock_adapter_rechecks_state_after_orkafin_preflight(tmp_path: Path) -> None:
    application, dependencies, _, state = _build(
        tmp_path,
        adapter_type=LastMomentConflictAdapter,
    )
    proposal = _prepare(application)

    response = _execute(application, proposal)

    assert response.status_code == 200
    execution = response.json()["execution"]
    assert execution["status"] == "failed"
    assert execution["safe_message"] == (
        "OrkaATS could not complete the request. No changes were made."
    )
    assert state.snapshot().candidate_start_dates["CAND-1042"] == date(2026, 9, 29)
    assert state.snapshot().executions == {}
    assert _stored_statuses(dependencies, proposal["proposal_id"])[2].status == "failed"


def test_adapter_validation_error_is_failed_and_never_fabricated_as_success(
    tmp_path: Path,
) -> None:
    application, dependencies, _, state = _build(
        tmp_path,
        simulation=MockFailureSimulation(
            failures={AdapterCapability.EXECUTE_APPROVED_ACTION: AdapterErrorCode.VALIDATION_FAILED}
        ),
    )
    proposal = _prepare(application)

    response = _execute(application, proposal)

    assert response.status_code == 200
    execution = response.json()["execution"]
    assert execution["status"] == "failed"
    assert execution["adapter_receipt"] is None
    assert execution["safe_message"] == (
        "OrkaATS could not complete the request. No changes were made."
    )
    assert _stored_statuses(dependencies, proposal["proposal_id"])[2].status == "failed"
    assert state.snapshot().candidate_start_dates == {}


def test_execution_timeout_is_unknown_and_requires_idempotency_reconciliation(
    tmp_path: Path,
) -> None:
    application, dependencies, _, state = _build(
        tmp_path,
        simulation=MockFailureSimulation(
            failures={AdapterCapability.EXECUTE_APPROVED_ACTION: AdapterErrorCode.TIMEOUT}
        ),
    )
    proposal = _prepare(application)

    response = _execute(application, proposal)

    assert response.status_code == 200
    execution = response.json()["execution"]
    assert execution["status"] == "unknown"
    assert execution["adapter_receipt"] is None
    assert execution["idempotency_key"].startswith("action-")
    assert "reconcile" in execution["safe_message"]
    assert "No changes were made" not in execution["safe_message"]
    assert _stored_statuses(dependencies, proposal["proposal_id"])[2].status == "unknown"
    assert state.snapshot().candidate_start_dates == {}
    events = [row.event_type for row in _action_audits(dependencies)]
    assert "action_execution_unknown" in events
    assert "action_final_result" in events


def test_adapter_unavailable_after_reservation_is_unknown_and_not_retried(
    tmp_path: Path,
) -> None:
    application, dependencies, _, state = _build(
        tmp_path,
        simulation=MockFailureSimulation(
            failures={AdapterCapability.EXECUTE_APPROVED_ACTION: AdapterErrorCode.UNAVAILABLE}
        ),
    )
    proposal = _prepare(application)

    response = _execute(application, proposal)

    assert response.status_code == 200
    execution = response.json()["execution"]
    assert execution["status"] == "unknown"
    assert "No changes were made" not in execution["safe_message"]
    assert state.snapshot().executions == {}
    counts = Counter(row.event_type for row in _action_audits(dependencies))
    assert counts["action_adapter_requested"] == 1
    assert counts["action_execution_unknown"] == 1


def test_malformed_receipt_cannot_create_success_even_when_mock_state_changed(
    tmp_path: Path,
) -> None:
    application, dependencies, _, state = _build(
        tmp_path,
        simulation=MockFailureSimulation(malformed_execution_receipt=True),
    )
    proposal = _prepare(application)

    response = _execute(application, proposal)

    assert response.status_code == 200
    execution = response.json()["execution"]
    assert execution["status"] == "unknown"
    assert execution["adapter_receipt"] is None
    assert "No changes were made" not in execution["safe_message"]
    assert state.snapshot().candidate_start_dates["CAND-1042"] == date.fromisoformat(NEW_START_DATE)
    assert _stored_statuses(dependencies, proposal["proposal_id"])[2].status == "unknown"


def test_duplicate_execution_is_an_idempotent_replay_and_confirmation_stays_consumed(
    tmp_path: Path,
) -> None:
    application, dependencies, _, state = _build(tmp_path)
    proposal = _prepare(application)
    first = _execute(application, proposal)

    replay = _execute(application, proposal, request_id=REPLAY_ID)
    reused_confirmation = asyncio.run(
        _post(
            application,
            f"/api/v1/action-proposals/{proposal['proposal_id']}/confirmations",
            {
                "decision": "accept",
                "confirmation_token": proposal["confirmation"]["confirmation_token"],
                "parameters": {"start_date": NEW_START_DATE},
                "context": context_hint(),
            },
            request_id="00000000-0000-4000-8000-000000001906",
        )
    )

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json()["idempotent_replay"] is True
    assert replay.json()["execution"] == first.json()["execution"]
    assert reused_confirmation.status_code == 409
    assert reused_confirmation.json()["code"] == "action_state_conflict"
    with dependencies.database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ActionExecutionModel)) == 1
    assert len(state.snapshot().executions) == 1
    event_counts = Counter(row.event_type for row in _action_audits(dependencies))
    assert event_counts["action_adapter_requested"] == 1
    assert event_counts["action_execution_succeeded"] == 1
    assert event_counts["action_final_result"] == 2


def test_mock_adapter_exact_idempotency_replay_returns_original_receipt(tmp_path: Path) -> None:
    application, _, adapter, state = _build(
        tmp_path,
        adapter_type=RecordingExecutionAdapter,
    )
    assert isinstance(adapter, RecordingExecutionAdapter)
    proposal = _prepare(application)
    first = _execute(application, proposal)
    assert first.json()["execution"]["status"] == "succeeded"
    assert adapter.last_execution_request is not None

    replay = asyncio.run(adapter.execute_approved_action(adapter.last_execution_request))

    assert replay.receipt.receipt_id == first.json()["execution"]["adapter_receipt"]["receipt_id"]
    assert replay.receipt.idempotency_key.root == first.json()["execution"]["idempotency_key"]
    assert len(state.snapshot().executions) == 1


def test_expired_accepted_confirmation_is_consumed_and_never_sent_to_adapter(
    tmp_path: Path,
) -> None:
    application, dependencies, _, state = _build(tmp_path)
    proposal = _prepare(application)
    with dependencies.database.session_factory.begin() as session:
        stored_proposal = session.get(ActionProposalModel, proposal["proposal_id"])
        stored_confirmation = session.scalar(
            select(ActionConfirmationModel).where(
                ActionConfirmationModel.proposal_id == proposal["proposal_id"]
            )
        )
        assert stored_proposal is not None and stored_confirmation is not None
        stored_proposal.expires_at = stored_proposal.created_at
        stored_confirmation.expires_at = stored_confirmation.issued_at

    response = _execute(application, proposal)

    assert response.status_code == 410
    assert response.json()["code"] == "action_confirmation_expired"
    _, confirmation_status, execution = _stored_statuses(dependencies, proposal["proposal_id"])
    assert confirmation_status == "consumed"
    assert execution.status == "rejected"
    assert state.snapshot().executions == {}
    assert "action_adapter_requested" not in [
        row.event_type for row in _action_audits(dependencies)
    ]


def test_parameter_hash_is_recomputed_at_execution_and_tampering_conflicts(
    tmp_path: Path,
) -> None:
    application, dependencies, _, state = _build(tmp_path)
    proposal = _prepare(application)
    with dependencies.database.session_factory.begin() as session:
        stored_proposal = session.get(ActionProposalModel, proposal["proposal_id"])
        stored_confirmation = session.scalar(
            select(ActionConfirmationModel).where(
                ActionConfirmationModel.proposal_id == proposal["proposal_id"]
            )
        )
        assert stored_proposal is not None and stored_confirmation is not None
        stored_proposal.parameter_hash = "0" * 64
        stored_confirmation.parameter_hash = "0" * 64

    response = _execute(application, proposal)

    assert response.status_code == 409
    assert response.json()["code"] == "action_state_conflict"
    assert _stored_statuses(dependencies, proposal["proposal_id"])[2].status == "conflict"
    assert state.snapshot().executions == {}


def test_action_definition_version_change_after_confirmation_conflicts(tmp_path: Path) -> None:
    knowledge_root = Path(__file__).resolve().parents[2] / "knowledge" / "orka_ats"
    original_index = load_knowledge(knowledge_root)
    mutable_actions = dict(original_index.actions_by_id)
    mutable_index = replace(original_index, actions_by_id=mutable_actions)
    application, dependencies, _, state = _build(
        tmp_path,
        knowledge_index=mutable_index,
    )
    proposal = _prepare(application)
    original = mutable_actions["candidate.update_start_date"]
    changed_action = original.action.model_copy(update={"action_version": "1.0.1"})
    changed_provenance = original.provenance.model_copy(update={"content_version": "1.0.1"})
    mutable_actions["candidate.update_start_date"] = ActionCatalogItem(
        action=changed_action,
        aliases=original.aliases,
        purpose=original.purpose,
        supported_roles=original.supported_roles,
        page_ids=original.page_ids,
        feature_ids=original.feature_ids,
        related_action_ids=original.related_action_ids,
        provenance=changed_provenance,
    )

    response = _execute(application, proposal)

    assert response.status_code == 409
    assert response.json()["code"] == "action_state_conflict"
    assert _stored_statuses(dependencies, proposal["proposal_id"])[2].status == "conflict"
    assert state.snapshot().executions == {}
