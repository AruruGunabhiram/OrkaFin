"""FastAPI application factory."""

from fastapi import FastAPI

from orkafin.api.routes import create_router
from orkafin.core.dependencies import ApplicationDependencies, build_dependencies
from orkafin.core.settings import Settings, default_settings


def create_app(
    *,
    settings: Settings | None = None,
    dependencies: ApplicationDependencies | None = None,
) -> FastAPI:
    """Create an isolated application instance with explicit dependencies."""
    if settings is not None and dependencies is not None:
        raise ValueError("Pass settings or dependencies, not both.")

    resolved_dependencies = dependencies or build_dependencies(settings or default_settings())
    resolved_settings = resolved_dependencies.settings
    application = FastAPI(
        title=resolved_settings.application_name,
        version=resolved_settings.api_version,
        docs_url=None,
        redoc_url=None,
    )
    application.include_router(create_router(resolved_dependencies))
    return application
