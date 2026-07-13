"""Deterministic loader and cross-file validator for controlled knowledge."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Protocol, TypeVar, runtime_checkable

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ValidationError

from orkafin.domain.catalog import (
    CatalogProvenance,
    CatalogStatus,
    FeatureCatalogItem,
    HelpArticle,
    PageCatalogItem,
)
from orkafin.knowledge.models import (
    ActionCatalogItem,
    AppCatalogItem,
    CatalogManifest,
    PermissionCatalogItem,
    RecommendationCatalogItem,
)

_T = TypeVar("_T", bound=BaseModel)
_CATALOG_FILES = frozenset(
    {
        "app.yaml",
        "pages.yaml",
        "features.yaml",
        "permissions.yaml",
        "recommendations.yaml",
        "actions.yaml",
    }
)


class KnowledgeValidationError(ValueError):
    """A safe error describing invalid controlled catalog content."""


@runtime_checkable
class _Provenanced(Protocol):
    provenance: CatalogProvenance


@dataclass(frozen=True, slots=True)
class KnowledgeIndex:
    """Immutable, deterministically ordered knowledge for one application."""

    root: Path
    manifest: CatalogManifest
    app: AppCatalogItem
    permissions: tuple[PermissionCatalogItem, ...]
    pages: tuple[PageCatalogItem, ...]
    features: tuple[FeatureCatalogItem, ...]
    help_articles: tuple[HelpArticle, ...]
    recommendations: tuple[RecommendationCatalogItem, ...]
    actions: tuple[ActionCatalogItem, ...]
    permissions_by_id: Mapping[str, PermissionCatalogItem]
    pages_by_id: Mapping[str, PageCatalogItem]
    features_by_id: Mapping[str, FeatureCatalogItem]
    help_by_id: Mapping[str, HelpArticle]
    recommendations_by_id: Mapping[str, RecommendationCatalogItem]
    actions_by_id: Mapping[str, ActionCatalogItem]

    @property
    def summary_counts(self) -> Mapping[str, int]:
        """Stable catalog count summary for the validation CLI."""
        return MappingProxyType(
            {
                "actions": len(self.actions),
                "features": len(self.features),
                "help_articles": len(self.help_articles),
                "pages": len(self.pages),
                "permissions": len(self.permissions),
                "recommendations": len(self.recommendations),
            }
        )


def load_knowledge(root: Path | str) -> KnowledgeIndex:
    """Load, validate, and sort all catalog sources under *root*."""
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise KnowledgeValidationError(f"knowledge directory does not exist: {root_path}")

    manifest = _parse_model(
        _read_yaml(root_path / "manifest.yaml"), CatalogManifest, "manifest.yaml"
    )
    _validate_manifest_files(root_path, manifest)
    app = _parse_model(_read_yaml(root_path / "app.yaml"), AppCatalogItem, "app.yaml")
    permissions = _parse_collection(
        root_path / "permissions.yaml", PermissionCatalogItem, "permissions"
    )
    pages = _parse_collection(root_path / "pages.yaml", PageCatalogItem, "pages")
    features = _parse_collection(root_path / "features.yaml", FeatureCatalogItem, "features")
    recommendations = _parse_collection(
        root_path / "recommendations.yaml", RecommendationCatalogItem, "recommendations"
    )
    actions = _parse_collection(root_path / "actions.yaml", ActionCatalogItem, "actions")
    help_articles = tuple(
        _parse_help_article(root_path / relative_path, relative_path)
        for relative_path in sorted(manifest.help_files)
    )

    index = _make_index(
        root_path,
        manifest,
        app,
        permissions,
        pages,
        features,
        help_articles,
        recommendations,
        actions,
    )
    _validate_cross_references(index)
    return index


def _read_yaml(path: Path) -> object:
    if not path.is_file():
        raise KnowledgeValidationError(f"catalog source file is missing: {path.name}")
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise KnowledgeValidationError(f"invalid YAML in {path.name}: {error}") from error
    if not isinstance(loaded, dict):
        raise KnowledgeValidationError(f"{path.name} must contain a YAML mapping")
    return loaded


def _parse_model(raw: object, model_type: type[_T], label: str) -> _T:
    try:
        # Catalog files are wire-format documents. Pydantic's strict JSON path
        # accepts JSON arrays/enums while preserving Prompt 4's strict Python API.
        return model_type.model_validate_json(json.dumps(raw, default=str))
    except ValidationError as error:
        raise KnowledgeValidationError(f"invalid {label}: {error}") from error


def _parse_collection(path: Path, model_type: type[_T], collection_key: str) -> tuple[_T, ...]:
    raw = _read_yaml(path)
    assert isinstance(raw, dict)
    values = raw.get(collection_key)
    if not isinstance(values, list):
        raise KnowledgeValidationError(f"{path.name} must contain a '{collection_key}' list")
    unexpected = set(raw).difference({collection_key})
    if unexpected:
        raise KnowledgeValidationError(
            f"{path.name} contains unexpected keys: {sorted(unexpected)}"
        )
    return tuple(
        _parse_model(value, model_type, f"{path.name} item {position}")
        for position, value in enumerate(values, 1)
    )


def _parse_help_article(path: Path, label: str) -> HelpArticle:
    if not path.is_file():
        raise KnowledgeValidationError(f"help source file is missing: {label}")
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise KnowledgeValidationError(f"help article has malformed Markdown metadata: {label}")
    closing_marker = text.find("\n---\n", 4)
    if closing_marker == -1:
        raise KnowledgeValidationError(f"help article has malformed Markdown metadata: {label}")
    metadata_text = text[4:closing_marker]
    content = text[closing_marker + 5 :].strip()
    if not content:
        raise KnowledgeValidationError(f"help article body is missing: {label}")
    try:
        metadata = yaml.safe_load(metadata_text)
    except yaml.YAMLError as error:
        raise KnowledgeValidationError(
            f"help article has malformed Markdown metadata: {label}"
        ) from error
    if not isinstance(metadata, dict):
        raise KnowledgeValidationError(f"help article has malformed Markdown metadata: {label}")
    return _parse_model({**metadata, "content": content}, HelpArticle, label)


def _validate_manifest_files(root: Path, manifest: CatalogManifest) -> None:
    actual_catalog_files = frozenset(manifest.catalog_files)
    if actual_catalog_files != _CATALOG_FILES:
        raise KnowledgeValidationError(
            "manifest catalog_files must list exactly the required catalog source files"
        )
    for relative_path in (*manifest.catalog_files, *manifest.help_files):
        path = root / relative_path
        if not path.is_file():
            raise KnowledgeValidationError(f"manifest source file is missing: {relative_path}")


def _make_index(
    root: Path,
    manifest: CatalogManifest,
    app: AppCatalogItem,
    permissions: tuple[PermissionCatalogItem, ...],
    pages: tuple[PageCatalogItem, ...],
    features: tuple[FeatureCatalogItem, ...],
    help_articles: tuple[HelpArticle, ...],
    recommendations: tuple[RecommendationCatalogItem, ...],
    actions: tuple[ActionCatalogItem, ...],
) -> KnowledgeIndex:
    permissions = tuple(sorted(permissions, key=lambda item: item.permission.root))
    pages = tuple(sorted(pages, key=lambda item: item.page_id))
    features = tuple(sorted(features, key=lambda item: item.feature_id))
    help_articles = tuple(sorted(help_articles, key=lambda item: item.article_id))
    recommendations = tuple(sorted(recommendations, key=lambda item: item.rule_id))
    actions = tuple(sorted(actions, key=lambda item: item.action.action_id))

    return KnowledgeIndex(
        root=root,
        manifest=manifest,
        app=app,
        permissions=permissions,
        pages=pages,
        features=features,
        help_articles=help_articles,
        recommendations=recommendations,
        actions=actions,
        permissions_by_id=_unique_map(permissions, lambda item: item.permission.root, "permission"),
        pages_by_id=_unique_map(pages, lambda item: item.page_id, "page"),
        features_by_id=_unique_map(features, lambda item: item.feature_id, "feature"),
        help_by_id=_unique_map(help_articles, lambda item: item.article_id, "help article"),
        recommendations_by_id=_unique_map(
            recommendations, lambda item: item.rule_id, "recommendation rule"
        ),
        actions_by_id=_unique_map(actions, lambda item: item.action.action_id, "action"),
    )


def _unique_map(
    items: tuple[_T, ...], key_function: Callable[[_T], str], item_name: str
) -> Mapping[str, _T]:
    result: dict[str, _T] = {}
    for item in items:
        identifier = key_function(item)
        if identifier in result:
            raise KnowledgeValidationError(f"duplicate {item_name} ID: {identifier}")
        result[identifier] = item
    return MappingProxyType(result)


def _validate_cross_references(index: KnowledgeIndex) -> None:
    if index.app.metadata.app_id != index.manifest.app_id:
        raise KnowledgeValidationError("app metadata app_id must match manifest app_id")
    _require_app_id(index.app.metadata.app_id, index.manifest.app_id, "app metadata")
    _require_active(index.app.provenance.status, "app metadata")

    all_references = [
        index.manifest.provenance.safe_reference.root,
        index.app.provenance.safe_reference.root,
    ]
    for permission_item in index.permissions:
        _validate_common_item(permission_item, index, permission_item.permission.root)
        all_references.append(permission_item.provenance.safe_reference.root)
    for page_item in index.pages:
        _require_app_id(page_item.app_id, index.manifest.app_id, f"page {page_item.page_id}")
        _validate_common_item(page_item, index, f"page {page_item.page_id}")
        _require_known(
            page_item.feature_ids, index.features_by_id, f"page {page_item.page_id} feature"
        )
        _require_known(
            page_item.related_page_ids, index.pages_by_id, f"page {page_item.page_id} related page"
        )
        _require_known(
            page_item.related_feature_ids,
            index.features_by_id,
            f"page {page_item.page_id} related feature",
        )
        _require_known(
            page_item.available_action_ids, index.actions_by_id, f"page {page_item.page_id} action"
        )
        all_references.append(page_item.provenance.safe_reference.root)
    for feature_item in index.features:
        _require_app_id(
            feature_item.app_id, index.manifest.app_id, f"feature {feature_item.feature_id}"
        )
        _validate_common_item(feature_item, index, f"feature {feature_item.feature_id}")
        _require_known(
            feature_item.page_ids, index.pages_by_id, f"feature {feature_item.feature_id} page"
        )
        _require_known(
            feature_item.related_feature_ids,
            index.features_by_id,
            f"feature {feature_item.feature_id} related feature",
        )
        _require_known(
            feature_item.available_action_ids,
            index.actions_by_id,
            f"feature {feature_item.feature_id} action",
        )
        if any(app_id != index.manifest.app_id for app_id in feature_item.related_app_ids):
            raise KnowledgeValidationError(
                f"feature {feature_item.feature_id} has an unknown related app"
            )
        all_references.append(feature_item.provenance.safe_reference.root)
    for help_item in index.help_articles:
        _require_app_id(
            help_item.app_id, index.manifest.app_id, f"help article {help_item.article_id}"
        )
        _validate_common_item(help_item, index, f"help article {help_item.article_id}")
        _require_known(
            help_item.page_ids, index.pages_by_id, f"help article {help_item.article_id} page"
        )
        _require_known(
            help_item.feature_ids,
            index.features_by_id,
            f"help article {help_item.article_id} feature",
        )
        _require_known(
            help_item.related_article_ids,
            index.help_by_id,
            f"help article {help_item.article_id} related article",
        )
        _require_known(
            help_item.related_feature_ids,
            index.features_by_id,
            f"help article {help_item.article_id} related feature",
        )
        _require_known(
            help_item.available_action_ids,
            index.actions_by_id,
            f"help article {help_item.article_id} action",
        )
        all_references.append(help_item.provenance.safe_reference.root)
    for recommendation_item in index.recommendations:
        _validate_common_item(
            recommendation_item, index, f"recommendation rule {recommendation_item.rule_id}"
        )
        _require_known(
            recommendation_item.page_ids,
            index.pages_by_id,
            f"recommendation rule {recommendation_item.rule_id} page",
        )
        _require_known(
            recommendation_item.feature_ids,
            index.features_by_id,
            f"recommendation rule {recommendation_item.rule_id} feature",
        )
        if recommendation_item.action_id is not None:
            _require_known(
                (recommendation_item.action_id,),
                index.actions_by_id,
                f"recommendation rule {recommendation_item.rule_id} action",
            )
        _require_known(
            recommendation_item.related_rule_ids,
            index.recommendations_by_id,
            f"recommendation rule {recommendation_item.rule_id} related rule",
        )
        all_references.append(recommendation_item.provenance.safe_reference.root)
    for action_item in index.actions:
        _require_app_id(
            action_item.action.owner_app_id,
            index.manifest.app_id,
            f"action {action_item.action.action_id}",
        )
        _validate_common_item(action_item, index, f"action {action_item.action.action_id}")
        _require_known(
            action_item.page_ids,
            index.pages_by_id,
            f"action {action_item.action.action_id} page",
        )
        _require_known(
            action_item.feature_ids,
            index.features_by_id,
            f"action {action_item.action.action_id} feature",
        )
        _require_known(
            action_item.related_action_ids,
            index.actions_by_id,
            f"action {action_item.action.action_id} related action",
        )
        _require_known(
            (action_item.action.required_permission.root,),
            index.permissions_by_id,
            "action permission",
        )
        all_references.append(action_item.provenance.safe_reference.root)

    if len(all_references) != len(set(all_references)):
        raise KnowledgeValidationError("catalog source references must be unique")


def _validate_common_item(item: _Provenanced, index: KnowledgeIndex, label: str) -> None:
    provenance = item.provenance
    if provenance.status is CatalogStatus.DRAFT:
        raise KnowledgeValidationError(f"{label} cannot be draft catalog content")
    permissions = getattr(item, "required_permissions", ())
    _require_known(
        tuple(permission.root for permission in permissions),
        index.permissions_by_id,
        f"{label} permission",
    )
    if provenance.status is CatalogStatus.ACTIVE:
        _validate_active_targets(item, index, label)


def _validate_active_targets(item: object, index: KnowledgeIndex, label: str) -> None:
    target_sets = (
        (getattr(item, "page_ids", ()), index.pages_by_id, "page"),
        (getattr(item, "feature_ids", ()), index.features_by_id, "feature"),
        (getattr(item, "related_page_ids", ()), index.pages_by_id, "related page"),
        (getattr(item, "related_feature_ids", ()), index.features_by_id, "related feature"),
        (getattr(item, "available_action_ids", ()), index.actions_by_id, "action"),
        (getattr(item, "action_ids", ()), index.actions_by_id, "action"),
        (getattr(item, "related_action_ids", ()), index.actions_by_id, "related action"),
        (getattr(item, "related_article_ids", ()), index.help_by_id, "related help article"),
        (getattr(item, "related_rule_ids", ()), index.recommendations_by_id, "related rule"),
    )
    for identifiers, lookup, target_name in target_sets:
        for identifier in identifiers:
            target = lookup.get(identifier)
            if target is not None and _status_of(target) is not CatalogStatus.ACTIVE:
                raise KnowledgeValidationError(
                    f"active {label} cannot reference non-active {target_name}: {identifier}"
                )
    action_id = getattr(item, "action_id", None)
    if action_id is not None:
        action = index.actions_by_id.get(action_id)
        if action is not None and _status_of(action) is not CatalogStatus.ACTIVE:
            raise KnowledgeValidationError(
                f"active {label} cannot reference non-active action: {action_id}"
            )


def _require_known(identifiers: tuple[str, ...], lookup: Mapping[str, object], label: str) -> None:
    for identifier in identifiers:
        if identifier not in lookup:
            raise KnowledgeValidationError(f"unknown {label}: {identifier}")


def _status_of(item: object) -> CatalogStatus:
    if not isinstance(item, _Provenanced):
        raise AssertionError("catalog index contains an item without provenance")
    return item.provenance.status


def _require_app_id(actual: str, expected: str, label: str) -> None:
    if actual != expected:
        raise KnowledgeValidationError(f"{label} app_id must match manifest app_id")


def _require_active(status: CatalogStatus, label: str) -> None:
    if status is not CatalogStatus.ACTIVE:
        raise KnowledgeValidationError(f"{label} must be active")
