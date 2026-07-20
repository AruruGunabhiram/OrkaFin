"""Replay, expiry, tampering, and binding tests for Prompt 18 confirmations."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select

from orkafin.adapters.orka_ats import MockOrkaATSAdapter
from orkafin.core.dependencies import ApplicationDependencies
from orkafin.infrastructure.database.models import (
    ActionConfirmationModel,
    ActionExecutionModel,
    ActionProposalModel,
)
from orkafin.infrastructure.database.repositories import OrkaFinRepository

from ..context_support import build_context_application, context_hint

PROPOSAL_REQUEST_ID = "00000000-0000-4000-8000-000000001811"
CONFIRM_REQUEST_ID = "00000000-0000-4000-8000-000000001812"


async def _post(
    application: FastAPI,
    path: str,
    body: dict[str, object],
    *,
    request_id: str = CONFIRM_REQUEST_ID,
) -> Response:
    transport = ASGITransport(app=application, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post(path, json=body, headers={"X-Request-ID": request_id})


def _propose(application: FastAPI, *, start_date: str = "2026-10-06") -> dict[str, Any]:
    response = asyncio.run(
        _post(
            application,
            "/api/v1/action-proposals",
            {
                "action_id": "candidate.update_start_date",
                "parameters": {"start_date": start_date},
                "context": context_hint(),
            },
            request_id=PROPOSAL_REQUEST_ID,
        )
    )
    assert response.status_code == 201
    return response.json()


def _confirmation_body(
    proposal: dict[str, Any],
    *,
    decision: str = "accept",
    start_date: str = "2026-10-06",
    token: str | None = None,
    candidate_id: str = "CAND-1042",
) -> dict[str, object]:
    return {
        "decision": decision,
        "confirmation_token": token or proposal["confirmation"]["confirmation_token"],
        "parameters": {"start_date": start_date},
        "context": context_hint(candidate_id=candidate_id),
    }


def _confirm_path(proposal: dict[str, Any]) -> str:
    return f"/api/v1/action-proposals/{proposal['proposal_id']}/confirmations"


def _stored_statuses(
    dependencies: ApplicationDependencies, proposal_id: str
) -> tuple[str, str, int]:
    with dependencies.database.session_factory() as session:
        proposal = session.get(ActionProposalModel, proposal_id)
        confirmation = session.scalar(
            select(ActionConfirmationModel).where(
                ActionConfirmationModel.proposal_id == proposal_id
            )
        )
        executions = session.scalar(select(func.count()).select_from(ActionExecutionModel))
        assert proposal is not None and confirmation is not None
        return proposal.status, confirmation.status, executions or 0


def _action_audits(dependencies: ApplicationDependencies) -> tuple[object, ...]:
    with dependencies.database.session_factory() as session:
        return tuple(
            row
            for row in OrkaFinRepository(session).list_audit_records()
            if row.event_type.startswith("action_")
        )


def test_tampered_parameters_and_token_are_rejected_without_consuming_challenge(
    tmp_path: Path,
) -> None:
    application, dependencies = build_context_application(
        tmp_path / "tampering.db", subject_reference="admin"
    )
    proposal = _propose(application)
    path = _confirm_path(proposal)

    parameter_tamper = asyncio.run(
        _post(application, path, _confirmation_body(proposal, start_date="2026-10-07"))
    )
    token_tamper = asyncio.run(
        _post(application, path, _confirmation_body(proposal, token="A" * 43))
    )

    assert parameter_tamper.status_code == 403
    assert parameter_tamper.json()["code"] == "action_confirmation_invalid"
    assert token_tamper.status_code == 403
    assert token_tamper.json()["code"] == "action_confirmation_invalid"
    assert "parameter" not in parameter_tamper.json()["message"].lower()
    assert _stored_statuses(dependencies, proposal["proposal_id"]) == (
        "proposed",
        "issued",
        0,
    )

    accepted = asyncio.run(_post(application, path, _confirmation_body(proposal)))
    replayed = asyncio.run(_post(application, path, _confirmation_body(proposal)))

    assert accepted.status_code == 200
    assert replayed.status_code == 409
    assert replayed.json()["code"] == "action_state_conflict"
    assert _stored_statuses(dependencies, proposal["proposal_id"]) == (
        "confirmed",
        "accepted",
        0,
    )
    tampering_reasons = [
        row.details_json["reason_code"]
        for row in _action_audits(dependencies)
        if row.event_type == "action_tampering_rejected"
    ]
    assert tampering_reasons == [
        "parameter_mismatch",
        "confirmation_mismatch",
        "confirmation_replayed",
    ]


def test_token_is_bound_to_its_proposal_and_exact_target(tmp_path: Path) -> None:
    application, dependencies = build_context_application(
        tmp_path / "proposal-target-binding.db", subject_reference="admin"
    )
    first = _propose(application, start_date="2026-10-06")
    second = _propose(application, start_date="2026-10-07")

    cross_proposal = asyncio.run(
        _post(
            application,
            _confirm_path(second),
            _confirmation_body(
                second,
                start_date="2026-10-07",
                token=first["confirmation"]["confirmation_token"],
            ),
        )
    )
    changed_target = asyncio.run(
        _post(
            application,
            _confirm_path(first),
            _confirmation_body(first, candidate_id="CAND-1043"),
        )
    )

    assert cross_proposal.status_code == 403
    assert changed_target.status_code == 403
    assert _stored_statuses(dependencies, first["proposal_id"]) == (
        "proposed",
        "issued",
        0,
    )
    assert _stored_statuses(dependencies, second["proposal_id"]) == (
        "proposed",
        "issued",
        0,
    )


def test_expired_token_transitions_both_states_and_never_executes(tmp_path: Path) -> None:
    application, dependencies = build_context_application(
        tmp_path / "expired.db", subject_reference="admin"
    )
    proposal = _propose(application)
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

    response = asyncio.run(
        _post(application, _confirm_path(proposal), _confirmation_body(proposal))
    )

    assert response.status_code == 410
    assert response.json()["code"] == "action_confirmation_expired"
    assert _stored_statuses(dependencies, proposal["proposal_id"]) == (
        "expired",
        "expired",
        0,
    )
    expired = [
        row
        for row in _action_audits(dependencies)
        if row.event_type == "action_confirmation_expired"
    ]
    assert len(expired) == 1
    assert expired[0].details_json["reason_code"] == "ttl_elapsed"


def test_wrong_verified_user_is_rejected_and_original_user_can_still_confirm(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "wrong-user.db"
    admin_application, dependencies = build_context_application(
        database_path, subject_reference="admin"
    )
    proposal = _propose(admin_application)
    recruiter_application, _ = build_context_application(
        database_path, subject_reference="recruiter"
    )

    wrong_user = asyncio.run(
        _post(recruiter_application, _confirm_path(proposal), _confirmation_body(proposal))
    )

    assert wrong_user.status_code == 403
    assert wrong_user.json()["code"] == "action_confirmation_invalid"
    assert _stored_statuses(dependencies, proposal["proposal_id"]) == (
        "proposed",
        "issued",
        0,
    )
    accepted = asyncio.run(
        _post(admin_application, _confirm_path(proposal), _confirmation_body(proposal))
    )
    assert accepted.status_code == 200


class _SwitchableWorkspaceAdapter(MockOrkaATSAdapter):
    def switch_workspace(self) -> None:
        self._fixtures["workspaces"]["workspace_other"] = {"display_name": "Other Workspace"}
        self._fixtures["users"]["admin"]["workspace_id"] = "workspace_other"


def test_wrong_workspace_binding_is_rejected_without_consuming_token(tmp_path: Path) -> None:
    adapter = _SwitchableWorkspaceAdapter()
    application, dependencies = build_context_application(
        tmp_path / "wrong-workspace.db",
        subject_reference="admin",
        adapter_factory=lambda: adapter,
    )
    proposal = _propose(application)
    adapter.switch_workspace()

    response = asyncio.run(
        _post(application, _confirm_path(proposal), _confirmation_body(proposal))
    )

    assert response.status_code == 403
    assert response.json()["code"] == "action_confirmation_invalid"
    assert _stored_statuses(dependencies, proposal["proposal_id"]) == (
        "proposed",
        "issued",
        0,
    )
    tampering = [
        row for row in _action_audits(dependencies) if row.event_type == "action_tampering_rejected"
    ]
    assert tampering[-1].details_json["reason_code"] == ("identity_workspace_or_target_mismatch")


def test_cancelled_proposal_cannot_be_confirmed_or_reused(tmp_path: Path) -> None:
    application, dependencies = build_context_application(
        tmp_path / "cancelled.db", subject_reference="admin"
    )
    proposal = _propose(application)
    path = _confirm_path(proposal)

    cancelled = asyncio.run(
        _post(application, path, _confirmation_body(proposal, decision="reject"))
    )
    retried = asyncio.run(_post(application, path, _confirmation_body(proposal)))

    assert cancelled.status_code == 200
    assert cancelled.json()["proposal_status"] == "cancelled"
    assert cancelled.json()["confirmation_status"] == "rejected"
    assert cancelled.json()["execution_ready"] is False
    assert retried.status_code == 409
    assert _stored_statuses(dependencies, proposal["proposal_id"]) == (
        "cancelled",
        "rejected",
        0,
    )
    event_types = [row.event_type for row in _action_audits(dependencies)]
    assert "action_confirmation_rejected" in event_types
    assert "action_tampering_rejected" in event_types
