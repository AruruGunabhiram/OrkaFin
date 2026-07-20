from __future__ import annotations

from pathlib import Path
from shutil import copytree

import pytest
import yaml

from orkafin.domain.catalog import CatalogStatus, VerificationStatus
from orkafin.knowledge import KnowledgeValidationError, load_knowledge


def catalog_copy(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[2] / "knowledge" / "orka_ats"
    target = tmp_path / "orka_ats"
    copytree(source, target)
    return target


def read_yaml(path: Path) -> dict[str, object]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def write_yaml(path: Path, value: dict[str, object]) -> None:
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def test_loads_valid_starter_catalog_with_stable_counts(tmp_path: Path) -> None:
    index = load_knowledge(catalog_copy(tmp_path))

    assert index.manifest.provenance.content_version == "0.1.0"
    assert index.summary_counts == {
        "actions": 1,
        "features": 5,
        "help_articles": 6,
        "pages": 6,
        "permissions": 4,
        "recommendations": 1,
    }
    assert index.pages_by_id["candidate_profile"].provenance.safe_reference.root.endswith(
        "/candidate_profile"
    )
    assert index.help_by_id["help_recruitment_pipeline"].provenance.verification_status is (
        VerificationStatus.PROVISIONAL
    )
    action = index.actions_by_id["candidate.update_start_date"].action
    assert action.status is CatalogStatus.ACTIVE
    assert action.action_version == "1.0.0"
    assert action.owner_app_id == "orka_ats"
    assert action.required_permission.root == "candidate.update_start_date"
    assert [parameter.parameter_id for parameter in action.parameters] == ["start_date"]
    assert action.validation_rules
    assert action.confirmation_required is True
    assert action.reversible is True
    assert action.execution_mode == "mock_only"
    assert action.audit_field_ids
    assert action.failure_behavior == "fail_closed_without_execution"


def test_rejects_duplicate_ids(tmp_path: Path) -> None:
    root = catalog_copy(tmp_path)
    pages_path = root / "pages.yaml"
    pages = read_yaml(pages_path)
    page_items = pages["pages"]
    assert isinstance(page_items, list)
    page_items.append(page_items[0])
    write_yaml(pages_path, pages)

    with pytest.raises(KnowledgeValidationError, match="duplicate page ID"):
        load_knowledge(root)


def test_rejects_dangling_references(tmp_path: Path) -> None:
    root = catalog_copy(tmp_path)
    pages_path = root / "pages.yaml"
    pages = read_yaml(pages_path)
    page_items = pages["pages"]
    assert isinstance(page_items, list)
    assert isinstance(page_items[0], dict)
    page_items[0]["feature_ids"] = ["missing_feature"]
    write_yaml(pages_path, pages)

    with pytest.raises(KnowledgeValidationError, match="unknown page candidate_dashboard feature"):
        load_knowledge(root)


def test_rejects_unknown_permissions_and_actions(tmp_path: Path) -> None:
    root = catalog_copy(tmp_path)
    features_path = root / "features.yaml"
    features = read_yaml(features_path)
    feature_items = features["features"]
    assert isinstance(feature_items, list)
    assert isinstance(feature_items[0], dict)
    feature_items[0]["required_permissions"] = ["candidate.unknown"]
    write_yaml(features_path, features)

    with pytest.raises(
        KnowledgeValidationError, match="unknown feature candidate_directory permission"
    ):
        load_knowledge(root)

    root = catalog_copy(tmp_path / "actions")
    pages_path = root / "pages.yaml"
    pages = read_yaml(pages_path)
    page_items = pages["pages"]
    assert isinstance(page_items, list)
    assert isinstance(page_items[0], dict)
    page_items[0]["available_action_ids"] = ["candidate.unknown_action"]
    write_yaml(pages_path, pages)

    with pytest.raises(KnowledgeValidationError, match="unknown page candidate_dashboard action"):
        load_knowledge(root)


def test_rejects_unknown_recommendation_rule_references(tmp_path: Path) -> None:
    root = catalog_copy(tmp_path)
    recommendations_path = root / "recommendations.yaml"
    recommendations = read_yaml(recommendations_path)
    rule_items = recommendations["recommendations"]
    assert isinstance(rule_items, list)
    assert isinstance(rule_items[0], dict)
    rule_items[0]["feature_ids"] = ["missing_feature"]
    write_yaml(recommendations_path, recommendations)

    with pytest.raises(
        KnowledgeValidationError,
        match="unknown recommendation rule review_recruitment_pipeline feature",
    ):
        load_knowledge(root)


def test_rejects_invalid_content_versions(tmp_path: Path) -> None:
    root = catalog_copy(tmp_path)
    manifest_path = root / "manifest.yaml"
    manifest = read_yaml(manifest_path)
    provenance = manifest["provenance"]
    assert isinstance(provenance, dict)
    provenance["content_version"] = "starter"
    write_yaml(manifest_path, manifest)

    with pytest.raises(KnowledgeValidationError, match="content_version"):
        load_knowledge(root)


def test_rejects_active_references_to_deprecated_items(tmp_path: Path) -> None:
    root = catalog_copy(tmp_path)
    pages_path = root / "pages.yaml"
    pages = read_yaml(pages_path)
    page_items = pages["pages"]
    assert isinstance(page_items, list)
    assert isinstance(page_items[1], dict)
    provenance = page_items[1]["provenance"]
    assert isinstance(provenance, dict)
    provenance["status"] = "deprecated"
    write_yaml(pages_path, pages)

    with pytest.raises(KnowledgeValidationError, match="cannot reference non-active page"):
        load_knowledge(root)


def test_rejects_missing_help_files_and_malformed_markdown_metadata(tmp_path: Path) -> None:
    root = catalog_copy(tmp_path)
    (root / "help" / "candidate_dashboard.md").unlink()

    with pytest.raises(KnowledgeValidationError, match="manifest source file is missing"):
        load_knowledge(root)

    root = catalog_copy(tmp_path / "malformed")
    (root / "help" / "candidate_dashboard.md").write_text("No front matter", encoding="utf-8")

    with pytest.raises(KnowledgeValidationError, match="malformed Markdown metadata"):
        load_knowledge(root)


def test_provisional_records_cannot_publish_steps_but_verified_records_can(tmp_path: Path) -> None:
    root = catalog_copy(tmp_path)
    pages_path = root / "pages.yaml"
    pages = read_yaml(pages_path)
    page_items = pages["pages"]
    assert isinstance(page_items, list)
    assert isinstance(page_items[0], dict)
    page_items[0]["instruction_steps"] = ["Verified control name has not been supplied."]
    write_yaml(pages_path, pages)

    with pytest.raises(
        KnowledgeValidationError, match="instruction steps require verified provenance"
    ):
        load_knowledge(root)

    provenance = page_items[0]["provenance"]
    assert isinstance(provenance, dict)
    provenance["verification_status"] = "verified"
    write_yaml(pages_path, pages)

    assert load_knowledge(root).pages_by_id["candidate_dashboard"].instruction_steps


def test_load_order_is_deterministic_when_source_lists_are_reordered(tmp_path: Path) -> None:
    root = catalog_copy(tmp_path)
    baseline = load_knowledge(root)
    pages_path = root / "pages.yaml"
    pages = read_yaml(pages_path)
    page_items = pages["pages"]
    assert isinstance(page_items, list)
    page_items.reverse()
    write_yaml(pages_path, pages)

    reordered = load_knowledge(root)

    assert tuple(item.page_id for item in reordered.pages) == tuple(
        item.page_id for item in baseline.pages
    )
    assert tuple(reordered.pages_by_id) == tuple(baseline.pages_by_id)
