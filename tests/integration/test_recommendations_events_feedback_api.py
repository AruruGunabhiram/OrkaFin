"""Prompt 17 end-to-end coverage for deterministic recommendation workflows."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select

from orkafin.domain.identifiers import Permission
from orkafin.infrastructure.database.models import RecommendationFeedbackModel, UserEventModel
from orkafin.knowledge import load_knowledge

from ..context_support import build_context_application, context_hint

REQUEST_ID = "00000000-0000-4000-8000-000000000845"


async def _request(
    application: FastAPI, method: str, path: str, *, json: dict[str, object]
) -> Response:
    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        return await client.request(method, path, json=json, headers={"X-Request-ID": REQUEST_ID})


def _evaluation_body(*, page_id: str = "recruitment_pipeline") -> dict[str, object]:
    return {"context": context_hint(page_id=page_id, candidate_id=None)}


def _evaluate(application: FastAPI, *, page_id: str = "recruitment_pipeline") -> Response:
    return asyncio.run(
        _request(
            application,
            "POST",
            "/api/v1/recommendations:evaluate",
            json=_evaluation_body(page_id=page_id),
        )
    )


def test_rule_match_is_deterministic_source_backed_and_frequency_limited(tmp_path: Path) -> None:
    first_app, _ = build_context_application(tmp_path / "first.db")
    second_app, _ = build_context_application(tmp_path / "second.db")

    first = _evaluate(first_app)
    second = _evaluate(second_app)
    repeated = _evaluate(first_app)

    assert first.status_code == second.status_code == repeated.status_code == 200
    first_recommendation = first.json()["recommendations"][0]
    second_recommendation = second.json()["recommendations"][0]
    assert (
        first_recommendation["rule_id"]
        == second_recommendation["rule_id"]
        == "review_recruitment_pipeline"
    )
    assert (
        first_recommendation["feature_id"]
        == second_recommendation["feature_id"]
        == "candidate_stage_tracking"
    )
    assert first_recommendation["source_references"] == [
        "catalog://orka_ats/recommendations/review_recruitment_pipeline",
        "catalog://orka_ats/features/candidate_stage_tracking",
    ]
    assert repeated.json()["recommendations"] == []
    assert repeated.json()["suppressed_rule_ids"] == ["review_recruitment_pipeline"]


def test_rule_does_not_recommend_on_an_unmatched_page(tmp_path: Path) -> None:
    application, _ = build_context_application(tmp_path / "page-filter.db")

    response = _evaluate(application, page_id="candidate_profile")

    assert response.status_code == 200
    assert response.json()["recommendations"] == []


def test_permission_filtering_excludes_an_otherwise_matching_rule(tmp_path: Path) -> None:
    index = load_knowledge("knowledge/orka_ats")
    original_rule = index.recommendations[0]
    restricted_rule = original_rule.model_copy(
        update={"required_permissions": (Permission(root="candidate.create"),)}
    )
    restricted_index = replace(
        index,
        recommendations=(restricted_rule,),
        recommendations_by_id=MappingProxyType({restricted_rule.rule_id: restricted_rule}),
    )
    application, _ = build_context_application(
        tmp_path / "permission-filter.db", knowledge_index=restricted_index
    )

    response = _evaluate(application)

    assert response.status_code == 200
    assert response.json()["recommendations"] == []


def test_feedback_lifecycle_records_all_types_and_dismissal_suppresses(tmp_path: Path) -> None:
    application, dependencies = build_context_application(tmp_path / "feedback.db")
    recommendation = _evaluate(application).json()["recommendations"][0]
    context = _evaluation_body()["context"]
    recommendation_id = recommendation["recommendation_id"]

    for feedback_type in ("helpful", "not_helpful", "dismissed"):
        response = asyncio.run(
            _request(
                application,
                "POST",
                "/api/v1/feedback",
                json={
                    "recommendation_id": recommendation_id,
                    "feedback_type": feedback_type,
                    "context": context,
                },
            )
        )
        assert response.status_code == 200
    assert _evaluate(application).json()["recommendations"] == []

    with dependencies.database.session_factory() as session:
        feedback_types = session.scalars(
            select(RecommendationFeedbackModel.feedback_type).order_by(
                RecommendationFeedbackModel.submitted_at
            )
        ).all()
    assert feedback_types == ["helpful", "not_helpful", "dismissed"]


def test_acceptance_and_disabled_preference_prevent_repetition(tmp_path: Path) -> None:
    accepted_app, _ = build_context_application(tmp_path / "accepted.db")
    accepted = _evaluate(accepted_app).json()["recommendations"][0]
    context = _evaluation_body()["context"]
    accepted_response = asyncio.run(
        _request(
            accepted_app,
            "POST",
            "/api/v1/feedback",
            json={
                "recommendation_id": accepted["recommendation_id"],
                "feedback_type": "accepted",
                "context": context,
            },
        )
    )
    assert accepted_response.status_code == 200
    assert _evaluate(accepted_app).json()["recommendations"] == []

    disabled_app, _ = build_context_application(tmp_path / "disabled.db")
    dismissed = _evaluate(disabled_app).json()["recommendations"][0]
    disabled_response = asyncio.run(
        _request(
            disabled_app,
            "POST",
            "/api/v1/feedback",
            json={
                "recommendation_id": dismissed["recommendation_id"],
                "feedback_type": "dismissed",
                "context": context,
                "preference": "disabled",
            },
        )
    )
    assert disabled_response.status_code == 200
    assert disabled_response.json()["preference"] == "disabled"
    assert _evaluate(disabled_app).json() == {
        "schema_version": "v1",
        "recommendations": [],
        "suppressed_rule_ids": [],
        "preference": "disabled",
    }


def test_event_allowlist_metadata_bounds_and_pii_exclusion(tmp_path: Path) -> None:
    application, dependencies = build_context_application(tmp_path / "events.db")
    context = _evaluation_body(page_id="candidate_profile")["context"]

    event = asyncio.run(
        _request(
            application,
            "POST",
            "/api/v1/events",
            json={
                "event_type": "page_viewed",
                "context": context,
                "metadata": {"origin": "widget"},
            },
        )
    )
    forbidden_event = asyncio.run(
        _request(
            application,
            "POST",
            "/api/v1/events",
            json={"event_type": "action_succeeded", "context": context, "metadata": {}},
        )
    )
    pii = asyncio.run(
        _request(
            application,
            "POST",
            "/api/v1/events",
            json={
                "event_type": "page_viewed",
                "context": context,
                "metadata": {"origin": "person@example.invalid"},
            },
        )
    )

    assert event.status_code == 200
    assert event.json()["actor_user_id"] == "mock-user-limited-viewer"
    assert forbidden_event.status_code == 400
    assert pii.status_code == 422
    with dependencies.database.session_factory() as session:
        rows = session.scalars(select(UserEventModel)).all()
    assert len(rows) == 1
    assert rows[0].metadata_json == {"origin": "widget"}
