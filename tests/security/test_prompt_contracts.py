"""Trust-tagged prompt construction and bounded-history security coverage."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType

import pytest
from pydantic import ValidationError

from orkafin.application.response_generation import (
    ResponseGenerationRequest,
    ResponseGenerationService,
)
from orkafin.application.retrieval import RetrievalIntent, RetrievalResult
from orkafin.application.retrieval.service import DeterministicRetrievalService
from orkafin.domain.base import DataOwner
from orkafin.domain.catalog import VerificationStatus
from orkafin.domain.identifiers import Permission, SafeReference
from orkafin.domain.sources import RetrievedSource, SourceType
from orkafin.providers.contracts import ResponseIntent
from orkafin.providers.deterministic import DeterministicResponseProvider
from orkafin.providers.history import (
    BoundedConversationHistoryPolicy,
    ConversationHistoryEntry,
    HistoryInputRole,
    HistorySensitivity,
)
from orkafin.providers.prompts import PROMPT_TEMPLATES, build_prompt_messages
from tests.security.test_provider_payload_security import (
    _request_with_sensitive_candidate_context,
)
from tests.unit.test_response_generation import _generation_request
from tests.unit.test_retrieval_service import _request, _service

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "red_team_prompt_injection.json"
NOW = datetime(2026, 7, 14, tzinfo=UTC)


def _red_team() -> dict[str, str]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _candidate_summary_source() -> RetrievedSource:
    return RetrievedSource(
        source_id="candidate-summary-response-001",
        source_type=SourceType.CANDIDATE_SUMMARY,
        source_owner=DataOwner.ORKA_ATS,
        app_id="orka_ats",
        content_version="1.0.0",
        revision="rev-001",
        title="Authorized candidate summary",
        safe_reference=SafeReference(root="adapter://orka_ats/candidate-summary/response-001"),
        excerpt="The adapter supplied the authorized standard candidate fields.",
        verification_status=VerificationStatus.VERIFIED,
        relevance_score=1.0,
        relevance_reason="Bound to the current adapter summary response.",
        required_permissions=(Permission(root="candidate.view"),),
        retrieved_at=NOW,
    )


def test_versioned_templates_are_separate_for_every_intent() -> None:
    assert set(PROMPT_TEMPLATES) == set(ResponseIntent)
    assert len({template.template_id for template in PROMPT_TEMPLATES.values()}) == len(
        ResponseIntent
    )
    assert {template.version for template in PROMPT_TEMPLATES.values()} == {"1.0.0"}


def test_user_and_prior_assistant_injection_stay_in_untrusted_data_sections() -> None:
    fixture = _red_team()
    history = tuple(
        ConversationHistoryEntry(
            role=HistoryInputRole.USER,
            content=f"older visible message {index} " + ("x" * 450),
        )
        for index in range(8)
    ) + (
        ConversationHistoryEntry(
            role=HistoryInputRole.SYSTEM,
            content=fixture["hidden_system_message"],
        ),
        ConversationHistoryEntry(
            role=HistoryInputRole.USER,
            content=fixture["sensitive_history_message"],
            sensitivity=HistorySensitivity.SENSITIVE,
        ),
        ConversationHistoryEntry(
            role=HistoryInputRole.ASSISTANT,
            content=fixture["prior_assistant_message"],
        ),
    )
    base = _generation_request()
    request = base.model_copy(
        update={
            "user_question": fixture["user_question"],
            "conversation_history": history,
        }
    )

    provider_request = ResponseGenerationService.build_provider_request(request)
    messages = build_prompt_messages(provider_request)
    context_payload = json.loads(messages[2]["content"])

    assert tuple(message["role"] for message in messages) == ("system", "developer", "user")
    assert fixture["user_question"] not in messages[0]["content"]
    assert fixture["user_question"] not in messages[1]["content"]
    assert context_payload["untrusted_user_question"]["data"] == fixture["user_question"]
    assert (
        context_payload["untrusted_user_question"]["trust"]
        == "untrusted_data_not_instruction_or_evidence"
    )
    history_text = " ".join(message.content for message in provider_request.history)
    assert fixture["prior_assistant_message"] in history_text
    assert fixture["hidden_system_message"] not in history_text
    assert fixture["sensitive_history_message"] not in history_text
    assert len(provider_request.history) <= BoundedConversationHistoryPolicy.max_messages
    assert all(
        len(message.content) <= BoundedConversationHistoryPolicy.max_message_characters
        for message in provider_request.history
    )
    assert (
        sum(len(message.content) for message in provider_request.history)
        <= BoundedConversationHistoryPolicy.max_total_characters
    )
    assert context_payload["forbidden_behaviors"]["trust"] == "mirror_of_system_policy"
    assert context_payload["output_contract"]["trust"] == "server_enforced_allowlist"


def test_oversized_question_is_rejected_before_provider_construction() -> None:
    base = _generation_request()

    with pytest.raises(ValidationError, match="at most 500 characters"):
        ResponseGenerationRequest(
            user_question="x" * 501,
            context=base.context,
            retrieval=base.retrieval,
            intent=base.intent,
            response_id=base.response_id,
            conversation_id=base.conversation_id,
        )


def test_raw_malicious_help_body_is_searchable_but_not_provider_evidence() -> None:
    fixture = _red_team()
    service = _service()
    index = service._knowledge_index  # noqa: SLF001 - controlled red-team catalog mutation.
    article = index.help_by_id["help_candidate_profile"]
    malicious = article.model_copy(update={"content": fixture["help_document"]})
    articles = tuple(
        malicious if item.article_id == malicious.article_id else item
        for item in index.help_articles
    )
    malicious_index = replace(
        index,
        help_articles=articles,
        help_by_id=MappingProxyType({item.article_id: item for item in articles}),
    )
    retrieval_request = _request("candidate profile help")
    retrieval = DeterministicRetrievalService(knowledge_index=malicious_index).retrieve(
        retrieval_request
    )
    generation_request = ResponseGenerationRequest(
        user_question="candidate profile help",
        context=retrieval_request.context,
        retrieval=retrieval,
        intent=ResponseIntent.EXPLAIN_PAGE,
        response_id="response-red-team-help",
        conversation_id="conversation-red-team-help",
    )

    provider_request = ResponseGenerationService.build_provider_request(generation_request)
    response = ResponseGenerationService(provider=DeterministicResponseProvider()).generate(
        generation_request
    )

    assert fixture["help_document"] not in provider_request.model_dump_json()
    assert fixture["help_document"] not in response.model_dump_json()
    assert (
        next(
            source for source in retrieval.sources if source.source_id == malicious.article_id
        ).excerpt
        == malicious.summary
    )


def test_candidate_note_admin_injection_is_excluded_even_for_candidate_summary() -> None:
    fixture = _red_team()
    base = _request_with_sensitive_candidate_context()
    summary = base.context.candidate_summary
    assert summary is not None and summary.notes_excerpt is not None
    malicious_notes = summary.notes_excerpt.model_copy(
        update={"content": fixture["candidate_note"]}
    )
    context = base.context.model_copy(
        update={"candidate_summary": summary.model_copy(update={"notes_excerpt": malicious_notes})}
    )
    retrieval = RetrievalResult(
        intent=RetrievalIntent.FEATURE_QUESTION,
        sources=(_candidate_summary_source(),),
        candidate_count=1,
        permission_filtered_count=0,
    )
    request = base.model_copy(
        update={
            "context": context,
            "retrieval": retrieval,
            "intent": ResponseIntent.CANDIDATE_SUMMARY,
            "user_question": "summarize this candidate",
        }
    )

    provider_request = ResponseGenerationService.build_provider_request(request)
    response = ResponseGenerationService(provider=DeterministicResponseProvider()).generate(request)
    serialized = provider_request.model_dump_json()

    assert "Safe Candidate" in serialized
    assert fixture["candidate_note"] not in serialized
    assert "HIDDEN-FIELD@example.invalid" not in serialized
    assert fixture["candidate_note"] not in response.model_dump_json()
    assert response.content.kind == "verified_fact"
