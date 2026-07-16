"""End-to-end tests for the trusted Local V1 assistant API."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select, text

from orkafin.adapters import AdapterCapability, AdapterErrorCode
from orkafin.adapters.orka_ats import MockFailureSimulation, MockOrkaATSAdapter
from orkafin.core.dependencies import ApplicationDependencies
from orkafin.infrastructure.database.models import ConversationModel
from orkafin.infrastructure.database.repositories import OrkaFinRepository

from ..context_support import build_context_application, context_hint

REQUEST_ID = "00000000-0000-4000-8000-000000000815"


async def _request(
    application: FastAPI,
    method: str,
    path: str,
    *,
    json: dict[str, object] | None = None,
) -> Response:
    transport = ASGITransport(app=application, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(
            method,
            path,
            json=json,
            headers={"X-Request-ID": REQUEST_ID},
        )


def _assistant_body(question: str, *, candidate_id: str | None = None) -> dict[str, object]:
    return {"question": question, "context": context_hint(candidate_id=candidate_id)}


def _messages(dependencies: ApplicationDependencies) -> tuple[object, ...]:
    with dependencies.database.session_factory() as session:
        repository = OrkaFinRepository(session)
        conversation = session.execute(select(ConversationModel)).scalars().one()
        return tuple(repository.list_messages(conversation.conversation_id))


def test_assistant_returns_grounded_page_response_with_sources_and_request_id(
    tmp_path: Path,
) -> None:
    application, dependencies = build_context_application(tmp_path / "grounded.db")

    response = asyncio.run(
        _request(
            application,
            "POST",
            "/api/v1/assistant/queries",
            json=_assistant_body("Explain this page."),
        )
    )

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == REQUEST_ID
    assert response.headers["X-Request-ID"] == REQUEST_ID
    assert body["grounding_status"] == "grounded"
    assert body["content"]["kind"] == "grounded_guidance"
    assert body["sources"][0]["source_id"] == "candidate_profile"
    messages = _messages(dependencies)
    assert [message.role.value for message in messages] == ["user", "assistant"]  # type: ignore[attr-defined]
    assert messages[1].source_ids == ("candidate_profile",)  # type: ignore[attr-defined]


def test_app_metadata_and_catalog_feature_endpoints_are_available(tmp_path: Path) -> None:
    application, _ = build_context_application(tmp_path / "apps.db")

    metadata = asyncio.run(_request(application, "GET", "/api/v1/apps/orka_ats/metadata"))
    features = asyncio.run(_request(application, "GET", "/api/v1/apps/orka_ats/features"))

    assert metadata.status_code == 200
    assert metadata.json()["app_id"] == "orka_ats"
    assert features.status_code == 200
    assert features.json()["app"]["app_id"] == "orka_ats"
    assert {feature["feature_id"] for feature in features.json()["features"]} == {
        "candidate_creation",
        "candidate_directory",
        "candidate_profile_review",
        "candidate_stage_tracking",
        "recruiter_filtering",
    }


def test_candidate_summary_is_redacted_grounded_and_not_persisted(tmp_path: Path) -> None:
    application, dependencies = build_context_application(tmp_path / "candidate.db")

    response = asyncio.run(
        _request(
            application,
            "POST",
            "/api/v1/assistant/queries",
            json=_assistant_body("Give me the candidate summary.", candidate_id="CAND-1042"),
        )
    )

    assert response.status_code == 200
    body = response.json()
    assert body["grounding_status"] == "verified"
    assert body["content"]["kind"] == "verified_fact"
    assert "Taylor Example" in body["content"]["text"]
    assert "candidate.invalid" not in body["content"]["text"]
    assert body["sources"][0]["source_type"] == "candidate_summary"
    messages = _messages(dependencies)
    assistant_message = next(
        message
        for message in messages
        if message.role.value == "assistant"  # type: ignore[attr-defined]
    )
    assert (
        assistant_message.content
        == "An authorized candidate summary was provided for this request."
    )  # type: ignore[attr-defined]
    assert "Taylor Example" not in assistant_message.content  # type: ignore[attr-defined]
    with dependencies.database.session_factory() as session:
        records = OrkaFinRepository(session).list_audit_records()
    assert [record.event_type for record in records] == ["candidate_read"]


def test_suggested_candidate_summary_phrase_requests_the_verified_summary(tmp_path: Path) -> None:
    application, _ = build_context_application(tmp_path / "suggested-candidate.db")

    response = asyncio.run(
        _request(
            application,
            "POST",
            "/api/v1/assistant/queries",
            json=_assistant_body("Summarize this candidate", candidate_id="CAND-1042"),
        )
    )

    assert response.status_code == 200
    assert response.json()["content"]["kind"] == "verified_fact"


def test_unknown_question_is_honestly_unavailable_and_persisted(tmp_path: Path) -> None:
    application, _ = build_context_application(tmp_path / "unknown.db")

    response = asyncio.run(
        _request(
            application,
            "POST",
            "/api/v1/assistant/queries",
            json=_assistant_body("What is quantum candidate matching?"),
        )
    )

    assert response.status_code == 200
    body = response.json()
    assert body["grounding_status"] == "unavailable"
    assert body["content"] == {
        "schema_version": "v1",
        "kind": "unavailable_information",
        "text": "Approved information is not available for this request.",
        "reason_code": "source_missing",
    }
    assert body["sources"] == []


def test_conversation_isolated_to_verified_owner(tmp_path: Path) -> None:
    database_path = tmp_path / "ownership.db"
    owner_app, _ = build_context_application(database_path, subject_reference="limited_viewer")
    owner_response = asyncio.run(
        _request(
            owner_app,
            "POST",
            "/api/v1/assistant/queries",
            json=_assistant_body("Explain this page."),
        )
    )
    conversation_id = owner_response.json()["conversation_id"]
    other_app, _ = build_context_application(database_path, subject_reference="recruiter")

    response = asyncio.run(
        _request(
            other_app,
            "GET",
            f"/api/v1/conversations/{conversation_id}?app_id=orka_ats&page=candidate_profile",
        )
    )

    assert response.status_code == 404
    assert response.json()["message"] == "The requested conversation is unavailable."


def test_adapter_failure_never_returns_a_fabricated_assistant_response(tmp_path: Path) -> None:
    def failing_adapter() -> MockOrkaATSAdapter:
        return MockOrkaATSAdapter(
            simulation=MockFailureSimulation(
                failures={AdapterCapability.RESOLVE_CURRENT_USER: AdapterErrorCode.UNAVAILABLE}
            )
        )

    application, dependencies = build_context_application(
        tmp_path / "adapter.db", adapter_factory=failing_adapter
    )
    response = asyncio.run(
        _request(
            application,
            "POST",
            "/api/v1/assistant/queries",
            json=_assistant_body("Explain this page."),
        )
    )

    assert response.status_code == 503
    assert response.json()["code"] == "adapter_unavailable"
    assert "conversation_id" not in response.text
    assert _messages_if_any(dependencies) == ()


def test_unverified_identity_and_candidate_denial_are_safe_and_audited(tmp_path: Path) -> None:
    unverified_app, unverified_dependencies = build_context_application(
        tmp_path / "unverified.db", subject_reference=None
    )
    unverified = asyncio.run(
        _request(
            unverified_app,
            "POST",
            "/api/v1/assistant/queries",
            json=_assistant_body("Explain this page."),
        )
    )
    denied_app, denied_dependencies = build_context_application(tmp_path / "denied.db")
    denied = asyncio.run(
        _request(
            denied_app,
            "POST",
            "/api/v1/assistant/queries",
            json=_assistant_body("Give me the candidate summary.", candidate_id="CAND-1099"),
        )
    )

    assert unverified.status_code == 401
    assert unverified.json()["code"] == "identity_unverified"
    assert denied.status_code == 403
    assert denied.json()["code"] == "candidate_access_denied"
    with unverified_dependencies.database.session_factory() as session:
        unverified_records = OrkaFinRepository(session).list_audit_records()
    with denied_dependencies.database.session_factory() as session:
        denied_records = OrkaFinRepository(session).list_audit_records()
    assert [record.event_type for record in unverified_records] == ["identity_denied"]
    assert [record.event_type for record in denied_records] == ["permission_denied"]


def test_assistant_requires_a_context_hint(tmp_path: Path) -> None:
    application, _ = build_context_application(tmp_path / "no-context.db")

    response = asyncio.run(
        _request(
            application,
            "POST",
            "/api/v1/assistant/queries",
            json={"question": "Explain this page."},
        )
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def _messages_if_any(dependencies: ApplicationDependencies) -> tuple[object, ...]:
    with dependencies.database.session_factory() as session:
        rows = session.execute(text("SELECT conversation_id FROM conversations")).all()
        if not rows:
            return ()
        return tuple(OrkaFinRepository(session).list_messages(rows[0][0]))
