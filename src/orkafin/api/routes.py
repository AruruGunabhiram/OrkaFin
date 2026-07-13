"""Routes that are safe to expose during repository scaffolding."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from orkafin.core.dependencies import ApplicationDependencies


class HealthResponse(BaseModel):
    """Versioned service-health payload."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok"]
    service: str
    version: str


def create_router(dependencies: ApplicationDependencies) -> APIRouter:
    """Create routes bound to an explicit dependency container."""
    router = APIRouter()

    @router.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service=dependencies.settings.service_name,
            version=dependencies.settings.api_version,
        )

    return router
