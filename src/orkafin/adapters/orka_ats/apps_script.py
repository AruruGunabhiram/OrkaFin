"""Authenticated HTTP transport for the OrkaATS Apps Script adapter boundary."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Protocol, TypeVar
from urllib.parse import urlsplit

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    SecretStr,
    ValidationError,
    model_validator,
)

from orkafin.adapters.base import (
    ADAPTER_CONTRACT_VERSION,
    AdapterCapability,
    AdapterCapabilityMetadata,
    AdapterContractVersion,
    AdapterMetadata,
    AdapterRequest,
    AdapterResponse,
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
    SearchAllowedRecordsRequest,
    SearchAllowedRecordsResponse,
)
from orkafin.adapters.errors import (
    AdapterConflictError,
    AdapterError,
    AdapterFailure,
    AdapterForbiddenError,
    AdapterInternalFailureError,
    AdapterNotFoundError,
    AdapterTimeoutError,
    AdapterUnauthorizedError,
    AdapterUnavailableError,
    AdapterValidationFailedError,
    adapter_error_from_failure,
)
from orkafin.adapters.orka_ats.crypto import create_signed_envelope
from orkafin.core.logging import get_logger
from orkafin.domain.base import (
    DataClassification,
    DataOwner,
    DomainModel,
    Identifier,
    LowercaseIdentifier,
    ModelDataPolicy,
    PersistencePolicy,
    UtcDatetime,
)
from orkafin.domain.identifiers import RequestId

if TYPE_CHECKING:
    from orkafin.core.config import Settings

APPS_SCRIPT_ORKA_ATS_ADAPTER_ID = "apps_script_orka_ats"
APPS_SCRIPT_ORKA_ATS_APP_ID = "orka_ats"
APPS_SCRIPT_WIRE_SCHEMA_VERSION = "v1"

_logger = get_logger("adapters.orka_ats.apps_script")
_ResponseT = TypeVar("_ResponseT", bound=AdapterResponse)


class AppsScriptAdapterConfig(BaseModel):
    """Validated operational and signing settings for the HTTP adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    enabled: bool = False
    endpoint_url: str | None = None
    version: int = Field(default=1, ge=1)
    key_id: str | None = Field(default=None, min_length=1, max_length=128)
    shared_secret: SecretStr | None = None
    timeout_seconds: float = Field(default=5.0, gt=0.0, le=10.0)
    max_response_bytes: int = Field(default=1_000_000, ge=1_024, le=2_000_000)

    @model_validator(mode="after")
    def validate_endpoint(self) -> AppsScriptAdapterConfig:
        if not self.enabled:
            return self
        if self.endpoint_url is None:
            raise ValueError("enabled Apps Script adapter requires endpoint_url")

        endpoint = self.endpoint_url.strip()
        parsed = urlsplit(endpoint)
        if endpoint != self.endpoint_url or parsed.scheme != "https" or parsed.hostname is None:
            raise ValueError("Apps Script endpoint_url must be an absolute HTTPS URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError(
                "Apps Script endpoint_url must not contain credentials, query, or fragment"
            )
        if not parsed.path.endswith("/exec"):
            raise ValueError("Apps Script endpoint_url must end in /exec")
        if self.key_id is None:
            raise ValueError("enabled Apps Script adapter requires key_id")
        if self.shared_secret is None:
            raise ValueError("enabled Apps Script adapter requires shared_secret")
        if not self.key_id.strip():
            raise ValueError("Apps Script key_id must not be blank")
        secret = self.shared_secret.get_secret_value()
        if re.fullmatch(r"[0-9a-fA-F]{64}", secret) is None:
            raise ValueError("Apps Script shared_secret must be 64 hexadecimal characters")
        return self

    @classmethod
    def from_settings(cls, settings: Settings) -> AppsScriptAdapterConfig:
        """Create adapter-local configuration from validated application settings."""

        secret = settings.orka_ats_adapter_shared_secret
        return cls(
            enabled=settings.adapter_mode.value == "apps_script",
            endpoint_url=settings.orka_ats_adapter_url,
            version=settings.orka_ats_adapter_version,
            key_id=settings.orka_ats_adapter_key_id,
            shared_secret=secret,
        )


