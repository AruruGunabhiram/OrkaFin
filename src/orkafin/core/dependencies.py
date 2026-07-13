"""Application dependency construction points."""

from dataclasses import dataclass

from orkafin.adapters.registry import AdapterRegistry
from orkafin.core.settings import Settings
from orkafin.infrastructure.database.session import Database


@dataclass(frozen=True, slots=True)
class ApplicationDependencies:
    """Dependencies supplied to routes and future application services."""

    settings: Settings
    database: Database
    adapter_registry: AdapterRegistry


def build_dependencies(
    settings: Settings,
    *,
    adapter_registry: AdapterRegistry | None = None,
) -> ApplicationDependencies:
    """Build the dependency container without global mutable state."""
    return ApplicationDependencies(
        settings=settings,
        database=Database(settings.database_url),
        adapter_registry=adapter_registry or AdapterRegistry(),
    )
