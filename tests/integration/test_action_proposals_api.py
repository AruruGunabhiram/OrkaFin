"""Integration coverage for the single confirmation-only action endpoint pair."""

from __future__ import annotations

import asyncio
import hashlib
from collections import Counter
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select

from orkafin.adapters import AdapterCapability, AdapterErrorCode
from orkafin.adapters.orka_ats import MockFailureSimulation, MockOrkaATSAdapter
from orkafin.core.dependencies import ApplicationDependencies
from orkafin.infrastructure.database.models import (
    ActionConfirmationModel,
    ActionExecutionModel,
    ActionProposalModel,
)
from orkafin.infrastructure.database.repositories import OrkaFinRepository

from ..context_support import build_context_application, context_hint

PROPOSAL_REQUEST_ID = "00000000-0000-4000-8000-000000001801"
CONFIRM_REQUEST_ID = "00000000-0000-4000-8000-000000001802"


def _proposal_body(
    *,
    start_date: str = "2026-10-06",
    candidate_id: str = "CAND-1042",
    action_id: str = "candidate.update_start_date",
) -> dict[str, object]:
    return {
        "action_id": action_id,
        "parameters": {"start_date": start_date},
        "context": context_hint(candidate_id=candidate_id),
    }


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


def _action_audit_rows(dependencies: ApplicationDependencies) -> tuple[object, ...]:
    with dependencies.database.session_factory() as session:
        return tuple(
            row
            for row in OrkaFinRepository(session).list_audit_records()
            if row.event_type.startswith("action_")
        )


def test_proposal_preview_and_confirmation_are_persisted_without_execution(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    application, dependencies = build_context_application(
        tmp_path / "confirmed-action.db",
        subject_reference="admin",
    )

    proposal_response = asyncio.run(
        _post(
            application,
            "/api/v1/action-proposals",
            _proposal_body(),
            request_id=PROPOSAL_REQUEST_ID,
        )
    )

    assert proposal_response.status_code == 201
    proposed = proposal_response.json()
    preview = proposed["preview"]
    assert preview == {
        "schema_version": "v1",
        "action_id": "candidate.update_start_date",
        "action_version": "1.0.0",
        "owning_app_id": "orka_ats",
        "owning_app_display_name": "Mock OrkaATS",
        "target_candidate_id": "CAND-1042",
        "affected_user_id": "mock-user-admin",
        "affected_user_display_name": "Synthetic Administrator",
        "affected_workspace_id": "workspace_recruiting_alpha",
        "affected_workspace_display_name": "Synthetic Recruiting Alpha",
        "summary": "Prepare a candidate start-date update for confirmation.",
        "changes": [
            {
                "schema_version": "v1",
                "field_label": "Start date",
                "old_value": "2026-08-17",
                "new_value": "2026-10-06",
            }
        ],
        "reversible": True,
        "warnings": [
            "Mock confirmation only: confirming does not update OrkaATS or candidate data.",
            "Execution stays disabled until a separate Prompt 19 human approval.",
            (
                "OrkaATS must revalidate current permissions, state, and business rules "
                "before any future execution."
            ),
        ],
    }
    assert proposed["proposal_status"] == "proposed"
    assert proposed["execution_ready"] is False
    assert proposed["execution_enabled"] is False
    assert proposed["execution_state"] == "not_started"
    assert "parameter_hash" not in proposal_response.text
    assert "confirmation_secret_hash" not in proposal_response.text
    token = proposed["confirmation"]["confirmation_token"]
    token_digest = hashlib.sha256(token.encode()).hexdigest()
    assert len(token) >= 43
    assert token_digest not in proposal_response.text

    with dependencies.database.session_factory() as session:
        proposal = session.get(ActionProposalModel, proposed["proposal_id"])
        confirmation = session.scalar(
            select(ActionConfirmationModel).where(
                ActionConfirmationModel.proposal_id == proposed["proposal_id"]
            )
        )
        assert proposal is not None
        assert confirmation is not None
        assert proposal.request_id == PROPOSAL_REQUEST_ID
        assert proposal.idempotency_key.startswith("action-")
        assert confirmation.confirmation_secret_hash == token_digest
        assert token not in str(confirmation.__dict__)
        assert session.scalar(select(func.count()).select_from(ActionExecutionModel)) == 0

    confirmation_response = asyncio.run(
        _post(
            application,
            f"/api/v1/action-proposals/{proposed['proposal_id']}/confirmations",
            {
                "decision": "accept",
                "confirmation_token": token,
                "parameters": {"start_date": "2026-10-06"},
                "context": context_hint(),
            },
            request_id=CONFIRM_REQUEST_ID,
        )
    )

    assert confirmation_response.status_code == 200
    confirmed = confirmation_response.json()
    assert confirmed["proposal_status"] == "confirmed"
    assert confirmed["confirmation_status"] == "accepted"
    assert confirmed["execution_ready"] is True
    assert confirmed["execution_enabled"] is False
    assert confirmed["execution_state"] == "not_started"
    assert confirmed["message"].endswith("no action was executed.")
    assert "confirmation_token" not in confirmation_response.text

    with dependencies.database.session_factory() as session:
        proposal = session.get(ActionProposalModel, proposed["proposal_id"])
        confirmation = session.scalar(
            select(ActionConfirmationModel).where(
                ActionConfirmationModel.proposal_id == proposed["proposal_id"]
            )
        )
        assert proposal is not None and proposal.status == "confirmed"
        assert confirmation is not None and confirmation.status == "accepted"
        assert session.scalar(select(func.count()).select_from(ActionExecutionModel)) == 0

    context_response = asyncio.run(
        _post(
            application,
            "/api/v1/contexts:resolve",
            context_hint(),
            request_id="00000000-0000-4000-8000-000000001803",
        )
    )
    assert context_response.status_code == 200
    start_date_fields = [
        field
        for field in context_response.json()["candidate_summary"]["visible_fields"]
        if field["field_id"] == "start_date"
    ]
    assert start_date_fields[0]["value"] == {
        "schema_version": "v1",
        "kind": "date",
        "value": "2026-08-17",
    }

    action_events = Counter(row.event_type for row in _action_audit_rows(dependencies))
    assert action_events == Counter(
        {
            "action_permission_checked": 2,
            "action_proposed": 1,
            "action_confirmation_issued": 1,
            "action_confirmed": 1,
        }
    )
    assert all("hash" not in str(row.details_json) for row in _action_audit_rows(dependencies))
    assert token not in caplog.text
    assert token_digest not in caplog.text


@pytest.mark.parametrize(
    ("subject", "candidate_id", "expected_code", "forbidden_marker"),
    (
        ("recruiter", "CAND-1042", "action_access_denied", "Taylor Example"),
        ("admin", "CAND-1099", "candidate_access_denied", "Private Synthetic Candidate"),
    ),
)
def test_missing_permission_or_invisible_candidate_creates_no_proposal(
    tmp_path: Path,
    subject: str,
    candidate_id: str,
    expected_code: str,
    forbidden_marker: str,
) -> None:
    application, dependencies = build_context_application(
        tmp_path / f"denied-{subject}.db",
        subject_reference=subject,
    )

    response = asyncio.run(
        _post(
            application,
            "/api/v1/action-proposals",
            _proposal_body(candidate_id=candidate_id),
            request_id=PROPOSAL_REQUEST_ID,
        )
    )

    assert response.status_code == 403
    assert response.json()["code"] == expected_code
    assert forbidden_marker not in response.text
    assert candidate_id not in response.text
    with dependencies.database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ActionProposalModel)) == 0


