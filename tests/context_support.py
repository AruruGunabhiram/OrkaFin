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


def build_context_application(
    database_path: Path,
    *,
    subject_reference: str | None = "limited_viewer",
    adapter_factory: Callable[[], OrkaApplicationAdapter] = MockOrkaATSAdapter,
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
    )
    Base.metadata.create_all(dependencies.database.engine)
    return create_app(dependencies=dependencies), dependencies


def context_hint(
    *,
    app_id: str = "orka_ats",
    page_id: str = "candidate_profile",
    candidate_id: str | None = "CAND-1042",
) -> dict[str, object]:
    """Return a browser hint carrying intentionally forged authorization claims."""
    selected_entity: dict[str, str] | None = None
    if candidate_id is not None:
        selected_entity = {
            "app_id_hint": app_id,
            "entity_type_hint": "candidate",
            "entity_id_hint": candidate_id,
        }
    return {
        "app_id_hint": app_id,
        "page_id_hint": page_id,
        "workspace_id_hint": "workspace_recruiting_alpha",
        "selected_entity_hint": selected_entity,
        "claimed_user_id": "forged-admin-user",
        "claimed_email": "forged.admin@example.invalid",
        "claimed_role_ids": ["administrator"],
        "claimed_permissions": [
            "candidate.view",
            "candidate.notes.view",
            "candidate.update_start_date",
        ],
        "claimed_available_action_ids": ["candidate.update_start_date"],
        "client_request_id_hint": "00000000-0000-4000-8000-000000000999",
    }
