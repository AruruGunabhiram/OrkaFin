"""Version-controlled product knowledge catalog contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from pydantic import Field

from orkafin.domain.base import (
    DataClassification,
    DataOwner,
    DomainModel,
    HandlingRule,
    LongText,
    LowercaseIdentifier,
    ModelDataPolicy,
    PersistencePolicy,
    Revision,
    SemanticVersion,
    SensitiveFieldPolicy,
    ShortText,
    UtcDatetime,
)
from orkafin.domain.context import Role
from orkafin.domain.identifiers import Permission, SafeReference


class CatalogStatus(StrEnum):
    """Lifecycle status for product knowledge."""

    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"


class VerificationStatus(StrEnum):
    """Human verification state for a catalog fact or instruction."""

    PROVISIONAL = "provisional"
    VERIFIED = "verified"
    NEEDS_REVIEW = "needs_review"


class CatalogProvenance(DomainModel):
    """Review, version, and safe-reference metadata shared by catalog items."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.PRODUCT_DOCUMENTATION,
        classification=DataClassification.INTERNAL,
        persistence=PersistencePolicy.CATALOG_FILE,
    )

    content_version: SemanticVersion
    revision: Revision
    status: CatalogStatus
    verification_status: VerificationStatus
    documentation_owner: ShortText
    last_reviewed_at: UtcDatetime
    safe_reference: SafeReference


class FeatureCatalogItem(DomainModel):
    """Approved or explicitly provisional description of one Orka feature."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.PRODUCT_DOCUMENTATION,
        classification=DataClassification.INTERNAL,
        persistence=PersistencePolicy.CATALOG_FILE,
    )
    model_config = {
        **DomainModel.model_config,
        "json_schema_extra": {
            "examples": [
                {
                    "schema_version": "v1",
                    "app_id": "orka_ats",
                    "feature_id": "candidate_pipeline",
                    "name": "Candidate pipeline",
                    "description": "Shows synthetic candidates by recruiting stage.",
                    "user_purpose": "Review recruiting workflow state.",
                    "aliases": ["pipeline"],
                    "supported_roles": [],
                    "required_permissions": ["candidate.view"],
                    "page_ids": ["recruitment_pipeline"],
                    "instruction_steps": [],
                    "related_feature_ids": [],
                    "related_app_ids": [],
                    "available_action_ids": [],
                    "provenance": {
                        "schema_version": "v1",
                        "content_version": "1.0.0",
                        "revision": "rev-001",
                        "status": "active",
                        "verification_status": "provisional",
                        "documentation_owner": "OrkaATS product owner",
                        "last_reviewed_at": "2026-07-13T20:00:00Z",
                        "safe_reference": "catalog://orka_ats/features/candidate_pipeline",
                    },
                }
            ]
        },
    }

    app_id: LowercaseIdentifier
    feature_id: LowercaseIdentifier
    name: ShortText
    description: ShortText
    user_purpose: ShortText
    aliases: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=25)
    supported_roles: tuple[Role, ...] = Field(default=(), max_length=25)
    required_permissions: tuple[Permission, ...] = Field(default=(), max_length=50)
    page_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=50)
    instruction_steps: tuple[ShortText, ...] = Field(default=(), max_length=25)
    related_feature_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=50)
    related_app_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=25)
    available_action_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=25)
    provenance: CatalogProvenance


class PageCatalogItem(DomainModel):
    """Approved or provisional metadata for one application page."""

    data_policy: ClassVar[ModelDataPolicy] = FeatureCatalogItem.data_policy

    app_id: LowercaseIdentifier
    page_id: LowercaseIdentifier
    title: ShortText
    purpose: ShortText
    route_hint: ShortText | None = None
    aliases: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=25)
    feature_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=50)
    required_permissions: tuple[Permission, ...] = Field(default=(), max_length=50)
    provenance: CatalogProvenance


class HelpArticle(DomainModel):
    """Bounded help content; approved text is still data, never system instruction."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.PRODUCT_DOCUMENTATION,
        classification=DataClassification.INTERNAL,
        persistence=PersistencePolicy.CATALOG_FILE,
        sensitive_fields=(
            SensitiveFieldPolicy(
                field_name="content",
                classification=DataClassification.INTERNAL,
                rules=(HandlingRule.MINIMIZE,),
            ),
        ),
    )

    app_id: LowercaseIdentifier
    article_id: LowercaseIdentifier
    title: ShortText
    summary: ShortText
    content: LongText
    content_trust_label: str = Field(
        default="controlled_content_not_instruction",
        pattern=r"^controlled_content_not_instruction$",
        strict=True,
    )
    aliases: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=25)
    tags: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=50)
    page_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=50)
    feature_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=50)
    required_permissions: tuple[Permission, ...] = Field(default=(), max_length=50)
    provenance: CatalogProvenance
