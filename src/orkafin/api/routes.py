"""Routes that are safe to expose during repository scaffolding."""

from typing import Literal

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, ConfigDict

from orkafin.application.context import TrustedContextResolutionService
from orkafin.core.dependencies import ApplicationDependencies
from orkafin.core.request_id import get_request_id, new_request_id
from orkafin.domain.context import ClientContextHint, ResolvedPageContext
from orkafin.domain.errors import ApiError
from orkafin.domain.identifiers import RequestId


class HealthResponse(BaseModel):
    """Versioned service-health payload."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok"]
    service: str
    version: str


def create_router(dependencies: ApplicationDependencies) -> APIRouter:
    """Create routes bound to an explicit dependency container."""
    router = APIRouter()
    context_service = TrustedContextResolutionService(
        adapter_registry=dependencies.adapter_registry,
        trusted_session_resolver=dependencies.trusted_session_resolver,
        audit_recorder=dependencies.audit_recorder,
    )

    @router.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service=dependencies.settings.service_name,
            version=dependencies.settings.api_version,
        )

    @router.post(
        "/api/v1/contexts:resolve",
        response_model=ResolvedPageContext,
        responses={
            status.HTTP_401_UNAUTHORIZED: {"model": ApiError},
            status.HTTP_403_FORBIDDEN: {"model": ApiError},
            status.HTTP_404_NOT_FOUND: {"model": ApiError},
            status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ApiError},
        },
        tags=["context"],
    )
    async def resolve_context(
        client_hint: ClientContextHint, request: Request
    ) -> ResolvedPageContext:
        """Resolve browser hints into request-scoped adapter-verified context."""
        request_id_value = getattr(request.state, "request_id", None) or get_request_id()
        request_id = RequestId(
            root=request_id_value if isinstance(request_id_value, str) else new_request_id()
        )
        return await context_service.resolve(client_hint=client_hint, request_id=request_id)

    return router
