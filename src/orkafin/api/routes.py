"""Routes that are safe to expose during repository scaffolding."""

from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request, status
from pydantic import BaseModel, ConfigDict

from orkafin.adapters import AdapterCapability, GetAppMetadataRequest
from orkafin.api.schemas import ConversationResponse, FeatureCatalogResponse
from orkafin.application.actions import (
    ActionConfirmationRequest,
    ActionConfirmationResponse,
    ActionProposalRequest,
    ActionProposalResponse,
    ActionProposalService,
)
from orkafin.application.assistant import AssistantQuery, AssistantQueryService
from orkafin.application.context import TrustedContextResolutionService
from orkafin.application.recommendations import (
    FeedbackRequest,
    FeedbackResponse,
    MeaningfulEventRequest,
    MeaningfulEventService,
    RecommendationEvaluationRequest,
    RecommendationEvaluationResponse,
    RecommendationService,
)
from orkafin.application.response_generation import ResponseGenerationService
from orkafin.application.retrieval import DeterministicRetrievalService
from orkafin.core.dependencies import ApplicationDependencies
from orkafin.core.request_id import get_request_id, new_request_id
from orkafin.domain.base import LowercaseIdentifier
from orkafin.domain.context import AppMetadata, ClientContextHint, ResolvedPageContext
from orkafin.domain.errors import ApiError
from orkafin.domain.events import UserEvent
from orkafin.domain.identifiers import RequestId
from orkafin.domain.responses import AssistantResponse


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
    event_service = MeaningfulEventService(
        database=dependencies.database,
        context_service=context_service,
    )
    recommendation_service = RecommendationService(
        database=dependencies.database,
        context_service=context_service,
        knowledge_index=dependencies.knowledge_index,
        settings=dependencies.settings,
        event_service=event_service,
    )
    assistant_service = AssistantQueryService(
        database=dependencies.database,
        context_service=context_service,
        retrieval_service=DeterministicRetrievalService(
            knowledge_index=dependencies.knowledge_index
        ),
        response_service=ResponseGenerationService(provider=dependencies.response_provider),
        event_service=event_service,
    )
    action_service = ActionProposalService(
        database=dependencies.database,
        context_service=context_service,
        adapter_registry=dependencies.adapter_registry,
        knowledge_index=dependencies.knowledge_index,
        settings=dependencies.settings,
    )

    def request_id_for(request: Request) -> RequestId:
        request_id_value = getattr(request.state, "request_id", None) or get_request_id()
        return RequestId(
            root=request_id_value if isinstance(request_id_value, str) else new_request_id()
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
        return await context_service.resolve(
            client_hint=client_hint, request_id=request_id_for(request)
        )

    @router.get(
        "/api/v1/apps/{app_id}/metadata",
        response_model=AppMetadata,
        responses={status.HTTP_404_NOT_FOUND: {"model": ApiError}},
        tags=["apps"],
    )
    async def app_metadata(app_id: str, request: Request) -> AppMetadata:
        """Expose adapter-owned public application metadata only."""
        adapter = dependencies.adapter_registry.resolve(
            app_id,
            required_capability=AdapterCapability.GET_APP_METADATA,
            request_id=request_id_for(request),
        )
        response = await adapter.get_app_metadata(
            GetAppMetadataRequest(request_id=request_id_for(request), app_id=app_id)
        )
        return response.app_metadata

    @router.get(
        "/api/v1/apps/{app_id}/features",
        response_model=FeatureCatalogResponse,
        responses={status.HTTP_404_NOT_FOUND: {"model": ApiError}},
        tags=["apps"],
    )
    def app_features(app_id: str) -> FeatureCatalogResponse:
        """Return the controlled catalog, not a user-specific authorization result."""
        index = dependencies.knowledge_index
        if index.manifest.app_id != app_id:
            from orkafin.application.context import AppNotSupportedError

            raise AppNotSupportedError
        return FeatureCatalogResponse(app=index.app.metadata, features=index.features)

    @router.post(
        "/api/v1/action-proposals",
        response_model=ActionProposalResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            status.HTTP_401_UNAUTHORIZED: {"model": ApiError},
            status.HTTP_403_FORBIDDEN: {"model": ApiError},
            status.HTTP_404_NOT_FOUND: {"model": ApiError},
            status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ApiError},
            status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ApiError},
        },
        tags=["actions"],
    )
    async def create_action_proposal(
        value: ActionProposalRequest, request: Request
    ) -> ActionProposalResponse:
        """Prepare one mock-only action and return its exact confirmation preview."""
        return await action_service.propose(value, request_id=request_id_for(request))

    @router.post(
        "/api/v1/action-proposals/{proposal_id}/confirmations",
        response_model=ActionConfirmationResponse,
        responses={
            status.HTTP_401_UNAUTHORIZED: {"model": ApiError},
            status.HTTP_403_FORBIDDEN: {"model": ApiError},
            status.HTTP_404_NOT_FOUND: {"model": ApiError},
            status.HTTP_409_CONFLICT: {"model": ApiError},
            status.HTTP_410_GONE: {"model": ApiError},
            status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ApiError},
            status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ApiError},
        },
        tags=["actions"],
    )
    async def confirm_action_proposal(
        proposal_id: str,
        value: ActionConfirmationRequest,
        request: Request,
    ) -> ActionConfirmationResponse:
        """Accept or reject intent only; this endpoint cannot execute an action."""
        return await action_service.confirm(
            proposal_id,
            value,
            request_id=request_id_for(request),
        )

    @router.post(
        "/api/v1/assistant/queries",
        response_model=AssistantResponse,
        responses={
            status.HTTP_401_UNAUTHORIZED: {"model": ApiError},
            status.HTTP_403_FORBIDDEN: {"model": ApiError},
            status.HTTP_404_NOT_FOUND: {"model": ApiError},
            status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ApiError},
        },
        tags=["assistant"],
    )
    async def assistant_query(value: AssistantQuery, request: Request) -> AssistantResponse:
        """Run one trusted, grounded assistant turn and persist safe visible messages."""
        return await assistant_service.query(value, request_id=request_id_for(request))

    @router.post(
        "/api/v1/events",
        response_model=UserEvent,
        responses={
            status.HTTP_401_UNAUTHORIZED: {"model": ApiError},
            status.HTTP_403_FORBIDDEN: {"model": ApiError},
        },
        tags=["events"],
    )
    async def submit_event(value: MeaningfulEventRequest, request: Request) -> UserEvent:
        """Record a small allowlisted product event after trusted context resolution."""
        return await event_service.submit(value, request_id=request_id_for(request))

    @router.post(
        "/api/v1/recommendations:evaluate",
        response_model=RecommendationEvaluationResponse,
        responses={
            status.HTTP_401_UNAUTHORIZED: {"model": ApiError},
            status.HTTP_403_FORBIDDEN: {"model": ApiError},
            status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ApiError},
        },
        tags=["recommendations"],
    )
    async def evaluate_recommendations(
        value: RecommendationEvaluationRequest, request: Request
    ) -> RecommendationEvaluationResponse:
        """Evaluate active source-backed rules; this endpoint never opens the widget itself."""
        return await recommendation_service.evaluate(value, request_id=request_id_for(request))

    @router.post(
        "/api/v1/feedback",
        response_model=FeedbackResponse,
        responses={
            status.HTTP_401_UNAUTHORIZED: {"model": ApiError},
            status.HTTP_403_FORBIDDEN: {"model": ApiError},
            status.HTTP_404_NOT_FOUND: {"model": ApiError},
        },
        tags=["feedback"],
    )
    async def submit_feedback(value: FeedbackRequest, request: Request) -> FeedbackResponse:
        """Persist feedback only for a recommendation owned by the verified user."""
        return await recommendation_service.submit_feedback(
            value, request_id=request_id_for(request)
        )

    @router.get(
        "/api/v1/conversations/{conversation_id}",
        response_model=ConversationResponse,
        responses={
            status.HTTP_401_UNAUTHORIZED: {"model": ApiError},
            status.HTTP_403_FORBIDDEN: {"model": ApiError},
            status.HTTP_404_NOT_FOUND: {"model": ApiError},
            status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ApiError},
        },
        tags=["conversations"],
    )
    async def get_conversation(
        conversation_id: str,
        request: Request,
        app_id: Annotated[LowercaseIdentifier, Query()],
        page: Annotated[LowercaseIdentifier, Query()],
    ) -> ConversationResponse:
        """Load a conversation only after resolving the current verified owner context."""
        context = await context_service.resolve(
            client_hint=ClientContextHint(app_id=app_id, page=page),
            request_id=request_id_for(request),
            include_candidate_summary=False,
        )
        conversation, messages = assistant_service.get_conversation(
            conversation_id=conversation_id, context=context
        )
        return ConversationResponse(conversation=conversation, messages=messages)

    return router
