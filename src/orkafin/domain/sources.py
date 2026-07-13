"""Grounding source references with provenance and safe internal locations."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, ClassVar

from pydantic import Field, StringConstraints, model_validator

from orkafin.domain.base import (
    DataClassification,
    DataOwner,
    DomainModel,
    HandlingRule,
    Identifier,
    LowercaseIdentifier,
    ModelDataPolicy,
    PersistencePolicy,
    Revision,
    SemanticVersion,
    SensitiveFieldPolicy,
    ShortText,
    UtcDatetime,
)
from orkafin.domain.catalog import VerificationStatus
from orkafin.domain.identifiers import Permission, SafeReference

SourceExcerpt = Annotated[
    str,
    StringConstraints(min_length=1, max_length=2_000, strip_whitespace=True, strict=True),
]


class SourceType(StrEnum):
    """Supported origin categories for grounded claims."""

    APP_METADATA = "app_metadata"
    PAGE_CATALOG = "page_catalog"
    FEATURE_CATALOG = "feature_catalog"
    HELP_ARTICLE = "help_article"
    CANDIDATE_SUMMARY = "candidate_summary"
    ACTION_DEFINITION = "action_definition"


class RetrievedSource(DomainModel):
    """Permission-filtered source returned by deterministic retrieval or an adapter."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.SOURCE_DECLARED,
        classification=DataClassification.RESTRICTED,
        persistence=PersistencePolicy.ORKAFIN_ALLOWED,
        sensitive_fields=(
            SensitiveFieldPolicy(
                field_name="excerpt",
                classification=DataClassification.RESTRICTED,
                rules=(HandlingRule.MINIMIZE, HandlingRule.REDACT_FROM_LOGS),
            ),
        ),
    )
    model_config = {
        **DomainModel.model_config,
        "json_schema_extra": {
            "examples": [
                {
                    "schema_version": "v1",
                    "source_id": "help_candidate_pipeline",
                    "source_type": "help_article",
                    "source_owner": "product_documentation",
                    "app_id": "orka_ats",
                    "content_version": "1.0.0",
                    "revision": "rev-001",
                    "title": "Candidate pipeline overview",
                    "safe_reference": "knowledge://orka_ats/help/candidate_pipeline",
                    "excerpt": "The pipeline groups synthetic records by recruiting stage.",
                    "verification_status": "verified",
                    "relevance_score": 1.0,
                    "relevance_reason": "Exact page match",
                    "required_permissions": ["candidate.view"],
                    "retrieved_at": "2026-07-13T20:00:00Z",
                }
            ]
        },
    }

    source_id: Identifier
    source_type: SourceType
    source_owner: DataOwner
    app_id: LowercaseIdentifier
    content_version: SemanticVersion
    revision: Revision
    title: ShortText
    safe_reference: SafeReference
    excerpt: SourceExcerpt
    verification_status: VerificationStatus
    relevance_score: float = Field(ge=0.0, le=1.0)
    relevance_reason: ShortText
    required_permissions: tuple[Permission, ...] = Field(default=(), max_length=50)
    retrieved_at: UtcDatetime

    @model_validator(mode="after")
    def require_correct_source_owner(self) -> RetrievedSource:
        if self.source_type is SourceType.CANDIDATE_SUMMARY:
            if self.source_owner not in {DataOwner.ORKA_ATS, DataOwner.OWNING_APPLICATION}:
                raise ValueError("candidate summary sources must be owned by an application")
        elif (
            self.source_type
            in {
                SourceType.PAGE_CATALOG,
                SourceType.FEATURE_CATALOG,
                SourceType.HELP_ARTICLE,
                SourceType.ACTION_DEFINITION,
            }
            and self.source_owner is not DataOwner.PRODUCT_DOCUMENTATION
        ):
            raise ValueError("catalog and help sources must be owned by product documentation")
        return self
