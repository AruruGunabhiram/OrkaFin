"""Application dependency construction points."""

from dataclasses import dataclass
from pathlib import Path

from orkafin.adapters.orka_ats import MOCK_ORKA_ATS_APP_ID, MockOrkaATSAdapter
from orkafin.adapters.registry import AdapterRegistration, AdapterRegistry
from orkafin.application.auth import MissingTrustedSessionResolver, TrustedSessionResolver
from orkafin.application.context import AuditRecorder
from orkafin.core.settings import Settings
from orkafin.infrastructure.database.audit import DatabaseAuditRecorder
from orkafin.infrastructure.database.session import Database
from orkafin.knowledge import KnowledgeIndex, load_knowledge
from orkafin.providers.base import ResponseProvider
from orkafin.providers.factory import build_response_provider


@dataclass(frozen=True, slots=True)
class ApplicationDependencies:
    """Dependencies supplied to routes and future application services."""

    settings: Settings
    database: Database
    adapter_registry: AdapterRegistry
    trusted_session_resolver: TrustedSessionResolver
    audit_recorder: AuditRecorder
    response_provider: ResponseProvider
    knowledge_index: KnowledgeIndex


def build_dependencies(
    settings: Settings,
    *,
    adapter_registry: AdapterRegistry | None = None,
    trusted_session_resolver: TrustedSessionResolver | None = None,
    audit_recorder: AuditRecorder | None = None,
    response_provider: ResponseProvider | None = None,
    knowledge_index: KnowledgeIndex | None = None,
) -> ApplicationDependencies:
    """Build the dependency container without global mutable state."""
    database = Database(settings.database_url)
    if adapter_registry is None:
        adapter_registry = AdapterRegistry(
            (
                AdapterRegistration(
                    app_id=MOCK_ORKA_ATS_APP_ID,
                    factory=MockOrkaATSAdapter,
                ),
            )
            if settings.fixture_mode
            else ()
        )
    return ApplicationDependencies(
        settings=settings,
        database=database,
        adapter_registry=adapter_registry,
        trusted_session_resolver=(trusted_session_resolver or MissingTrustedSessionResolver()),
        audit_recorder=audit_recorder or DatabaseAuditRecorder(database),
        response_provider=response_provider or build_response_provider(settings),
        knowledge_index=knowledge_index or load_knowledge(_default_knowledge_root()),
    )


def _default_knowledge_root() -> Path:
    """Locate the repository-controlled OrkaATS knowledge used by Local V1."""
    return Path(__file__).resolve().parents[3] / "knowledge" / "orka_ats"
