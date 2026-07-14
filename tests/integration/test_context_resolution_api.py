"""Endpoint, safe-failure, and audit integration tests for resolved context."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response

from orkafin.adapters import AdapterCapability, AdapterErrorCode
from orkafin.adapters.orka_ats import MockFailureSimulation, MockOrkaATSAdapter
from orkafin.core.dependencies import ApplicationDependencies
from orkafin.infrastructure.database.repositories import OrkaFinRepository

from ..context_support import build_context_application, context_hint

REQUEST_ID = "00000000-0000-4000-8000-000000000812"


async def _post(application: FastAPI, body: dict[str, object]) -> Response:
    transport = ASGITransport(app=application, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post(
            "/api/v1/contexts:resolve",
            json=body,
            headers={"X-Request-ID": REQUEST_ID},
        )


def _audit_rows(dependencies: ApplicationDependencies) -> tuple[object, ...]:
    with dependencies.database.session_factory() as session:
        return tuple(OrkaFinRepository(session).list_audit_records())


def test_missing_identity_returns_safe_refusal_and_identity_denial_audit(
    tmp_path: Path,
) -> None:
    application, dependencies = build_context_application(
        tmp_path / "missing-identity.db", subject_reference=None
    )

    response = asyncio.run(_post(application, context_hint()))

    assert response.status_code == 401
    assert response.json() == {
        "schema_version": "v1",
        "code": "identity_unverified",
        "message": "Sign-in verification is required before this information can be shown.",
        "request_id": REQUEST_ID,
    }
    assert "candidate_summary" not in response.text
    rows = _audit_rows(dependencies)
    assert len(rows) == 1
    assert rows[0].event_type == "identity_denied"  # type: ignore[attr-defined]
    assert rows[0].actor_user_id is None  # type: ignore[attr-defined]
    assert rows[0].target_entity_id is None  # type: ignore[attr-defined]
    assert rows[0].details_json == {  # type: ignore[attr-defined]
        "decision_code": "identity_unverified"
    }


def test_missing_candidate_selection_returns_verified_context_without_entity_or_read_audit(
    tmp_path: Path,
) -> None:
    application, dependencies = build_context_application(tmp_path / "no-selection.db")

    response = asyncio.run(_post(application, context_hint(candidate_id=None)))

    assert response.status_code == 200
    body = response.json()
    assert body["selected_entity"] is None
    assert body["candidate_summary"] is None
    assert body["component_trust"]["selected_entity"] is None
    assert body["component_trust"]["candidate_summary"] is None
    assert _audit_rows(dependencies) == ()


@pytest.mark.parametrize(
    ("body", "database_name", "expected_code"),
    (
        (context_hint(app_id="unknown_app"), "unknown-app.db", "app_not_supported"),
        (context_hint(page_id="unknown_page"), "unknown-page.db", "page_not_supported"),
    ),
)
def test_unknown_app_or_page_returns_distinct_safe_client_error(
    tmp_path: Path,
    body: dict[str, object],
    database_name: str,
    expected_code: str,
) -> None:
    application, _ = build_context_application(tmp_path / database_name)

    response = asyncio.run(_post(application, body))

    assert response.status_code == 404
    error = response.json()
    assert error["code"] == expected_code
    assert error["request_id"] == REQUEST_ID
    assert "candidate_summary" not in response.text
    assert "unknown_app" not in response.text
    assert "unknown_page" not in response.text


@pytest.mark.parametrize("failure_code", (AdapterErrorCode.TIMEOUT, AdapterErrorCode.UNAVAILABLE))
def test_adapter_timeout_or_unavailable_returns_503_with_no_data(
    tmp_path: Path, failure_code: AdapterErrorCode
) -> None:
    def failing_adapter() -> MockOrkaATSAdapter:
        return MockOrkaATSAdapter(
            simulation=MockFailureSimulation(
                failures={
                    AdapterCapability.RESOLVE_CURRENT_USER: failure_code,
                }
            )
        )

    application, dependencies = build_context_application(
        tmp_path / f"adapter-{failure_code.value}.db",
        adapter_factory=failing_adapter,
    )

    response = asyncio.run(_post(application, context_hint()))

    assert response.status_code == 503
    assert response.json()["code"] == "adapter_unavailable"
    assert response.json()["message"].endswith("No application data was returned.")
    assert "candidate_summary" not in response.text
    assert _audit_rows(dependencies) == ()


def test_known_but_disallowed_page_returns_permission_denied_audit(tmp_path: Path) -> None:
    application, dependencies = build_context_application(tmp_path / "page-denied.db")

    response = asyncio.run(
        _post(application, context_hint(page_id="candidate_creation_form", candidate_id=None))
    )

    assert response.status_code == 403
    assert response.json()["code"] == "context_access_denied"
    rows = _audit_rows(dependencies)
    assert len(rows) == 1
    assert rows[0].event_type == "permission_denied"  # type: ignore[attr-defined]
    assert rows[0].target_entity_id is None  # type: ignore[attr-defined]
    assert rows[0].details_json == {  # type: ignore[attr-defined]
        "check": "page",
        "decision_code": "page_access_denied",
    }