@pytest.mark.parametrize(
    ("body", "expected_code"),
    (
        (_proposal_body(start_date="2026-02-30"), "validation_error"),
        (_proposal_body(start_date="2026-08-17"), "action_input_invalid"),
        (_proposal_body(action_id="candidate.delete"), "action_not_available"),
    ),
)
def test_invalid_date_value_or_uncatalogued_action_creates_no_proposal(
    tmp_path: Path,
    body: dict[str, object],
    expected_code: str,
) -> None:
    application, dependencies = build_context_application(
        tmp_path / f"invalid-{expected_code}.db",
        subject_reference="admin",
    )

    response = asyncio.run(
        _post(
            application,
            "/api/v1/action-proposals",
            body,
            request_id=PROPOSAL_REQUEST_ID,
        )
    )

    assert response.status_code in {404, 422}
    assert response.json()["code"] == expected_code
    with dependencies.database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ActionProposalModel)) == 0


def test_adapter_unavailable_returns_no_preview_or_proposal(tmp_path: Path) -> None:
    def failing_adapter() -> MockOrkaATSAdapter:
        return MockOrkaATSAdapter(
            simulation=MockFailureSimulation(
                failures={AdapterCapability.RESOLVE_CURRENT_USER: AdapterErrorCode.UNAVAILABLE}
            )
        )

    application, dependencies = build_context_application(
        tmp_path / "adapter-unavailable.db",
        subject_reference="admin",
        adapter_factory=failing_adapter,
    )

    response = asyncio.run(
        _post(
            application,
            "/api/v1/action-proposals",
            _proposal_body(),
            request_id=PROPOSAL_REQUEST_ID,
        )
    )

    assert response.status_code == 503
    assert response.json()["code"] == "adapter_unavailable"
    assert "preview" not in response.text
    with dependencies.database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ActionProposalModel)) == 0
