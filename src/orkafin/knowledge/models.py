"""Typed file-level contracts for version-controlled product knowledge."""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field, field_validator, model_validator

from orkafin.domain.actions import ActionDefinition
from orkafin.domain.base import (
    DataClassification,
    DataOwner,
    DomainModel,
    LowercaseIdentifier,
    ModelDataPolicy,
    PersistencePolicy,
    ShortText,
)
from orkafin.domain.catalog import (
    CatalogProvenance,
    CatalogStatus,
    FeatureCatalogItem,
    PageCatalogItem,
)
from orkafin.domain.context import AppMetadata, Role
from orkafin.domain.identifiers import Permission
from orkafin.domain.recommendations import RecommendationKind


class CatalogManifest(DomainModel):
    """Manifest that pins every source file used by one application catalog."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.PRODUCT_DOCUMENTATION,
        classification=DataClassification.INTERNAL,
        persistence=PersistencePolicy.CATALOG_FILE,
    )

    app_id: LowercaseIdentifier
    catalog_files: tuple[ShortText, ...] = Field(min_length=1, max_length=20)
    help_files: tuple[ShortText, ...] = Field(min_length=1, max_length=100)
    provenance: CatalogProvenance

    @field_validator("catalog_files", "help_files")
    @classmethod
    def require_safe_relative_paths(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        for value in values:
            if value.startswith("/") or "\\" in value or ".." in value.split("/"):
                raise ValueError("catalog source files must use safe relative paths")
        if len(values) != len(set(values)):
            raise ValueError("catalog source files must be unique")
        return values


class AppCatalogItem(DomainModel):
    """Catalog provenance and relationship metadata around Prompt 4 app metadata."""

    data_policy: ClassVar[ModelDataPolicy] = CatalogManifest.data_policy

    metadata: AppMetadata
    aliases: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=25)
    purpose: ShortText
    supported_roles: tuple[Role, ...] = Field(default=(), max_length=25)
    required_permissions: tuple[Permission, ...] = Field(default=(), max_length=50)
    page_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=50)
    feature_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=50)
    related_app_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=25)
    provenance: CatalogProvenance


class PermissionCatalogItem(DomainModel):
    """Controlled declaration of a permission name usable by this catalog."""

    data_policy: ClassVar[ModelDataPolicy] = CatalogManifest.data_policy

    permission: Permission
    title: ShortText
    purpose: ShortText
    aliases: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=25)
    supported_roles: tuple[Role, ...] = Field(default=(), max_length=25)
    page_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=50)
    feature_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=50)
    action_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=25)
    provenance: CatalogProvenance


class RecommendationCatalogItem(DomainModel):
    """Rule metadata only; no recommendation is generated while loading it."""

    data_policy: ClassVar[ModelDataPolicy] = CatalogManifest.data_policy

    rule_id: LowercaseIdentifier
    title: ShortText
    description: ShortText
    purpose: ShortText
    kind: RecommendationKind
    aliases: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=25)
    supported_roles: tuple[Role, ...] = Field(default=(), max_length=25)
    required_permissions: tuple[Permission, ...] = Field(default=(), max_length=50)
    page_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=50)
    feature_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=50)
    action_id: LowercaseIdentifier | None = None
    related_rule_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=50)
    provenance: CatalogProvenance


class ActionCatalogItem(DomainModel):
    """Catalog provenance and discovery metadata around an action definition."""

    data_policy: ClassVar[ModelDataPolicy] = CatalogManifest.data_policy

    action: ActionDefinition
    aliases: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=25)
    purpose: ShortText
    supported_roles: tuple[Role, ...] = Field(default=(), max_length=25)
    page_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=50)
    feature_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=50)
    related_action_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=25)
    provenance: CatalogProvenance

    @model_validator(mode="after")
    def require_matching_lifecycle_metadata(self) -> ActionCatalogItem:
        if self.action.action_version != self.provenance.content_version:
            raise ValueError("action version must match catalog provenance content version")
        if self.action.revision != self.provenance.revision:
            raise ValueError("action revision must match catalog provenance revision")
        if self.action.status is not self.provenance.status:
            raise ValueError("action status must match catalog provenance status")
        if self.action.safe_reference != self.provenance.safe_reference:
            raise ValueError("action source reference must match catalog provenance")
        return self


CatalogItem = (
    AppCatalogItem
    | PermissionCatalogItem
    | PageCatalogItem
    | FeatureCatalogItem
    | RecommendationCatalogItem
    | ActionCatalogItem
)


def catalog_status(item: CatalogItem) -> CatalogStatus:
    """Return one item's lifecycle status without exposing storage details."""
    return item.provenance.status
