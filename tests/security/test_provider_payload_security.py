"""Security checks for minimized provider inputs and offline external-adapter tests."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime

from pydantic import SecretStr

from orkafin.application.response_generation import (
    ResponseGenerationRequest,
    ResponseGenerationService,
)
from orkafin.domain.candidate import (
    CandidateFieldSensitivity,
    CandidateNotesExcerpt,
    CandidateSummary,
    CandidateTextValue,
    CandidateVisibilitySummary,
    VisibleCandidateField,
)
from orkafin.domain.context import SelectedEntityRef
from orkafin.providers.contracts import ResponseIntent
from orkafin.providers.external import OpenAICompatibleResponseProvider
from tests.unit.test_retrieval_service import _context, _request, _service


class _OfflineTransport:
    def __init__(self) -> None:
        self.calls = 0

    def post_json(
        self, *, url: str, headers: Mapping[str, str], payload: Mapping[str, object], timeout: float
    ) -> Mapping[str, object]:
        self.calls += 1
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "kind": "grounded_guidance",
                                "text": "Candidate profile guidance.",
                                "cited_source_ids": ["candidate_profile"],
                                "template_id": "external_mock",
                            }
                        )
                    }
                }
            ]
        }


def _request_with_sensitive_candidate_context() -> ResponseGenerationRequest:
    now = datetime(2026, 7, 14, tzinfo=UTC)
    base = _context(page_id="candidate_profile", permissions=("candidate.view",))
    summary = CandidateSummary(
        candidate_id="CAND-1001",
        visible_fields=(
            VisibleCandidateField(
                field_id="display_name",
                label="Candidate name",
                sensitivity=CandidateFieldSensitivity.STANDARD,
                value=CandidateTextValue(value="Safe Candidate"),
            ),
            VisibleCandidateField(
                field_id="personal_email",
                label="Personal email",
                sensitivity=CandidateFieldSensitivity.RESTRICTED,
                value=CandidateTextValue(value="HIDDEN-FIELD@example.invalid"),
            ),
        ),
        visibility=CandidateVisibilitySummary(
            visible_field_count=2,
            redacted_field_count=3,
            redaction_applied=True,
            explanation_code="field_permissions_applied",
        ),
        notes_excerpt=CandidateNotesExcerpt(
            content="PRIVATE-CANDIDATE-NOTE",
            included_by_explicit_permission="candidate.notes.view",
        ),
        source_adapter_response_id="candidate-summary-response-001",
        valid_for_request_id=base.request_id,
        retrieved_at=now,
    )
    context_trust = base.component_trust.model_copy(
        update={
            "selected_entity": base.component_trust.app,
            "candidate_summary": base.component_trust.app.model_copy(
                update={"source_response_id": "candidate-summary-response-001"}
            ),
        }
    )
    context = base.model_copy(
        update={
            "component_trust": context_trust,
            "selected_entity": SelectedEntityRef(
                app_id="orka_ats", entity_type="candidate", entity_id="CAND-1001"
            ),
            "candidate_summary": summary,
        }
    )
    return ResponseGenerationRequest(
        user_question="explain this page",
        context=context,
        retrieval=_service().retrieve(_request("explain this page")),
        intent=ResponseIntent.EXPLAIN_PAGE,
        response_id="response-provider-002",
        conversation_id="conversation-002",
    )


def test_provider_payload_excludes_secrets_notes_hidden_fields_and_identity() -> None:
    provider_request = ResponseGenerationService.build_provider_request(
        _request_with_sensitive_candidate_context()
    )
    payload = provider_request.model_dump_json()

    assert "Safe Candidate" in payload
    assert "PRIVATE-CANDIDATE-NOTE" not in payload
    assert "HIDDEN-FIELD@example.invalid" not in payload
    assert "CAND-1001" not in payload
    assert "user-001" not in payload
    assert "candidate.view" not in payload


def test_external_adapter_uses_injected_transport_and_never_needs_live_network() -> None:
    transport = _OfflineTransport()
    provider = OpenAICompatibleResponseProvider(
        api_key=SecretStr("server-only-secret"),
        base_url="https://provider.example.invalid/v1/chat/completions",
        model="mock-model",
        timeout_seconds=1,
        transport=transport,
    )
    provider_request = ResponseGenerationService.build_provider_request(
        _request_with_sensitive_candidate_context()
    )
    payload = provider.build_payload(provider_request)
    payload_text = json.dumps(payload)

    assert "server-only-secret" not in payload_text
    assert "PRIVATE-CANDIDATE-NOTE" not in payload_text
    assert "HIDDEN-FIELD@example.invalid" not in payload_text
    assert transport.calls == 0

    draft = provider.generate(provider_request)

    assert transport.calls == 1
    assert draft.cited_source_ids == ("candidate_profile",)
