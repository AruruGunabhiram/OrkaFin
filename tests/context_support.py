"""Shared construction helpers for trusted-context API tests."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI

from orkafin.adapters import AdapterRegistration, AdapterRegistry, OrkaApplicationAdapter
from orkafin.adapters.orka_ats import MOCK_ORKA_ATS_APP_ID, MockOrkaATSAdapter
from orkafin.api.app import create_app
from orkafin.application.auth import StaticTrustedSessionResolver
from orkafin.core.dependencies import ApplicationDependencies, build_dependencies
from orkafin.core.settings import Settings
from orkafin.infrastructure.database.base import Base
from orkafin.knowledge import KnowledgeIndex


def build_context_application(
    database_path: Path,
    *,
    subject_reference: str | None = "limited_viewer",
    adapter_factory: Callable[[], OrkaApplicationAdapter] = MockOrkaATSAdapter,
    knowledge_index: KnowledgeIndex | None = None,
) -> tuple[FastAPI, ApplicationDependencies]:
    """Build an isolated migrated-enough API with a server-injected synthetic session."""
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{database_path}",
        fixture_mode=True,
    )
    registry = AdapterRegistry(
        (
            AdapterRegistration(
                app_id=MOCK_ORKA_ATS_APP_ID,
                factory=adapter_factory,
            ),
        )
    )
    dependencies = build_dependencies(
        settings,
        adapter_registry=registry,
        trusted_session_resolver=StaticTrustedSessionResolver(subject_reference),
        knowledge_index=knowledge_index,
    )
    Base.metadata.create_all(dependencies.database.engine)
    return create_app(dependencies=dependencies), dependencies


def context_hint(
    *,
    app_id: str = "orka_ats",
    page_id: str = "candidate_profile",
    candidate_id: str | None = "CAND-1042",
) -> dict[str, object]:
    """Return the complete public navigation and selection hint."""
    selected_entity: dict[str, str] | None = None
    if candidate_id is not None:
        selected_entity = {
            "type": "candidate",
            "id": candidate_id,
        }
    return {
        "app_id": app_id,
        "page": page_id,
        "selected_entity": selected_entity,
    }
