"""Application dependency construction points."""

from dataclasses import dataclass

from orkafin.core.settings import Settings


@dataclass(frozen=True, slots=True)
class ApplicationDependencies:
    """Dependencies supplied to routes and future application services."""

    settings: Settings


def build_dependencies(settings: Settings) -> ApplicationDependencies:
    """Build the dependency container without global mutable state."""
    return ApplicationDependencies(settings=settings)
