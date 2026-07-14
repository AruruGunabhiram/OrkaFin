"""Deterministic, fixture-owned local implementation of the OrkaATS contract.

Only this module reads the synthetic candidate fixtures.  It deliberately exposes
the general adapter response models rather than a candidate ORM or raw fixture
objects, so an OrkaFin service cannot retrieve an unrestricted candidate record.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]

from orkafin.adapters import (
    ADAPTER_CONTRACT_VERSION,
    AdapterCapability,
    AdapterCapabilityMetadata,
    AdapterErrorCode,
    AdapterFailure,
    AdapterMetadata,
    AdapterNotFoundError,
    AdapterUnauthorizedError,
    AdapterUnsupportedCapabilityError,
    AdapterValidationFailedError,
    AllowedRecordSearchResult,
    ApplicationPageMetadata,
    ApplicationUserEvent,
    EntityBooleanValue,
    EntityDateValue,
    EntityFieldSensitivity,
    EntityIntegerValue,
    EntityNumberValue,
    EntityReferenceValue,
    EntityTextValue,
    EntityTimestampValue,
    EntityVisibilitySummary,
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
    SelectedEntitySummary,
    VisibleEntityField,
    adapter_error_from_failure,
)
from orkafin.application.permissions import (
    AuthorizationSource,
    RecordVisibilityGrant,
    TrustedAuthorizationFacts,
)
from orkafin.domain.context import (
    AppMetadata,
    AppStatus,
    IdentityVerificationStatus,
    Role,
    SelectedEntityRef,
    UserIdentity,
    WorkspaceRef,
)
from orkafin.domain.identifiers import SafeReference
from orkafin.domain.metadata import BoundedMetadata

MOCK_ORKA_ATS_APP_ID = "orka_ats"
MOCK_ORKA_ATS_ADAPTER_ID = "mock_orka_ats"
_FIXTURE_TIME = datetime(2026, 7, 13, 20, 0, tzinfo=UTC)
_CONTEXT_TTL_SECONDS = 300


@dataclass(frozen=True, slots=True)
class MockFailureSimulation:
    """Deterministic test-only fault and latency controls for one adapter instance."""

    failures: Mapping[AdapterCapability | str, AdapterErrorCode] | None = None
    latency_seconds: float = 0.0

    def code_for(self, capability: AdapterCapability) -> AdapterErrorCode | None:
        if self.failures is None:
            return None
        return self.failures.get(capability, self.failures.get(capability.value))


class MockOrkaATSAdapter:
    """Synthetic OrkaATS owner that enforces all candidate visibility internally."""

    def __init__(
        self,
        *,
        fixture_root: Path | str | None = None,
        simulation: MockFailureSimulation | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._fixture_root = (
            Path(fixture_root) if fixture_root is not None else _default_fixture_root()
        )
        self._simulation = simulation or MockFailureSimulation()
        if self._simulation.latency_seconds < 0:
            raise ValueError("mock adapter latency_seconds must not be negative")
        self._clock = clock or (lambda: _FIXTURE_TIME)
        self._fixtures = _load_fixture_bundle(self._fixture_root)
        self._metadata = AdapterMetadata(
            adapter_id=MOCK_ORKA_ATS_ADAPTER_ID,
            owning_app_id=MOCK_ORKA_ATS_APP_ID,
            adapter_version="1.0.0",
            capabilities=tuple(
                AdapterCapabilityMetadata(capability=capability, capability_version="1.0.0")
                for capability in (
                    AdapterCapability.GET_APP_METADATA,
                    AdapterCapability.RESOLVE_CURRENT_USER,
                    AdapterCapability.RESOLVE_CONTEXT,
                    AdapterCapability.GET_USER_PERMISSIONS,
                    AdapterCapability.GET_PAGE_METADATA,
                    AdapterCapability.GET_SELECTED_ENTITY_SUMMARY,
                    AdapterCapability.GET_AVAILABLE_FEATURES,
                    AdapterCapability.GET_AVAILABLE_ACTIONS,
                    AdapterCapability.GET_RECENT_USER_EVENTS,
                    AdapterCapability.SEARCH_ALLOWED_RECORDS,
                )
            ),
        )

    @property
    def metadata(self) -> AdapterMetadata:
        return self._metadata

    async def get_app_metadata(self, request: GetAppMetadataRequest) -> GetAppMetadataResponse:
        await self._before(AdapterCapability.GET_APP_METADATA, request)
        return GetAppMetadataResponse(
            **self._envelope(request, AdapterCapability.GET_APP_METADATA),
            app_metadata=self._app_metadata(),
        )

    async def resolve_current_user(
        self, request: ResolveCurrentUserRequest
    ) -> ResolveCurrentUserResponse:
        await self._before(AdapterCapability.RESOLVE_CURRENT_USER, request)
        user = self._user_for_subject(request.trusted_subject_reference)
        identity = (
            self._identity_for_user(user)
            if user is not None
            else UserIdentity(verification_status=IdentityVerificationStatus.UNVERIFIED)
        )
        return ResolveCurrentUserResponse(
            **self._envelope(request, AdapterCapability.RESOLVE_CURRENT_USER), identity=identity
        )

    async def resolve_context(self, request: ResolveContextRequest) -> ResolveContextResponse:
        await self._before(AdapterCapability.RESOLVE_CONTEXT, request)
        user = self._verified_user(request.trusted_identity)
        hint = request.client_hint
        workspace = self._workspace_for_user(user)
        page_id = hint.page
        if page_id not in self._fixtures["pages"]:
            raise AdapterNotFoundError(request_id=request.request_id, app_id=request.app_id)
        selected = self._selected_hint(hint.selected_entity, workspace.workspace_id)
        now = self._now()
        context = ResolvedApplicationContext(
            app=self._app_metadata(),
            identity=request.trusted_identity,
            page_id=page_id,
            workspace=workspace,
            selected_entity=selected,
            resolved_at=now,
            valid_until=now + timedelta(seconds=_CONTEXT_TTL_SECONDS),
        )
        return ResolveContextResponse(
            **self._envelope(request, AdapterCapability.RESOLVE_CONTEXT), context=context
        )

    async def get_user_permissions(
        self, request: GetUserPermissionsRequest
    ) -> GetUserPermissionsResponse:
        await self._before(AdapterCapability.GET_USER_PERMISSIONS, request)
        user = self._authorized_context(request, require_page_access=False)
        records = tuple(
            RecordVisibilityGrant(
                record=SelectedEntityRef(
                    app_id=MOCK_ORKA_ATS_APP_ID, entity_type="candidate", entity_id=candidate_id
                ),
                visible_field_ids=tuple(field_ids),
            )
            for candidate_id, field_ids in user["record_grants"].items()
            if self._candidate_is_available(candidate_id, request.context.workspace.workspace_id)
        )
        response_id = self._response_id(request, AdapterCapability.GET_USER_PERMISSIONS)
        facts = TrustedAuthorizationFacts(
            source=AuthorizationSource.APPLICATION_ADAPTER,
            adapter_response_id=response_id,
            app_id=MOCK_ORKA_ATS_APP_ID,
            app_access=True,
            allowed_page_ids=tuple(user["allowed_page_ids"]),
            permissions=tuple(user["permissions"]),
            records=records,
            available_action_ids=tuple(self._available_action_ids(user, request.context)),
        )
        return GetUserPermissionsResponse(
            **self._envelope(
                request, AdapterCapability.GET_USER_PERMISSIONS, adapter_response_id=response_id
            ),
            authorization_facts=facts,
        )

    async def get_page_metadata(self, request: GetPageMetadataRequest) -> GetPageMetadataResponse:
        await self._before(AdapterCapability.GET_PAGE_METADATA, request)
        self._authorized_context(request)
        page = self._fixtures["pages"][request.context.page_id]
        metadata = ApplicationPageMetadata(
            app_id=MOCK_ORKA_ATS_APP_ID,
            page_id=request.context.page_id,
            page_version=page["page_version"],
            title=page["title"],
            purpose=page["purpose"],
            feature_ids=tuple(page["feature_ids"]),
            safe_reference=SafeReference(root=page["safe_reference"]),
        )
        return GetPageMetadataResponse(
            **self._envelope(request, AdapterCapability.GET_PAGE_METADATA), page_metadata=metadata
        )

    async def get_selected_entity_summary(
        self, request: GetSelectedEntitySummaryRequest
    ) -> GetSelectedEntitySummaryResponse:
        await self._before(AdapterCapability.GET_SELECTED_ENTITY_SUMMARY, request)
        user = self._authorized_context(request)
        entity = request.context.selected_entity
        assert entity is not None
        candidate = self._visible_candidate(
            user, entity, request.context.workspace.workspace_id, request
        )
        requested = tuple(request.requested_field_ids)
        allowed_ids = tuple(user["record_grants"][entity.entity_id])
        returned_ids = requested if requested else allowed_ids
        visible_ids = tuple(field_id for field_id in returned_ids if field_id in allowed_ids)
        fields = tuple(self._visible_field(candidate, field_id) for field_id in visible_ids)
        redacted = sum(
            1 for field_id in requested if field_id != "notes" and field_id not in allowed_ids
        )
        visibility = EntityVisibilitySummary(
            visible_field_count=len(fields),
            redacted_field_count=redacted,
            redaction_applied=redacted > 0,
            explanation_code=(
                "field_permissions_applied"
                if redacted
                else "all_requested_fields_visible"
                if requested
                else "minimum_summary_only"
            ),
        )
        response_id = self._response_id(request, AdapterCapability.GET_SELECTED_ENTITY_SUMMARY)
        summary = SelectedEntitySummary(
            entity=entity,
            display_label=(
                candidate["display_label"] if "display_name" in allowed_ids else "Candidate record"
            ),
            visible_fields=fields,
            visibility=visibility,
            source_adapter_response_id=response_id,
            valid_for_request_id=request.request_id,
            retrieved_at=self._now(),
        )
        return GetSelectedEntitySummaryResponse(
            **self._envelope(
                request,
                AdapterCapability.GET_SELECTED_ENTITY_SUMMARY,
                adapter_response_id=response_id,
            ),
            summary=summary,
        )

    async def get_available_features(
        self, request: GetAvailableFeaturesRequest
    ) -> GetAvailableFeaturesResponse:
        await self._before(AdapterCapability.GET_AVAILABLE_FEATURES, request)
        user = self._authorized_context(request)
        page = self._fixtures["pages"][request.context.page_id]
        features = tuple(
            feature for feature in page["feature_ids"] if feature in user["available_features"]
        )
        return GetAvailableFeaturesResponse(
            **self._envelope(request, AdapterCapability.GET_AVAILABLE_FEATURES),
            feature_ids=features,
        )

    async def get_available_actions(
        self, request: GetAvailableActionsRequest
    ) -> GetAvailableActionsResponse:
        await self._before(AdapterCapability.GET_AVAILABLE_ACTIONS, request)
        user = self._authorized_context(request)
        return GetAvailableActionsResponse(
            **self._envelope(request, AdapterCapability.GET_AVAILABLE_ACTIONS),
            action_ids=tuple(self._available_action_ids(user, request.context)),
        )

    async def get_recent_user_events(
        self, request: GetRecentUserEventsRequest
    ) -> GetRecentUserEventsResponse:
        await self._before(AdapterCapability.GET_RECENT_USER_EVENTS, request)
        user = self._authorized_context(request)
        events: list[ApplicationUserEvent] = []
        for raw in self._fixtures["events"]:
            if raw["actor_fixture_id"] != user["fixture_id"]:
                continue
            occurred_at = _parse_timestamp(raw["occurred_at"])
            if request.occurred_after is not None and occurred_at <= request.occurred_after:
                continue
            entity = self._event_entity(raw, user, request.context.workspace.workspace_id)
            events.append(
                ApplicationUserEvent(
                    event_id=raw["event_id"],
                    event_type=raw["event_type"],
                    app_id=MOCK_ORKA_ATS_APP_ID,
                    actor_user_id=user["user_id"],
                    workspace=request.context.workspace,
                    entity_ref=entity,
                    metadata=BoundedMetadata(root=raw["metadata"]),
                    occurred_at=occurred_at,
                )
            )
        events.sort(key=lambda event: event.occurred_at, reverse=True)
        return GetRecentUserEventsResponse(
            **self._envelope(request, AdapterCapability.GET_RECENT_USER_EVENTS),
            events=tuple(events[: request.limit]),
        )

    async def search_allowed_records(
        self, request: SearchAllowedRecordsRequest
    ) -> SearchAllowedRecordsResponse:
        await self._before(AdapterCapability.SEARCH_ALLOWED_RECORDS, request)
        user = self._authorized_context(request)
        if request.entity_types and "candidate" not in request.entity_types:
            return SearchAllowedRecordsResponse(
                **self._envelope(request, AdapterCapability.SEARCH_ALLOWED_RECORDS), results=()
            )
        query = request.query.casefold()
        results: list[AllowedRecordSearchResult] = []
        for candidate_id in sorted(user["record_grants"]):
            if not self._candidate_is_available(
                candidate_id, request.context.workspace.workspace_id
            ):
                continue
            candidate = self._fixtures["candidates"].get(candidate_id)
            if candidate is None:
                continue
            allowed_ids = tuple(user["record_grants"][candidate_id])
            searchable = [candidate["display_label"], candidate_id]
            searchable.extend(
                str(candidate["fields"][field_id]["value"])
                for field_id in allowed_ids
                if field_id in candidate["fields"]
            )
            if not any(query in value.casefold() for value in searchable):
                continue
            result_fields = tuple(
                self._visible_field(candidate, field_id)
                for field_id in request.requested_field_ids
                if field_id in allowed_ids
            )
            results.append(
                AllowedRecordSearchResult(
                    entity=SelectedEntityRef(
                        app_id=MOCK_ORKA_ATS_APP_ID,
                        entity_type="candidate",
                        entity_id=candidate_id,
                    ),
                    display_label=candidate["display_label"],
                    visible_fields=result_fields,
                )
            )
        return SearchAllowedRecordsResponse(
            **self._envelope(request, AdapterCapability.SEARCH_ALLOWED_RECORDS),
            results=tuple(results[: min(request.limit, 10)]),
        )

    async def execute_approved_action(
        self, request: ExecuteApprovedActionRequest
    ) -> ExecuteApprovedActionResponse:
        await self._before(AdapterCapability.EXECUTE_APPROVED_ACTION, request)
        raise AdapterUnsupportedCapabilityError(
            request_id=request.request_id, app_id=request.app_id
        )

    async def log_feedback(self, request: LogFeedbackRequest) -> LogFeedbackResponse:
        await self._before(AdapterCapability.LOG_FEEDBACK, request)
        raise AdapterUnsupportedCapabilityError(
            request_id=request.request_id, app_id=request.app_id
        )

    async def _before(self, capability: AdapterCapability, request: Any) -> None:
        self._validate_app(request.app_id, request.request_id)
        if self._simulation.latency_seconds:
            await asyncio.sleep(self._simulation.latency_seconds)
        code = self._simulation.code_for(capability)
        if code is not None:
            failure = AdapterFailure(
                request_id=request.request_id,
                app_id=request.app_id,
                adapter_response_id=self._response_id(request, capability),
                code=code,
                safe_message="The mock OrkaATS adapter simulated a safe failure.",
                retryable=code in {AdapterErrorCode.UNAVAILABLE, AdapterErrorCode.TIMEOUT},
                failure_reference=f"mock-failure-{capability.value}",
                failed_at=self._now(),
            )
            raise adapter_error_from_failure(failure)

    def _validate_app(self, app_id: str, request_id: Any) -> None:
        if app_id != MOCK_ORKA_ATS_APP_ID:
            raise AdapterValidationFailedError(request_id=request_id, app_id=app_id)

    def _app_metadata(self) -> AppMetadata:
        app = self._fixtures["app"]
        return AppMetadata(
            app_id=MOCK_ORKA_ATS_APP_ID,
            display_name=app["display_name"],
            description=app["description"],
            app_version=app["app_version"],
            adapter_contract_version=ADAPTER_CONTRACT_VERSION,
            status=AppStatus(app["status"]),
        )

    def _identity_for_user(self, user: dict[str, Any]) -> UserIdentity:
        return UserIdentity(
            user_id=user["user_id"],
            display_name=user["display_name"],
            email=user["email"],
            role=Role(
                role_id=user["role_id"],
                display_name=user["role_display_name"],
                owner_app_id=MOCK_ORKA_ATS_APP_ID,
            ),
            verification_status=IdentityVerificationStatus.ADAPTER_VERIFIED,
            verified_at=self._now(),
            verification_reference=f"mock-orka-ats:{user['fixture_id']}",
        )

    def _user_for_subject(self, subject: str | None) -> dict[str, Any] | None:
        if subject is None:
            return None
        user = self._fixtures["users"].get(subject)
        return cast(dict[str, Any] | None, user) if user and "user_id" in user else None

    def _verified_user(self, identity: UserIdentity) -> dict[str, Any]:
        if identity.verification_status is not IdentityVerificationStatus.ADAPTER_VERIFIED:
            raise AdapterUnauthorizedError()
        user = next(
            (
                candidate
                for candidate in self._fixtures["users"].values()
                if candidate["user_id"] == identity.user_id
            ),
            None,
        )
        if user is None or identity != self._identity_for_user(user):
            raise AdapterUnauthorizedError()
        return cast(dict[str, Any], user)

    def _authorized_context(
        self, request: Any, *, require_page_access: bool = True
    ) -> dict[str, Any]:
        user = self._verified_user(request.trusted_identity)
        context = request.context
        if (
            context.app.app_id != MOCK_ORKA_ATS_APP_ID
            or context.identity != request.trusted_identity
        ):
            raise AdapterUnauthorizedError(request_id=request.request_id, app_id=request.app_id)
        if context.workspace != self._workspace_for_user(user):
            raise AdapterUnauthorizedError(request_id=request.request_id, app_id=request.app_id)
        if require_page_access and context.page_id not in user["allowed_page_ids"]:
            raise AdapterNotFoundError(request_id=request.request_id, app_id=request.app_id)
        return user

    def _workspace_for_user(self, user: dict[str, Any]) -> WorkspaceRef:
        workspace = self._fixtures["workspaces"][user["workspace_id"]]
        return WorkspaceRef(
            workspace_id=user["workspace_id"],
            app_id=MOCK_ORKA_ATS_APP_ID,
            display_name=workspace["display_name"],
        )

    def _selected_hint(self, hint: Any, workspace_id: str) -> SelectedEntityRef | None:
        if hint is None:
            return None
        if hint.type != "candidate":
            raise AdapterValidationFailedError()
        candidate = self._fixtures["candidates"].get(hint.id)
        if candidate is None or candidate["workspace_id"] != workspace_id:
            return None
        return SelectedEntityRef(
            app_id=MOCK_ORKA_ATS_APP_ID, entity_type="candidate", entity_id=hint.id
        )

    def _visible_candidate(
        self, user: dict[str, Any], entity: SelectedEntityRef, workspace_id: str, request: Any
    ) -> dict[str, Any]:
        candidate = self._fixtures["candidates"].get(entity.entity_id)
        if (
            entity.entity_type != "candidate"
            or candidate is None
            or candidate["workspace_id"] != workspace_id
            or not self._candidate_is_available(entity.entity_id, workspace_id)
            or "candidate.view" not in user["permissions"]
            or entity.entity_id not in user["record_grants"]
        ):
            raise AdapterNotFoundError(request_id=request.request_id, app_id=request.app_id)
        return cast(dict[str, Any], candidate)

    def _candidate_is_available(self, candidate_id: str, workspace_id: str) -> bool:
        candidate = self._fixtures["candidates"].get(candidate_id)
        return bool(
            candidate
            and candidate["workspace_id"] == workspace_id
            and candidate["visibility"] == "allowed"
            and not candidate["archived"]
        )

    def _visible_field(self, candidate: dict[str, Any], field_id: str) -> VisibleEntityField:
        raw = candidate["fields"][field_id]
        kind = raw["kind"]
        value: Any = raw["value"]
        typed_value: Any
        if kind == "text":
            typed_value = EntityTextValue(value=value)
        elif kind == "date":
            typed_value = EntityDateValue(value=datetime.fromisoformat(value).date())
        elif kind == "timestamp":
            typed_value = EntityTimestampValue(value=_parse_timestamp(value))
        elif kind == "integer":
            typed_value = EntityIntegerValue(value=value)
        elif kind == "number":
            typed_value = EntityNumberValue(value=value)
        elif kind == "boolean":
            typed_value = EntityBooleanValue(value=value)
        elif kind == "reference":
            typed_value = EntityReferenceValue(value=SafeReference(root=value))
        else:
            raise AdapterValidationFailedError(
                safe_message="Mock fixture contains an invalid field."
            )
        return VisibleEntityField(
            field_id=field_id,
            label=raw["label"],
            sensitivity=EntityFieldSensitivity(raw["sensitivity"]),
            value=typed_value,
        )

    def _available_action_ids(
        self, user: dict[str, Any], context: ResolvedApplicationContext
    ) -> tuple[str, ...]:
        if context.selected_entity is None:
            return ()
        return tuple(
            action_id
            for action_id in user["available_action_ids"]
            if action_id in self._fixtures["enabled_action_ids"]
            and context.selected_entity.entity_id in user["record_grants"]
        )

    def _event_entity(
        self, raw: dict[str, Any], user: dict[str, Any], workspace_id: str
    ) -> SelectedEntityRef | None:
        candidate_id = raw.get("candidate_id")
        if candidate_id is None or candidate_id not in user["record_grants"]:
            return None
        if not self._candidate_is_available(candidate_id, workspace_id):
            return None
        return SelectedEntityRef(
            app_id=MOCK_ORKA_ATS_APP_ID, entity_type="candidate", entity_id=candidate_id
        )

    def _envelope(
        self, request: Any, capability: AdapterCapability, *, adapter_response_id: str | None = None
    ) -> dict[str, Any]:
        return {
            "request_id": request.request_id,
            "app_id": MOCK_ORKA_ATS_APP_ID,
            "adapter_response_id": adapter_response_id or self._response_id(request, capability),
            "responded_at": self._now(),
        }

    @staticmethod
    def _response_id(request: Any, capability: AdapterCapability) -> str:
        return f"mock-{capability.value}-{request.request_id.root[-8:]}"

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("mock adapter clock must return a UTC datetime")
        return value


def _default_fixture_root() -> Path:
    return Path(__file__).resolve().parents[4] / "fixtures" / "orka_ats"


def _load_fixture_bundle(root: Path) -> dict[str, Any]:
    files = ("app.yaml", "users.yaml", "candidates.yaml", "events.yaml")
    loaded = {name.removesuffix(".yaml"): _load_yaml(root / name) for name in files}
    app = loaded["app"]
    users = {item["fixture_id"]: item for item in loaded["users"]["users"]}
    candidates = {item["candidate_id"]: item for item in loaded["candidates"]["candidates"]}
    pages = {item["page_id"]: item for item in app["pages"]}
    workspaces = {item["workspace_id"]: item for item in app["workspaces"]}
    if not users or not candidates or not pages or not workspaces:
        raise ValueError(
            "mock OrkaATS fixtures must define users, candidates, pages, and workspaces"
        )
    return {
        "app": app,
        "users": users,
        "candidates": candidates,
        "events": loaded["events"]["events"],
        "pages": pages,
        "workspaces": workspaces,
        "enabled_action_ids": tuple(app.get("enabled_action_ids", ())),
    }


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError(f"mock OrkaATS fixture is unavailable: {path.name}") from error
    except yaml.YAMLError as error:
        raise ValueError(f"mock OrkaATS fixture is invalid: {path.name}") from error
    if not isinstance(parsed, dict):
        raise ValueError(f"mock OrkaATS fixture must be a mapping: {path.name}")
    return parsed


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
