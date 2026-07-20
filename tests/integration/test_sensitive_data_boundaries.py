"""Cross-boundary checks for sensitive text in questions, feedback, events, and audits."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select

from orkafin.infrastructure.database.models import (
    AuditRecordModel,
    MessageModel,
    RecommendationFeedbackModel,
    UserEventModel,
)
from orkafin.providers.contracts import ProviderDraft, ProviderRequest
from orkafin.providers.deterministic import DeterministicResponseProvider

from ..context_support import build_context_application, context_hint

REQUEST_ID = "00000000-0000-4000-8000-000000002001"


class RecordingDeterministicProvider:
    """Capture the exact minimized provider contract without using a network."""

    def __init__(self) -> None:
        self.requests: list[ProviderRequest] = []
        self._delegate = DeterministicResponseProvider()

    def generate(self, request: ProviderRequest) -> ProviderDraft:
        self.requests.append(request)
        return self._delegate.generate(request)


async def _request(
    application: FastAPI,
    method: str,
    path: str,
    *,
    body: dict[str, object] | None = None,
) -> Response:
    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        return await client.request(
            method,
            path,
            json=body,
            headers={"X-Request-ID": REQUEST_ID},
        )


def test_sensitive_markers_do_not_cross_provider_persistence_event_audit_or_response_boundaries(
    tmp_path: Path,
) -> None:
    email = "boundary.marker" + "@" + "example.invalid"
    token = "sk-" + "S" * 24
    database_path = tmp_path / "sensitive-boundaries.db"
    provider = RecordingDeterministicProvider()
    application, dependencies = build_context_application(
        database_path,
        response_provider=provider,
    )
    assistant = asyncio.run(
        _request(
            application,
            "POST",
            "/api/v1/assistant/queries",
            body={
                "question": (f"Summarize this candidate for {email}; api_key={token}."),
                "context": context_hint(),
            },
        )
    )

    assert assistant.status_code == 200, assistant.text
    assert email not in assistant.text
    assert token not in assistant.text
    assert len(provider.requests) == 1
    provider_payload = provider.requests[0].model_dump_json()
    assert email not in provider_payload
    assert token not in provider_payload
    assert "[REDACTED]" in provider.requests[0].user_question

    conversation_id = assistant.json()["conversation_id"]
    conversation = asyncio.run(
        _request(
            application,
            "GET",
            f"/api/v1/conversations/{conversation_id}?app_id=orka_ats&page=candidate_profile",
        )
    )
    assert conversation.status_code == 200
    assert email not in conversation.text
    assert token not in conversation.text
    assert "[REDACTED]" in conversation.text

    rejected_event = asyncio.run(
        _request(
            application,
            "POST",
            "/api/v1/events",
            body={
                "event_type": "page_viewed",
                "context": context_hint(candidate_id=None),
                "metadata": {"origin": f"token={token}"},
            },
        )
    )
    assert rejected_event.status_code == 422
    assert email not in rejected_event.text
    assert token not in rejected_event.text

    recommendation = asyncio.run(
        _request(
            application,
            "POST",
            "/api/v1/recommendations:evaluate",
            body={"context": context_hint(page_id="recruitment_pipeline", candidate_id=None)},
        )
    ).json()["recommendations"][0]
    feedback = asyncio.run(
        _request(
            application,
            "POST",
            "/api/v1/feedback",
            body={
                "recommendation_id": recommendation["recommendation_id"],
                "feedback_type": "helpful",
                "context": context_hint(page_id="recruitment_pipeline", candidate_id=None),
                "comment": f"Contact {email}; token={token}",
            },
        )
    )
    assert feedback.status_code == 200
    assert email not in feedback.text
    assert token not in feedback.text

    with dependencies.database.session_factory() as session:
        messages = tuple(session.scalars(select(MessageModel.content)))
        comments = tuple(session.scalars(select(RecommendationFeedbackModel.comment)))
        event_metadata = tuple(session.scalars(select(UserEventModel.metadata_json)))
        audit_details = tuple(session.scalars(select(AuditRecordModel.details_json)))
    serialized_rows = repr((messages, comments, event_metadata, audit_details))
    assert email not in serialized_rows
    assert token not in serialized_rows
    assert "[REDACTED]" in serialized_rows
    assert "IGNORE PRIOR INSTRUCTIONS" not in serialized_rows
    assert "taylor.example@candidate.invalid" not in serialized_rows

    database_bytes = database_path.read_bytes()
    assert email.encode() not in database_bytes
    assert token.encode() not in database_bytes
