"""Tiny generic fake used only to prove the adapter contract suite."""

from __future__ import annotations

from datetime import UTC, datetime

from orkafin.adapters import (
    ADAPTER_CONTRACT_VERSION,
    AdapterCapability,
    AdapterCapabilityMetadata,
    AdapterMetadata,
    AdapterUnsupportedCapabilityError,
    ApplicationPageMetadata,
    ExecuteApprovedActionRequest,
    ExecuteApprovedActionResponse,
    GetAppMetadataRequest,
    GetAppMetadataResponse,
    GetAvailableActionsRequest,
    GetAvailableActionsResponse,
    GetAvailableFeaturesRequest,
    GetAvailableFeaturesResponse,
    GetPageMetadataRequest,
    GetPageMetadataResponse,
    GetRecentUserEventsRequest,
    GetRecentUserEventsResponse,
    GetSelectedEntitySummaryRequest,
    GetSelectedEntitySummaryResponse,
    GetUserPermissionsRequest,
    GetUserPermissionsResponse,
    LogFeedbackRequest,
    LogFeedbackResponse,
    ResolveContextRequest,
    ResolveContextResponse,
    ResolveCurrentUserRequest,
    ResolveCurrentUserResponse,
    ResolvedApplicationContext,
    SearchAllowedRecordsRequest,
    SearchAllowedRecordsResponse,
)
from orkafin.application.permissions import AuthorizationSource, TrustedAuthorizationFacts
from orkafin.domain.context import (
    AppMetadata,
    AppStatus,
    IdentityVerificationStatus,
    Role,
    UserIdentity,
    WorkspaceRef,
)

NOW = datetime(2026, 7, 13, 20, 0, tzinfo=UTC)
LATER = datetime(2026, 7, 13, 20, 5, tzinfo=UTC)
APP_ID = "sample_app"
RESPONSE_ID = "adapter-response-contract"


class MinimalContractFakeAdapter:
    """Generic baseline adapter with every optional capability explicitly unsupported."""

    def __init__(self) -> None:
        self._metadata = AdapterMetadata(
            adapter_id="sample_contract_fake",
            owning_app_id=APP_ID,
            adapter_version="1.0.0",
            capabilities=tuple(
                AdapterCapabilityMetadata(capability=capability, capability_version="1.0.0")
                for capability in (
                    AdapterCapability.GET_APP_METADATA,
                    AdapterCapability.RESOLVE_CURRENT_USER,
                    AdapterCapability.RESOLVE_CONTEXT,
                    AdapterCapability.GET_USER_PERMISSIONS,
                    AdapterCapability.GET_PAGE_METADATA,
                )
            ),
        )

    @property
    def metadata(self) -> AdapterMetadata:
        return self._metadata

    @staticmethod
    def _app_metadata() -> AppMetadata:
        return AppMetadata(
            app_id=APP_ID,
            display_name="Sample application",
            description="Synthetic application used only for contract conformance.",
            app_version="1.0.0",
            adapter_contract_version=ADAPTER_CONTRACT_VERSION,
            status=AppStatus.ACTIVE,
        )

    @staticmethod
    def _identity() -> UserIdentity:
        return UserIdentity(
            user_id="sample-user",
            display_name="Sample User",
            role=Role(role_id="sample_role", display_name="Sample role", owner_app_id=APP_ID),
            verification_status=IdentityVerificationStatus.ADAPTER_VERIFIED,
            verified_at=NOW,
            verification_reference="adapter-user-reference",
        )

    async def get_app_metadata(self, request: GetAppMetadataRequest) -> GetAppMetadataResponse:
        return GetAppMetadataResponse(
            request_id=request.request_id,
            app_id=request.app_id,
            adapter_response_id=RESPONSE_ID,
            responded_at=NOW,
            app_metadata=self._app_metadata(),
        )

    async def resolve_current_user(
        self, request: ResolveCurrentUserRequest
    ) -> ResolveCurrentUserResponse:
        return ResolveCurrentUserResponse(
            request_id=request.request_id,
            app_id=request.app_id,
            adapter_response_id=RESPONSE_ID,
            responded_at=NOW,
            identity=self._identity(),
        )

    async def resolve_context(self, request: ResolveContextRequest) -> ResolveContextResponse:
        context = ResolvedApplicationContext(
            app=self._app_metadata(),
            identity=request.trusted_identity,
            page_id=request.client_hint.page,
            workspace=WorkspaceRef(workspace_id="sample-workspace", app_id=APP_ID),
            resolved_at=NOW,
            valid_until=LATER,
        )
        return ResolveContextResponse(
            request_id=request.request_id,
            app_id=request.app_id,
            adapter_response_id=RESPONSE_ID,
            responded_at=NOW,
            context=context,
        )

    async def get_user_permissions(
        self, request: GetUserPermissionsRequest
    ) -> GetUserPermissionsResponse:
        facts = TrustedAuthorizationFacts(
            source=AuthorizationSource.APPLICATION_ADAPTER,
            adapter_response_id=RESPONSE_ID,
            app_id=APP_ID,
            app_access=True,
            allowed_page_ids=(request.context.page_id,),
        )
        return GetUserPermissionsResponse(
            request_id=request.request_id,
            app_id=request.app_id,
            adapter_response_id=RESPONSE_ID,
            responded_at=NOW,
            authorization_facts=facts,
        )

    async def get_page_metadata(self, request: GetPageMetadataRequest) -> GetPageMetadataResponse:
        page = ApplicationPageMetadata(
            app_id=APP_ID,
            page_id=request.context.page_id,
            page_version="1.0.0",
            title="Sample page",
            purpose="Exercise the generic adapter contract.",
            safe_reference="app://sample_app/pages/sample",
        )
        return GetPageMetadataResponse(
            request_id=request.request_id,
            app_id=request.app_id,
            adapter_response_id=RESPONSE_ID,
            responded_at=NOW,
            page_metadata=page,
        )

    async def get_selected_entity_summary(
        self, request: GetSelectedEntitySummaryRequest
    ) -> GetSelectedEntitySummaryResponse:
        raise AdapterUnsupportedCapabilityError(
            request_id=request.request_id,
            app_id=request.app_id,
        )

    async def get_available_features(
        self, request: GetAvailableFeaturesRequest
    ) -> GetAvailableFeaturesResponse:
        raise AdapterUnsupportedCapabilityError(
            request_id=request.request_id,
            app_id=request.app_id,
        )

    async def get_available_actions(
        self, request: GetAvailableActionsRequest
    ) -> GetAvailableActionsResponse:
        raise AdapterUnsupportedCapabilityError(
            request_id=request.request_id,
            app_id=request.app_id,
        )

    async def get_recent_user_events(
        self, request: GetRecentUserEventsRequest
    ) -> GetRecentUserEventsResponse:
        raise AdapterUnsupportedCapabilityError(
            request_id=request.request_id,
            app_id=request.app_id,
        )

    async def search_allowed_records(
        self, request: SearchAllowedRecordsRequest
    ) -> SearchAllowedRecordsResponse:
        raise AdapterUnsupportedCapabilityError(
            request_id=request.request_id,
            app_id=request.app_id,
        )

    async def execute_approved_action(
        self, request: ExecuteApprovedActionRequest
    ) -> ExecuteApprovedActionResponse:
        raise AdapterUnsupportedCapabilityError(
            request_id=request.request_id,
            app_id=request.app_id,
        )

    async def log_feedback(self, request: LogFeedbackRequest) -> LogFeedbackResponse:
        raise AdapterUnsupportedCapabilityError(
            request_id=request.request_id,
            app_id=request.app_id,
        )
