"""Application dependency construction points."""

from dataclasses import dataclass

from orkafin.adapters.orka_ats import MOCK_ORKA_ATS_APP_ID, MockOrkaATSAdapter
from orkafin.adapters.registry import AdapterRegistration, AdapterRegistry
from orkafin.application.auth import MissingTrustedSessionResolver, TrustedSessionResolver
from orkafin.application.context import AuditRecorder
from orkafin.core.settings import Settings
from orkafin.infrastructure.database.audit import DatabaseAuditRecorder
from orkafin.infrastructure.database.session import Database


@dataclass(frozen=True, slots=True)
class ApplicationDependencies:
    """Dependencies supplied to routes and future application services."""

    settings: Settings
    database: Database
    adapter_registry: AdapterRegistry
    trusted_session_resolver: TrustedSessionResolver
    audit_recorder: AuditRecorder


def build_dependencies(
    settings: Settings,
    *,
    adapter_registry: AdapterRegistry | None = None,
    trusted_session_resolver: TrustedSessionResolver | None = None,
    audit_recorder: AuditRecorder | None = None,
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
    )
