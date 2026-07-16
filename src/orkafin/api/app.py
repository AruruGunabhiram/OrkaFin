"""FastAPI application factory."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from orkafin.api.routes import create_router
from orkafin.core.dependencies import ApplicationDependencies, build_dependencies
from orkafin.core.errors import install_exception_handlers
from orkafin.core.logging import configure_logging
from orkafin.core.request_id import RequestIDMiddleware
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
    configure_logging(resolved_settings.log_level)
    application = FastAPI(
        title=resolved_settings.application_name,
        version=resolved_settings.api_version,
        docs_url=None,
        redoc_url=None,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.allowed_origins),
        allow_credentials=resolved_settings.cors_allow_credentials,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )
    application.add_middleware(
        RequestIDMiddleware,
        accept_incoming=resolved_settings.accept_incoming_request_ids,
    )
    install_exception_handlers(application, debug=resolved_settings.debug)
    application.include_router(create_router(resolved_dependencies))
    web_root = Path(__file__).resolve().parents[1] / "web"

    @application.get("/demo", include_in_schema=False)
    def local_demo() -> FileResponse:
        """Serve the synthetic local-only widget harness from the same origin."""
        return FileResponse(web_root / "demo.html")

    application.mount(
        "/_orkafin/static",
        StaticFiles(directory=web_root / "assets"),
        name="orkafin-web-assets",
    )
    return application
