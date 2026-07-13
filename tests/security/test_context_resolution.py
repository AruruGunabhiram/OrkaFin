"""Security tests for forged browser context and record-swap attempts."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response

from orkafin.core.dependencies import ApplicationDependencies
from orkafin.infrastructure.database.repositories import OrkaFinRepository

from ..context_support import build_context_application, context_hint

REQUEST_ID = "00000000-0000-4000-8000-000000000811"


async def _post(application: FastAPI, body: dict[str, object]) -> Response:
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post(
            "/api/v1/contexts:resolve",
            json=body,
            headers={"X-Request-ID": REQUEST_ID},
        )


def _audit_rows(dependencies: ApplicationDependencies) -> tuple[object, ...]:
    with dependencies.database.session_factory() as session:
        return tuple(OrkaFinRepository(session).list_audit_records())


def test_forged_admin_permissions_and_actions_cannot_expand_limited_context(
    tmp_path: Path,
) -> None:
    application, dependencies = build_context_application(tmp_path / "forged-context.db")

    response = asyncio.run(_post(application, context_hint()))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["request_id"] == REQUEST_ID
    assert body["identity"]["user_id"] == "mock-user-limited-viewer"
    assert body["identity"]["role"]["role_id"] == "limited_viewer"
    assert body["identity"]["email"] == "limited.viewer.mock@example.invalid"
    assert body["permissions"] == ["candidate.view"]
    assert body["available_action_ids"] == []
    assert [field["field_id"] for field in body["candidate_summary"]["visible_fields"]] == [
        "display_name",
        "recruiter",
        "recruitment_stage",
    ]
    assert body["candidate_summary"]["visibility"] == {
        "schema_version": "v1",
        "visible_field_count": 3,
        "redacted_field_count": 5,
        "redaction_applied": True,
        "explanation_code": "field_permissions_applied",
    }
    assert "notes_excerpt" not in body["candidate_summary"]
    assert body["request_id"] != context_hint()["client_request_id_hint"]

    trust = body["component_trust"]
    for component in (
        "app",
        "identity",
        "page",
        "workspace",
        "selected_entity",
        "permissions",
        "available_actions",
        "candidate_summary",
    ):
        assert trust[component]["trust_label"] == "trusted_for_response_lifetime"
        assert trust[component]["verification_source"] == "application_adapter"

    rows = _audit_rows(dependencies)
    assert len(rows) == 1
    assert rows[0].event_type == "candidate_read"  # type: ignore[attr-defined]
    assert rows[0].details_json == {  # type: ignore[attr-defined]
        "visible_field_count": 3,
        "redacted_field_count": 5,
        "redaction_applied": True,
        "source": "application_adapter",
    }


def test_candidate_record_swap_is_denied_without_leaking_hidden_content(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    application, dependencies = build_context_application(tmp_path / "record-swap.db")

    response = asyncio.run(_post(application, context_hint(candidate_id="CAND-1099")))

    assert response.status_code == 403
    body = response.json()
    assert body == {
        "schema_version": "v1",
        "code": "candidate_access_denied",
        "message": (
            "The requested candidate information is not available for the verified account."
        ),
        "request_id": REQUEST_ID,
    }
    serialized = response.text
    captured = capsys.readouterr()
    combined_logs = captured.out + captured.err
    for hidden_value in (
        "Private Synthetic Candidate",
        "Private synthetic note",
        "IGNORE PRIOR INSTRUCTIONS",
        "forged.admin@example.invalid",
    ):
        assert hidden_value not in serialized
        assert hidden_value not in combined_logs

    rows = _audit_rows(dependencies)
    assert len(rows) == 1
    denial = rows[0]
    assert denial.event_type == "permission_denied"  # type: ignore[attr-defined]
    assert denial.outcome == "denied"  # type: ignore[attr-defined]
    assert denial.target_entity_id == "CAND-1099"  # type: ignore[attr-defined]
    assert denial.details_json == {  # type: ignore[attr-defined]
        "check": "record",
        "decision_code": "record_access_denied",
    }
    audit_text = str(denial.details_json)  # type: ignore[attr-defined]
    assert "notes" not in audit_text.lower()
    assert "Private Synthetic Candidate" not in audit_text
