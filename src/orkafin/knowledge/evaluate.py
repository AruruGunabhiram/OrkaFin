"""Run the version-controlled deterministic retrieval evaluation fixture set."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import yaml  # type: ignore[import-untyped]

from orkafin.application.retrieval import (
    DeterministicRetrievalService,
    RetrievalRequest,
    normalize_question,
)
from orkafin.domain.context import (
    AppMetadata,
    AppStatus,
    ContextComponentTrust,
    ContextVerificationSource,
    IdentityVerificationStatus,
    ResolvedContextTrust,
    ResolvedPageContext,
    ResolvedUserIdentity,
    Role,
    WorkspaceRef,
)
from orkafin.domain.identifiers import Permission, RequestId
from orkafin.knowledge import load_knowledge


def evaluate(
    *,
    knowledge_root: Path | None = None,
    fixture_path: Path | None = None,
) -> dict[str, object]:
    """Evaluate fixture top-source and intent expectations without network access."""
    repository_root = Path(__file__).resolve().parents[3]
    index = load_knowledge(knowledge_root or repository_root / "knowledge" / "orka_ats")
    cases = _load_cases(fixture_path or repository_root / "fixtures" / "retrieval_evaluation.yaml")
    service = DeterministicRetrievalService(
        knowledge_index=index,
        clock=lambda: datetime(2026, 7, 14, tzinfo=UTC),
    )
    failures: list[dict[str, object]] = []
    for case in cases:
        request = _request_from_case(case)
        result = service.retrieve(request)
        actual_source_ids = [source.source_id for source in result.sources]
        expected_source_ids = _strings(case, "expected_source_ids")
        expected_intent = _string(case, "expected_intent")
        expected_top = list(expected_source_ids[:1])
        actual_top = actual_source_ids[:1]
        if actual_top != expected_top or result.intent.value != expected_intent:
            failures.append(
                {
                    "id": _string(case, "id"),
                    "expected_intent": expected_intent,
                    "actual_intent": result.intent.value,
                    "expected_top_source_ids": expected_top,
                    "actual_top_source_ids": actual_top,
                    "no_source_reason": result.no_source_reason,
                }
            )
    total = len(cases)
    passed = total - len(failures)
    return {
        "total_cases": total,
        "passed_cases": passed,
        "failed_cases": len(failures),
        "top_source_accuracy": passed / total if total else 0.0,
        "failures": failures,
    }


def _load_cases(path: Path) -> tuple[Mapping[str, object], ...]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("cases"), list):
        raise ValueError("retrieval evaluation fixture must contain a cases list")
    cases = raw["cases"]
    assert isinstance(cases, list)
    parsed: list[Mapping[str, object]] = []
    for position, value in enumerate(cases, 1):
        if not isinstance(value, dict):
            raise ValueError(f"retrieval evaluation case {position} must be a mapping")
        for key in (
            "id",
            "question",
            "page_id",
            "permissions",
            "expected_source_ids",
            "expected_intent",
        ):
            if key not in value:
                raise ValueError(f"retrieval evaluation case {position} is missing {key}")
        parsed.append(value)
    return tuple(parsed)


def _request_from_case(case: Mapping[str, object]) -> RetrievalRequest:
    permissions = _strings(case, "permissions")
    return RetrievalRequest(
        normalized_question=normalize_question(_string(case, "question")),
        context=_context(page_id=_string(case, "page_id"), permissions=permissions),
        trusted_permissions=tuple(Permission(root=value) for value in permissions),
    )


def _context(*, page_id: str, permissions: Sequence[str]) -> ResolvedPageContext:
    now = datetime(2026, 7, 14, tzinfo=UTC)
    response_id = "evaluation-context-response"
    component = ContextComponentTrust(
        verification_source=ContextVerificationSource.LOCAL_FIXTURE,
        source_response_id=response_id,
    )
    return ResolvedPageContext(
        verification_source=ContextVerificationSource.LOCAL_FIXTURE,
        adapter_response_id=response_id,
        component_trust=ResolvedContextTrust(
            app=component,
            identity=component,
            page=component,
            workspace=component,
            permissions=component,
            available_actions=component,
        ),
        request_id=RequestId(root=str(uuid4())),
        app=AppMetadata(
            app_id="orka_ats",
            display_name="OrkaATS",
            description="Synthetic evaluation application.",
            app_version="1.0.0",
            adapter_contract_version="1.0.0",
            status=AppStatus.ACTIVE,
        ),
        page_id=page_id,
        identity=ResolvedUserIdentity(
            user_id="evaluation-user",
            role=Role(role_id="recruiter", display_name="Recruiter", owner_app_id="orka_ats"),
            verification_status=IdentityVerificationStatus.LOCAL_FIXTURE_VERIFIED,
            verified_at=now,
            verification_reference="evaluation-identity-response",
        ),
        workspace=WorkspaceRef(workspace_id="evaluation-workspace", app_id="orka_ats"),
        permissions=tuple(Permission(root=value) for value in permissions),
        resolved_at=now,
        valid_until=now,
    )


def _string(case: Mapping[str, object], key: str) -> str:
    value = case[key]
    if not isinstance(value, str):
        raise ValueError(f"retrieval evaluation {key} must be a string")
    return value


def _strings(case: Mapping[str, object], key: str) -> tuple[str, ...]:
    value = case[key]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"retrieval evaluation {key} must be a string list")
    return tuple(value)


def main() -> int:
    """Print stable JSON metrics and fail when a fixture expectation is not met."""
    metrics = evaluate()
    print(json.dumps(metrics, sort_keys=True))
    return 0 if metrics["failed_cases"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