@dataclass(frozen=True, slots=True)
class HttpTransportResponse:
    """Minimal HTTP response returned by an injected transport."""

    status_code: int
    body: bytes
    headers: Mapping[str, str] = field(default_factory=dict)


class HttpTransportTimeoutError(Exception):
    """Injected transport did not produce a response before its deadline."""


class HttpTransportError(Exception):
    """Injected transport could not complete the HTTP exchange."""


class AsyncHttpTransport(Protocol):
    """Library-neutral async HTTP transport used only by the adapter shell."""

    async def post(
        self,
        *,
        url: str,
        body: bytes,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> HttpTransportResponse:
        """POST one JSON body without interpreting adapter semantics."""
        ...


class HttpxAsyncHttpTransport:
    """Production HTTP transport implemented with ``httpx``.

    A client may be injected for connection pooling or mocked transport tests. When
    absent, the transport owns a short-lived client for the request.
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def post(
        self,
        *,
        url: str,
        body: bytes,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> HttpTransportResponse:
        try:
            if self._client is not None:
                response = await self._client.post(
                    url,
                    content=body,
                    headers=headers,
                    timeout=timeout_seconds,
                    follow_redirects=True,
                )
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        url,
                        content=body,
                        headers=headers,
                        timeout=timeout_seconds,
                        follow_redirects=True,
                    )
        except httpx.TimeoutException as error:
            raise HttpTransportTimeoutError from error
        except httpx.RequestError as error:
            raise HttpTransportError from error
        return HttpTransportResponse(
            status_code=response.status_code,
            body=response.content,
            headers=dict(response.headers),
        )


_WIRE_POLICY = ModelDataPolicy(
    owner=DataOwner.OWNING_APPLICATION,
    classification=DataClassification.RESTRICTED,
    persistence=PersistencePolicy.NEVER,
)


class AppsScriptRequestEnvelope(DomainModel):
    """Versioned operation envelope sent to the Apps Script router."""

    data_policy = _WIRE_POLICY

    adapter_contract_version: AdapterContractVersion = ADAPTER_CONTRACT_VERSION
    operation: AdapterCapability
    request_id: RequestId
    app_id: LowercaseIdentifier
    payload: dict[str, JsonValue]

    @model_validator(mode="after")
    def validate_payload_bindings(self) -> AppsScriptRequestEnvelope:
        if self.payload.get("schema_version") != self.schema_version:
            raise ValueError("request payload schema version must match its envelope")
        if self.payload.get("adapter_contract_version") != self.adapter_contract_version:
            raise ValueError("request payload adapter contract must match its envelope")
        if self.payload.get("request_id") != self.request_id.root:
            raise ValueError("request payload request ID must match its envelope")
        if self.payload.get("app_id") != self.app_id:
            raise ValueError("request payload app ID must match its envelope")
        return self


class AppsScriptSuccessEnvelope(DomainModel):
    """Versioned successful response envelope from the Apps Script router."""

    data_policy = _WIRE_POLICY

    adapter_contract_version: AdapterContractVersion = ADAPTER_CONTRACT_VERSION
    operation: AdapterCapability
    request_id: RequestId
    app_id: LowercaseIdentifier
    adapter_response_id: Identifier
    responded_at: UtcDatetime
    outcome: Literal["success"]
    payload: dict[str, JsonValue]


class AppsScriptFailureEnvelope(DomainModel):
    """Versioned typed failure envelope from the Apps Script router."""

    data_policy = _WIRE_POLICY

    adapter_contract_version: AdapterContractVersion = ADAPTER_CONTRACT_VERSION
    operation: AdapterCapability
    request_id: RequestId
    app_id: LowercaseIdentifier
    adapter_response_id: Identifier
    responded_at: UtcDatetime
    outcome: Literal["failure"]
    failure: AdapterFailure

    @model_validator(mode="after")
    def validate_failure_bindings(self) -> AppsScriptFailureEnvelope:
        if (
            self.failure.adapter_contract_version != self.adapter_contract_version
            or self.failure.request_id != self.request_id
            or self.failure.app_id != self.app_id
            or self.failure.adapter_response_id != self.adapter_response_id
        ):
            raise ValueError("adapter failure must match its response envelope")
        if self.responded_at < self.failure.failed_at:
            raise ValueError("response envelope cannot precede adapter failure")
        return self


class AppsScriptOrkaATSAdapter:
    """Signed HTTP client preserving the general application adapter protocol."""

    def __init__(
        self,
        *,
        transport: AsyncHttpTransport | None = None,
        config: AppsScriptAdapterConfig | None = None,
    ) -> None:
        self._config = config or AppsScriptAdapterConfig()
        if not self._config.enabled:
            raise AdapterUnavailableError(
                app_id=APPS_SCRIPT_ORKA_ATS_APP_ID,
                safe_message="The Apps Script OrkaATS adapter is disabled.",
            )
        assert self._config.endpoint_url is not None
        self._transport = transport or HttpxAsyncHttpTransport()
        self._metadata = AdapterMetadata(
            adapter_id=APPS_SCRIPT_ORKA_ATS_ADAPTER_ID,
            owning_app_id=APPS_SCRIPT_ORKA_ATS_APP_ID,
            adapter_version="1.0.0",
            capabilities=tuple(
                AdapterCapabilityMetadata(capability=capability, capability_version="1.0.0")
                for capability in AdapterCapability
            ),
        )

    @property
    def metadata(self) -> AdapterMetadata:
        return self._metadata

    async def get_app_metadata(self, request: GetAppMetadataRequest) -> GetAppMetadataResponse:
        return await self._send(AdapterCapability.GET_APP_METADATA, request, GetAppMetadataResponse)

    async def resolve_current_user(
        self, request: ResolveCurrentUserRequest
    ) -> ResolveCurrentUserResponse:
        return await self._send(
            AdapterCapability.RESOLVE_CURRENT_USER, request, ResolveCurrentUserResponse
        )

    async def resolve_context(self, request: ResolveContextRequest) -> ResolveContextResponse:
        return await self._send(AdapterCapability.RESOLVE_CONTEXT, request, ResolveContextResponse)

    async def get_user_permissions(
        self, request: GetUserPermissionsRequest
    ) -> GetUserPermissionsResponse:
        return await self._send(
            AdapterCapability.GET_USER_PERMISSIONS, request, GetUserPermissionsResponse
        )

    async def get_page_metadata(self, request: GetPageMetadataRequest) -> GetPageMetadataResponse:
        return await self._send(
            AdapterCapability.GET_PAGE_METADATA, request, GetPageMetadataResponse
        )

    async def get_selected_entity_summary(
        self, request: GetSelectedEntitySummaryRequest
    ) -> GetSelectedEntitySummaryResponse:
        return await self._send(
            AdapterCapability.GET_SELECTED_ENTITY_SUMMARY,
            request,
            GetSelectedEntitySummaryResponse,
        )

    async def get_available_features(
        self, request: GetAvailableFeaturesRequest
    ) -> GetAvailableFeaturesResponse:
        return await self._send(
            AdapterCapability.GET_AVAILABLE_FEATURES, request, GetAvailableFeaturesResponse
        )

    async def get_available_actions(
        self, request: GetAvailableActionsRequest
    ) -> GetAvailableActionsResponse:
        return await self._send(
            AdapterCapability.GET_AVAILABLE_ACTIONS, request, GetAvailableActionsResponse
        )

    async def get_recent_user_events(
        self, request: GetRecentUserEventsRequest
    ) -> GetRecentUserEventsResponse:
        return await self._send(
            AdapterCapability.GET_RECENT_USER_EVENTS, request, GetRecentUserEventsResponse
        )

    async def search_allowed_records(
        self, request: SearchAllowedRecordsRequest
    ) -> SearchAllowedRecordsResponse:
        return await self._send(
            AdapterCapability.SEARCH_ALLOWED_RECORDS, request, SearchAllowedRecordsResponse
        )

    async def execute_approved_action(
        self, request: ExecuteApprovedActionRequest
    ) -> ExecuteApprovedActionResponse:
        response = await self._send(
            AdapterCapability.EXECUTE_APPROVED_ACTION, request, ExecuteApprovedActionResponse
        )
        receipt = response.receipt
        if (
            receipt.adapter_id != self.metadata.adapter_id
            or receipt.action_id != request.action_definition.action_id
            or receipt.action_version != request.action_definition.action_version
            or receipt.target != request.proposal.target
            or receipt.idempotency_key != request.idempotency_key
        ):
            raise self._malformed_response(request)
        return response

    async def log_feedback(self, request: LogFeedbackRequest) -> LogFeedbackResponse:
        return await self._send(AdapterCapability.LOG_FEEDBACK, request, LogFeedbackResponse)

    async def _send(
        self,
        operation: AdapterCapability,
        request: AdapterRequest,
        response_type: type[_ResponseT],
    ) -> _ResponseT:
        endpoint_url = self._config.endpoint_url
        assert endpoint_url is not None
        request_payload = request.model_dump(mode="json")
        envelope = AppsScriptRequestEnvelope(
            operation=operation,
            request_id=request.request_id,
            app_id=request.app_id,
            payload=request_payload,
        )
        key_id = self._config.key_id
        shared_secret = self._config.shared_secret
        assert key_id is not None
        assert shared_secret is not None
        signed_envelope = create_signed_envelope(
            envelope.model_dump(mode="json"),
            version=self._config.version,
            key_id=key_id,
            shared_secret=shared_secret,
        )
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-OrkaFin-Request-ID": request.request_id.root,
            "X-OrkaFin-Wire-Schema": APPS_SCRIPT_WIRE_SCHEMA_VERSION,
            "X-OrkaFin-Adapter-Contract": ADAPTER_CONTRACT_VERSION,
        }
        _logger.info(
            "apps_script_adapter_request",
            extra={
                "request_id": request.request_id.root,
                "app_id": request.app_id,
                "adapter_operation": operation.value,
            },
        )
        try:
            transport_response = await self._transport.post(
                url=endpoint_url,
                body=json.dumps(
                    signed_envelope,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8"),
                headers=headers,
                timeout_seconds=self._config.timeout_seconds,
            )
        except (HttpTransportTimeoutError, TimeoutError) as error:
            raise AdapterTimeoutError(
                request_id=request.request_id,
                app_id=request.app_id,
            ) from error
        except HttpTransportError as error:
            raise AdapterUnavailableError(
                request_id=request.request_id,
                app_id=request.app_id,
            ) from error
        except AdapterError:
            raise
        except Exception as error:
            raise AdapterUnavailableError(
                request_id=request.request_id,
                app_id=request.app_id,
            ) from error

        _logger.info(
            "apps_script_adapter_response",
            extra={
                "request_id": request.request_id.root,
                "app_id": request.app_id,
                "adapter_operation": operation.value,
                "http_status": transport_response.status_code,
            },
        )
        return self._parse_response(
            transport_response,
            operation=operation,
            request=request,
            response_type=response_type,
        )

    def _parse_response(
        self,
        transport_response: HttpTransportResponse,
        *,
        operation: AdapterCapability,
        request: AdapterRequest,
        response_type: type[_ResponseT],
    ) -> _ResponseT:
        body = transport_response.body
        if len(body) > self._config.max_response_bytes:
            raise AdapterInternalFailureError(
                request_id=request.request_id,
                app_id=request.app_id,
                safe_message="The owning application returned an invalid response.",
            )

        try:
            decoded = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            if transport_response.status_code >= 400:
                raise self._error_from_status(transport_response.status_code, request) from error
            raise self._malformed_response(request) from error
        if not isinstance(decoded, dict):
            raise self._malformed_response(request)

        self._validate_wire_bindings(decoded, operation=operation, request=request)
        outcome = decoded.get("outcome")
        if outcome == "failure":
            try:
                failure_envelope = AppsScriptFailureEnvelope.model_validate_json(body)
            except ValidationError as error:
                raise self._malformed_response(request) from error
            raise adapter_error_from_failure(failure_envelope.failure)

        if transport_response.status_code >= 400:
            raise self._error_from_status(transport_response.status_code, request)
        if outcome != "success":
            raise self._malformed_response(request)

        try:
            success_envelope = AppsScriptSuccessEnvelope.model_validate_json(body)
        except ValidationError as error:
            raise self._malformed_response(request) from error
        self._validate_payload_versions(success_envelope.payload, request=request)
        try:
            typed_response = response_type.model_validate_json(
                json.dumps(success_envelope.payload, separators=(",", ":"))
            )
        except ValidationError as error:
            raise self._malformed_response(request) from error
        if (
            typed_response.request_id != request.request_id
            or typed_response.app_id != request.app_id
            or typed_response.adapter_response_id != success_envelope.adapter_response_id
            or typed_response.responded_at != success_envelope.responded_at
        ):
            raise self._malformed_response(request)
        return typed_response

    @staticmethod
    def _validate_wire_bindings(
        decoded: Mapping[str, object],
        *,
        operation: AdapterCapability,
        request: AdapterRequest,
    ) -> None:
        required_fields = {
            "schema_version",
            "adapter_contract_version",
            "operation",
            "request_id",
            "app_id",
        }
        if not required_fields.issubset(decoded):
            raise AppsScriptOrkaATSAdapter._malformed_response(request)
        if decoded.get("schema_version") != APPS_SCRIPT_WIRE_SCHEMA_VERSION:
            raise AdapterConflictError(
                request_id=request.request_id,
                app_id=request.app_id,
                safe_message="The Apps Script wire schema version is incompatible.",
            )
        if decoded.get("adapter_contract_version") != ADAPTER_CONTRACT_VERSION:
            raise AdapterConflictError(
                request_id=request.request_id,
                app_id=request.app_id,
                safe_message="The Apps Script adapter contract version is incompatible.",
            )
        if (
            decoded.get("operation") != operation.value
            or decoded.get("request_id") != request.request_id.root
            or decoded.get("app_id") != request.app_id
        ):
            raise AppsScriptOrkaATSAdapter._malformed_response(request)

    @staticmethod
    def _validate_payload_versions(
        payload: Mapping[str, JsonValue], *, request: AdapterRequest
    ) -> None:
        if payload.get("schema_version") != APPS_SCRIPT_WIRE_SCHEMA_VERSION:
            raise AdapterConflictError(
                request_id=request.request_id,
                app_id=request.app_id,
                safe_message="The Apps Script payload schema version is incompatible.",
            )
        if payload.get("adapter_contract_version") != ADAPTER_CONTRACT_VERSION:
            raise AdapterConflictError(
                request_id=request.request_id,
                app_id=request.app_id,
                safe_message="The Apps Script payload contract version is incompatible.",
            )

    @staticmethod
    def _malformed_response(request: AdapterRequest) -> AdapterInternalFailureError:
        return AdapterInternalFailureError(
            request_id=request.request_id,
            app_id=request.app_id,
            safe_message="The owning application returned an invalid response.",
        )

    @staticmethod
    def _error_from_status(status_code: int, request: AdapterRequest) -> AdapterError:
        error_type: type[AdapterError]
        if status_code == 401:
            error_type = AdapterUnauthorizedError
        elif status_code == 403:
            error_type = AdapterForbiddenError
        elif status_code == 404:
            error_type = AdapterNotFoundError
        elif status_code in {408, 504}:
            error_type = AdapterTimeoutError
        elif status_code == 409:
            error_type = AdapterConflictError
        elif status_code in {400, 422}:
            error_type = AdapterValidationFailedError
        elif status_code in {429, 502, 503}:
            error_type = AdapterUnavailableError
        else:
            error_type = AdapterInternalFailureError
        return error_type(request_id=request.request_id, app_id=request.app_id)


# Prompt 8 terminology; preserve the established repository class name as well.
AppsScriptAdapter = AppsScriptOrkaATSAdapter
