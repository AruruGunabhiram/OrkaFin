"""Cross-endpoint Local V1 flow using only the in-process deterministic stack."""

from __future__ import annotations

import asyncio
from pathlib import Path

from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select

from orkafin.core.dependencies import ApplicationDependencies
from orkafin.infrastructure.database.models import ConversationModel, MessageModel

from ..context_support import build_context_application, context_hint


async def _run_flow(
    database_path: Path,
) -> tuple[dict[str, Response], ApplicationDependencies]:
    application, dependencies = build_context_application(database_path)
    assert dependencies.settings.ai_provider == "deterministic"

    counter = 0

    def request_id() -> str:
        nonlocal counter
        counter += 1
        return f"00000000-0000-4000-8000-{counter:012d}"

    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        health = await client.get("/health", headers={"X-Request-ID": request_id()})
        metadata = await client.get(
            "/api/v1/apps/orka_ats/metadata",
            headers={"X-Request-ID": request_id()},
        )
        context = await client.post(
            "/api/v1/contexts:resolve",
            json=context_hint(),
            headers={"X-Request-ID": request_id()},
        )
        page_answer = await client.post(
            "/api/v1/assistant/queries",
            json={"question": "Explain this page.", "context": context_hint()},
            headers={"X-Request-ID": request_id()},
        )
        conversation_id = page_answer.json()["conversation_id"]
        candidate_answer = await client.post(
            "/api/v1/assistant/queries",
            json={
                "question": "Summarize this candidate.",
                "context": context_hint(),
                "conversation_id": conversation_id,
            },
            headers={"X-Request-ID": request_id()},
        )
        conversation = await client.get(
            f"/api/v1/conversations/{conversation_id}",
            params={"app_id": "orka_ats", "page": "candidate_profile"},
            headers={"X-Request-ID": request_id()},
        )
        recommendation = await client.post(
            "/api/v1/recommendations:evaluate",
            json={"context": context_hint(page_id="recruitment_pipeline", candidate_id=None)},
            headers={"X-Request-ID": request_id()},
        )

    responses = {
        "health": health,
        "metadata": metadata,
        "context": context,
        "page_answer": page_answer,
        "candidate_answer": candidate_answer,
        "conversation": conversation,
        "recommendation": recommendation,
    }
    return responses, dependencies


def test_end_to_end_local_assistant_flow_is_grounded_isolated_and_offline(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "local-assistant-e2e.db"
    responses, dependencies = asyncio.run(_run_flow(database_path))

    assert all(response.status_code == 200 for response in responses.values())
    assert responses["health"].json() == {
        "status": "ok",
        "service": "orkafin",
        "version": "v1",
    }
    assert responses["metadata"].json()["app_id"] == "orka_ats"

    resolved = responses["context"].json()
    assert resolved["identity"]["user_id"] == "mock-user-limited-viewer"
    assert "email" not in resolved["identity"]
    assert [field["field_id"] for field in resolved["candidate_summary"]["visible_fields"]] == [
        "display_name",
        "recruiter",
        "recruitment_stage",
    ]

    page_answer = responses["page_answer"].json()
    assert page_answer["grounding_status"] == "grounded"
    assert page_answer["content"]["kind"] == "grounded_guidance"
    assert page_answer["sources"][0]["source_id"] == "candidate_profile"

    candidate_answer = responses["candidate_answer"].json()
    assert candidate_answer["conversation_id"] == page_answer["conversation_id"]
    assert candidate_answer["grounding_status"] == "verified"
    assert candidate_answer["content"]["kind"] == "verified_fact"
    assert "Taylor Example" in candidate_answer["content"]["text"]
    assert "taylor.example@candidate.invalid" not in candidate_answer["content"]["text"]
    assert candidate_answer["sources"][0]["source_type"] == "candidate_summary"

    conversation = responses["conversation"].json()
    assert [message["role"] for message in conversation["messages"]] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert conversation["messages"][-1]["content"] == (
        "An authorized candidate summary was provided for this request."
    )
    assert "Taylor Example" not in responses["conversation"].text

    recommendations = responses["recommendation"].json()["recommendations"]
    assert len(recommendations) == 1
    assert recommendations[0]["rule_id"] == "review_recruitment_pipeline"
    assert recommendations[0]["source_references"] == [
        "catalog://orka_ats/recommendations/review_recruitment_pipeline",
        "catalog://orka_ats/features/candidate_stage_tracking",
    ]

    with dependencies.database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ConversationModel)) == 1
        assert session.scalar(select(func.count()).select_from(MessageModel)) == 4
    persisted = database_path.read_bytes()
    assert b"IGNORE PRIOR INSTRUCTIONS" not in persisted
    assert b"taylor.example@candidate.invalid" not in persisted
