"""Versioned, application-neutral Orka application adapter contract."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, ClassVar, Literal, Protocol, runtime_checkable

from pydantic import Field, StringConstraints, field_validator, model_validator

from orkafin.application.permissions.models import (
    AuthorizationSource,
    TrustedAuthorizationFacts,
)
from orkafin.domain.actions import (
    ActionConfirmation,
    ActionConfirmationStatus,
    ActionDefinition,
    ActionProposal,
    ActionProposalStatus,
    AdapterExecutionReceipt,
)
from orkafin.domain.base import (
    DataClassification,
    DataOwner,
    DomainModel,
    HandlingRule,
    Identifier,
    LowercaseIdentifier,
    ModelDataPolicy,
    PersistencePolicy,
    SemanticVersion,
    SensitiveFieldPolicy,
    ShortText,
    UtcDatetime,
)
from orkafin.domain.catalog import CatalogStatus
from orkafin.domain.context import (
    AppMetadata,
    ClientContextHint,
    IdentityVerificationStatus,
    SelectedEntityRef,
    UserIdentity,
    WorkspaceRef,
)
from orkafin.domain.identifiers import IdempotencyKey, RequestId, SafeReference
from orkafin.domain.metadata import BoundedMetadata
from orkafin.domain.recommendations import RecommendationFeedback

AdapterContractVersion = Literal["1.0.0"]
ADAPTER_CONTRACT_VERSION: AdapterContractVersion = "1.0.0"

SearchText = Annotated[
    str,
    StringConstraints(min_length=1, max_length=500, strip_whitespace=True, strict=True),
]

_REQUEST_POLICY = ModelDataPolicy(
    owner=DataOwner.ORKAFIN,
    classification=DataClassification.RESTRICTED,
    persistence=PersistencePolicy.NEVER,
)
_RESPONSE_POLICY = ModelDataPolicy(
    owner=DataOwner.OWNING_APPLICATION,
    classification=DataClassification.RESTRICTED,
    persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
)


class AdapterCapability(StrEnum):
    """Independently versioned operations exposed by an application adapter."""

    GET_APP_METADATA = "get_app_metadata"
    RESOLVE_CURRENT_USER = "resolve_current_user"
    RESOLVE_CONTEXT = "resolve_context"
    GET_USER_PERMISSIONS = "get_user_permissions"
    GET_PAGE_METADATA = "get_page_metadata"
    GET_SELECTED_ENTITY_SUMMARY = "get_selected_entity_summary"
    GET_AVAILABLE_FEATURES = "get_available_features"
    GET_AVAILABLE_ACTIONS = "get_available_actions"
    GET_RECENT_USER_EVENTS = "get_recent_user_events"
    SEARCH_ALLOWED_RECORDS = "search_allowed_records"
    EXECUTE_APPROVED_ACTION = "execute_approved_action"
    LOG_FEEDBACK = "log_feedback"


REQUIRED_ADAPTER_CAPABILITIES: frozenset[AdapterCapability] = frozenset(
    {
        AdapterCapability.GET_APP_METADATA,
        AdapterCapability.RESOLVE_CURRENT_USER,
        AdapterCapability.RESOLVE_CONTEXT,
        AdapterCapability.GET_USER_PERMISSIONS,
        AdapterCapability.GET_PAGE_METADATA,
    }
)


class AdapterCapabilityMetadata(DomainModel):
    """Version declaration for one supported adapter operation."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.OWNING_APPLICATION,
        classification=DataClassification.INTERNAL,
        persistence=PersistencePolicy.VALUE_OBJECT,
    )

    capability: AdapterCapability
    capability_version: SemanticVersion


class AdapterMetadata(DomainModel):
    """Configured adapter identity, contract version, and supported capabilities."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.OWNING_APPLICATION,
        classification=DataClassification.INTERNAL,
        persistence=PersistencePolicy.VALUE_OBJECT,
    )

    adapter_id: LowercaseIdentifier
    owning_app_id: LowercaseIdentifier
    adapter_version: SemanticVersion
    adapter_contract_version: AdapterContractVersion = ADAPTER_CONTRACT_VERSION
    capabilities: tuple[AdapterCapabilityMetadata, ...] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def require_unique_capabilities(self) -> AdapterMetadata:
        capability_ids = [item.capability for item in self.capabilities]
        if len(capability_ids) != len(set(capability_ids)):
            raise ValueError("adapter capabilities must be unique")
        missing = REQUIRED_ADAPTER_CAPABILITIES.difference(capability_ids)
        if missing:
            raise ValueError("adapter metadata is missing required capabilities")
        return self

    def supports(self, capability: AdapterCapability) -> bool:
        """Return whether the adapter advertises one exact capability."""
        return any(item.capability is capability for item in self.capabilities)


class AdapterRequest(DomainModel):
    """Common request envelope propagated across every adapter operation."""

    data_policy: ClassVar[ModelDataPolicy] = _REQUEST_POLICY

    adapter_contract_version: AdapterContractVersion = ADAPTER_CONTRACT_VERSION
    request_id: RequestId
    app_id: LowercaseIdentifier


class AdapterResponse(DomainModel):
    """Common response envelope binding trusted data to one request and app."""

    data_policy: ClassVar[ModelDataPolicy] = _RESPONSE_POLICY

    adapter_contract_version: AdapterContractVersion = ADAPTER_CONTRACT_VERSION
    request_id: RequestId
    app_id: LowercaseIdentifier
    adapter_response_id: Identifier
    responded_at: UtcDatetime


class TrustedAdapterRequest(AdapterRequest):
    """Request carrying identity already verified by a trusted resolver or adapter."""

    trusted_identity: UserIdentity

    @model_validator(mode="after")
    def require_verified_identity(self) -> TrustedAdapterRequest:
        identity = self.trusted_identity
        if identity.verification_status is IdentityVerificationStatus.UNVERIFIED:
            raise ValueError("trusted adapter request requires a verified identity")
        if identity.role is None or identity.role.owner_app_id != self.app_id:
            raise ValueError("trusted identity must belong to the requested app")
        return self


class ResolvedApplicationContext(DomainModel):
    """Application-neutral, adapter-verified page and selection context."""

    data_policy: ClassVar[ModelDataPolicy] = _RESPONSE_POLICY

    trust_label: Literal["trusted_application_context"] = "trusted_application_context"
    app: AppMetadata
    identity: UserIdentity
    page_id: LowercaseIdentifier
    workspace: WorkspaceRef
    selected_entity: SelectedEntityRef | None = None
    resolved_at: UtcDatetime
    valid_until: UtcDatetime

    @model_validator(mode="after")
    def validate_context_bindings(self) -> ResolvedApplicationContext:
        app_id = self.app.app_id
        if self.identity.verification_status is IdentityVerificationStatus.UNVERIFIED:
            raise ValueError("resolved application context requires verified identity")
        if self.identity.role is None or self.identity.role.owner_app_id != app_id:
            raise ValueError("context identity must belong to the resolved app")
        if self.workspace.app_id != app_id:
            raise ValueError("context workspace must belong to the resolved app")
        if self.selected_entity is not None and self.selected_entity.app_id != app_id:
            raise ValueError("selected entity must belong to the resolved app")
        if self.valid_until < self.resolved_at:
            raise ValueError("context valid_until must not precede resolved_at")
        return self


class ContextBoundAdapterRequest(TrustedAdapterRequest):
    """Sensitive request bound to the same verified identity and application context."""

    context: ResolvedApplicationContext

    @model_validator(mode="after")
    def validate_context_request_bindings(self) -> ContextBoundAdapterRequest:
        if self.context.app.app_id != self.app_id:
            raise ValueError("adapter request context must belong to the requested app")
        if self.context.identity != self.trusted_identity:
            raise ValueError("adapter request identity must match context identity")
        return self


class GetAppMetadataRequest(AdapterRequest):
    """Request public owning-application metadata."""


class GetAppMetadataResponse(AdapterResponse):
    """Return application metadata without exposing its backing store."""

    app_metadata: AppMetadata

    @model_validator(mode="after")
    def validate_app_metadata(self) -> GetAppMetadataResponse:
        if self.app_metadata.app_id != self.app_id:
            raise ValueError("application metadata must match response app")
        if self.app_metadata.adapter_contract_version != self.adapter_contract_version:
            raise ValueError("application metadata must declare the response contract version")
        return self


class ResolveCurrentUserRequest(AdapterRequest):
    """Resolve identity from a trusted server/transport reference, never browser claims."""

    trusted_subject_reference: Identifier | None = None
    client_hint: ClientContextHint | None = None


class ResolveCurrentUserResponse(AdapterResponse):
    """Return a verified identity or a claim-free unverified identity."""

    identity: UserIdentity


class ResolveContextRequest(TrustedAdapterRequest):
    """Resolve page, workspace, and selected entity from untrusted client hints."""

    client_hint: ClientContextHint

    @model_validator(mode="after")
    def require_routed_app_hint(self) -> ResolveContextRequest:
        if self.client_hint.app_id != self.app_id:
            raise ValueError("client app hint must match the routed adapter app")
        return self


class ResolveContextResponse(AdapterResponse):
    """Return trusted application-neutral context for the response lifetime."""

    context: ResolvedApplicationContext

    @model_validator(mode="after")
    def validate_resolved_context(self) -> ResolveContextResponse:
        if self.context.app.app_id != self.app_id:
            raise ValueError("resolved context must match response app")
        return self


class GetUserPermissionsRequest(ContextBoundAdapterRequest):
    """Request fresh explicit app/page/record/field/action authorization facts."""


class GetUserPermissionsResponse(AdapterResponse):
    """Return trusted facts suitable for the deny-by-default permission evaluator."""

    authorization_facts: TrustedAuthorizationFacts

    @model_validator(mode="after")
    def validate_authorization_facts(self) -> GetUserPermissionsResponse:
        facts = self.authorization_facts
        if facts.source is not AuthorizationSource.APPLICATION_ADAPTER:
            raise ValueError("adapter authorization response must identify the adapter source")
        if facts.app_id != self.app_id:
            raise ValueError("authorization facts must match response app")
        if facts.adapter_response_id != self.adapter_response_id:
            raise ValueError("authorization facts must match adapter response ID")
        return self


class ApplicationPageMetadata(DomainModel):
    """Bounded application-owned metadata for one page."""

    data_policy: ClassVar[ModelDataPolicy] = _RESPONSE_POLICY

    app_id: LowercaseIdentifier
    page_id: LowercaseIdentifier
    page_version: SemanticVersion
    title: ShortText
    purpose: ShortText
    feature_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=50)
    safe_reference: SafeReference

    @field_validator("feature_ids")
    @classmethod
    def require_unique_feature_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("page feature IDs must be unique")
        return values


class GetPageMetadataRequest(ContextBoundAdapterRequest):
    """Request metadata for the verified current page."""


class GetPageMetadataResponse(AdapterResponse):
    """Return bounded current-page metadata."""

    page_metadata: ApplicationPageMetadata

    @model_validator(mode="after")
    def validate_page_metadata(self) -> GetPageMetadataResponse:
        if self.page_metadata.app_id != self.app_id:
            raise ValueError("page metadata must match response app")
        return self


class EntityTextValue(DomainModel):
    """Bounded text value for an explicitly visible entity field."""

    data_policy: ClassVar[ModelDataPolicy] = _RESPONSE_POLICY

    kind: Literal["text"] = "text"
    value: ShortText


class EntityDateValue(DomainModel):
    """Calendar-date value for an explicitly visible entity field."""

    data_policy: ClassVar[ModelDataPolicy] = _RESPONSE_POLICY

    kind: Literal["date"] = "date"
    value: date


class EntityTimestampValue(DomainModel):
    """UTC timestamp value for an explicitly visible entity field."""

    data_policy: ClassVar[ModelDataPolicy] = _RESPONSE_POLICY

    kind: Literal["timestamp"] = "timestamp"
    value: UtcDatetime


class EntityIntegerValue(DomainModel):
    """Strict integer value for an explicitly visible entity field."""

    data_policy: ClassVar[ModelDataPolicy] = _RESPONSE_POLICY

    kind: Literal["integer"] = "integer"
    value: int


class EntityNumberValue(DomainModel):
    """Strict floating-point value for an explicitly visible entity field."""

    data_policy: ClassVar[ModelDataPolicy] = _RESPONSE_POLICY

    kind: Literal["number"] = "number"
    value: float


class EntityBooleanValue(DomainModel):
    """Strict boolean value for an explicitly visible entity field."""

    data_policy: ClassVar[ModelDataPolicy] = _RESPONSE_POLICY

    kind: Literal["boolean"] = "boolean"
    value: bool


class EntityReferenceValue(DomainModel):
    """Safe internal reference value that cannot carry credentials or query data."""

    data_policy: ClassVar[ModelDataPolicy] = _RESPONSE_POLICY

    kind: Literal["reference"] = "reference"
    value: SafeReference


EntityFieldValue = Annotated[
    EntityTextValue
    | EntityDateValue
    | EntityTimestampValue
    | EntityIntegerValue
    | EntityNumberValue
    | EntityBooleanValue
    | EntityReferenceValue,
    Field(discriminator="kind"),
]


class EntityFieldSensitivity(StrEnum):
    """Owning-application sensitivity label for one returned entity field."""

    STANDARD = "standard"
    SENSITIVE = "sensitive"
    RESTRICTED = "restricted"


class VisibleEntityField(DomainModel):
    """One field the owning application explicitly allowed for this response."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.OWNING_APPLICATION,
        classification=DataClassification.RESTRICTED,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
        sensitive_fields=(
            SensitiveFieldPolicy(
                field_name="value",
                classification=DataClassification.RESTRICTED,
                rules=(HandlingRule.MINIMIZE, HandlingRule.REDACT_FROM_LOGS),
            ),
        ),
    )

    field_id: Identifier
    label: ShortText
    sensitivity: EntityFieldSensitivity
    visibility: Literal["visible"] = "visible"
    value: EntityFieldValue


class EntityVisibilitySummary(DomainModel):
    """Safe redaction counts that never enumerate hidden fields."""

    data_policy: ClassVar[ModelDataPolicy] = _RESPONSE_POLICY

    visible_field_count: int = Field(ge=0, le=100)
    redacted_field_count: int = Field(ge=0, le=100)
    redaction_applied: bool
    explanation_code: Literal[
        "all_requested_fields_visible",
        "field_permissions_applied",
        "minimum_summary_only",
    ]

    @model_validator(mode="after")
    def validate_redaction_flag(self) -> EntityVisibilitySummary:
        if self.redaction_applied != (self.redacted_field_count > 0):
            raise ValueError("redaction_applied must match the redacted field count")
        return self


class SelectedEntitySummary(DomainModel):
    """Permission-filtered application-neutral view of one selected entity."""

    data_policy: ClassVar[ModelDataPolicy] = _RESPONSE_POLICY

    entity: SelectedEntityRef
    display_label: ShortText | None = None
    visible_fields: tuple[VisibleEntityField, ...] = Field(default=(), max_length=100)
    visibility: EntityVisibilitySummary
    source_adapter_response_id: Identifier
    valid_for_request_id: RequestId
    retrieved_at: UtcDatetime

    @model_validator(mode="after")
    def validate_visible_fields(self) -> SelectedEntitySummary:
        if self.visibility.visible_field_count != len(self.visible_fields):
            raise ValueError("visible_field_count must match visible_fields")
        field_ids = [field.field_id for field in self.visible_fields]
        if len(field_ids) != len(set(field_ids)):
            raise ValueError("visible entity field IDs must be unique")
        return self


class GetSelectedEntitySummaryRequest(ContextBoundAdapterRequest):
    """Request only approved fields for the verified selected entity."""

    requested_field_ids: tuple[Identifier, ...] = Field(default=(), max_length=100)

    @model_validator(mode="after")
    def validate_summary_request(self) -> GetSelectedEntitySummaryRequest:
        if self.context.selected_entity is None:
            raise ValueError("selected entity summary requires a verified selected entity")
        if len(self.requested_field_ids) != len(set(self.requested_field_ids)):
            raise ValueError("requested field IDs must be unique")
        return self


class GetSelectedEntitySummaryResponse(AdapterResponse):
    """Return an already permission-filtered selected-entity summary."""

    summary: SelectedEntitySummary

    @model_validator(mode="after")
    def validate_summary_response(self) -> GetSelectedEntitySummaryResponse:
        if self.summary.entity.app_id != self.app_id:
            raise ValueError("selected entity summary must match response app")
        if self.summary.source_adapter_response_id != self.adapter_response_id:
            raise ValueError("selected entity summary must match adapter response ID")
        if self.summary.valid_for_request_id != self.request_id:
            raise ValueError("selected entity summary must match response request ID")
        return self


class GetAvailableFeaturesRequest(ContextBoundAdapterRequest):
    """Request feature IDs available in the verified context."""


class GetAvailableFeaturesResponse(AdapterResponse):
    """Return only owning-app-approved feature IDs."""

    feature_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=100)

    @field_validator("feature_ids")
    @classmethod
    def require_unique_feature_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("available feature IDs must be unique")
        return values


class GetAvailableActionsRequest(ContextBoundAdapterRequest):
    """Request action IDs currently available in the verified context."""


class GetAvailableActionsResponse(AdapterResponse):
    """Return availability only; action definitions remain catalog-owned."""

    action_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=50)

    @field_validator("action_ids")
    @classmethod
    def require_unique_action_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("available action IDs must be unique")
        return values


class ApplicationUserEvent(DomainModel):
    """Bounded meaningful event returned by the owning application."""

    data_policy: ClassVar[ModelDataPolicy] = _RESPONSE_POLICY

    event_id: Identifier
    event_type: LowercaseIdentifier
    app_id: LowercaseIdentifier
    actor_user_id: Identifier
    workspace: WorkspaceRef
    entity_ref: SelectedEntityRef | None = None
    metadata: BoundedMetadata
    occurred_at: UtcDatetime

    @model_validator(mode="after")
    def validate_event_bindings(self) -> ApplicationUserEvent:
        if self.workspace.app_id != self.app_id:
            raise ValueError("event workspace must belong to event app")
        if self.entity_ref is not None and self.entity_ref.app_id != self.app_id:
            raise ValueError("event entity must belong to event app")
        return self


class GetRecentUserEventsRequest(ContextBoundAdapterRequest):
    """Request a bounded recent meaningful-event window."""

    limit: int = Field(default=20, ge=1, le=100)
    occurred_after: UtcDatetime | None = None


class GetRecentUserEventsResponse(AdapterResponse):
    """Return privacy-minimized events, never raw clicks or content dumps."""

    events: tuple[ApplicationUserEvent, ...] = Field(default=(), max_length=100)

    @model_validator(mode="after")
    def validate_events(self) -> GetRecentUserEventsResponse:
        event_ids = [event.event_id for event in self.events]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("application event IDs must be unique")
        if any(event.app_id != self.app_id for event in self.events):
            raise ValueError("application events must match response app")
        return self


class AllowedRecordSearchResult(DomainModel):
    """Minimal, field-filtered result for one record the user may view."""

    data_policy: ClassVar[ModelDataPolicy] = _RESPONSE_POLICY

    entity: SelectedEntityRef
    display_label: ShortText
    visible_fields: tuple[VisibleEntityField, ...] = Field(default=(), max_length=25)

    @model_validator(mode="after")
    def require_unique_visible_fields(self) -> AllowedRecordSearchResult:
        field_ids = [field.field_id for field in self.visible_fields]
        if len(field_ids) != len(set(field_ids)):
            raise ValueError("search result field IDs must be unique")
        return self


class SearchAllowedRecordsRequest(ContextBoundAdapterRequest):
    """Search only records and fields the owning application authorizes."""

    query: SearchText
    entity_types: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=25)
    requested_field_ids: tuple[Identifier, ...] = Field(default=(), max_length=25)
    limit: int = Field(default=20, ge=1, le=50)

    @model_validator(mode="after")
    def validate_search_request(self) -> SearchAllowedRecordsRequest:
        if len(self.entity_types) != len(set(self.entity_types)):
            raise ValueError("search entity types must be unique")
        if len(self.requested_field_ids) != len(set(self.requested_field_ids)):
            raise ValueError("search requested field IDs must be unique")
        return self


class SearchAllowedRecordsResponse(AdapterResponse):
    """Return bounded, filtered records rather than an unrestricted query result."""

    results: tuple[AllowedRecordSearchResult, ...] = Field(default=(), max_length=50)

    @model_validator(mode="after")
    def validate_search_results(self) -> SearchAllowedRecordsResponse:
        references = [result.entity for result in self.results]
        if len(references) != len(set(references)):
            raise ValueError("search result entity references must be unique")
        if any(result.entity.app_id != self.app_id for result in self.results):
            raise ValueError("search results must match response app")
        return self


class ExecuteApprovedActionRequest(ContextBoundAdapterRequest):
    """Execution-ready, fully bound state-changing application request."""

    action_definition: ActionDefinition
    proposal: ActionProposal
    confirmation: ActionConfirmation
    idempotency_key: IdempotencyKey

    @model_validator(mode="after")
    def validate_execution_bindings(self) -> ExecuteApprovedActionRequest:
        definition = self.action_definition
        proposal = self.proposal
        confirmation = self.confirmation
        identity = self.trusted_identity
        selected_entity = self.context.selected_entity

        if definition.status is not CatalogStatus.ACTIVE:
            raise ValueError("adapter execution requires an active action definition")
        if proposal.status is not ActionProposalStatus.CONFIRMED:
            raise ValueError("adapter execution requires a confirmed action proposal")
        if confirmation.status is not ActionConfirmationStatus.ACCEPTED:
            raise ValueError("adapter execution requires accepted confirmation state")
        if selected_entity is None or proposal.target != selected_entity:
            raise ValueError("action proposal target must match current selected entity")
        if (
            definition.owner_app_id != self.app_id
            or proposal.owner_app_id != self.app_id
            or definition.action_id != proposal.action_id
            or definition.action_version != proposal.action_version
            or definition.target_entity_type != proposal.target.entity_type
        ):
            raise ValueError("action definition and proposal bindings must match")
        if proposal.idempotency_key != self.idempotency_key:
            raise ValueError("action proposal idempotency key must match adapter request")
        if identity.user_id is None or proposal.proposed_by_user_id != identity.user_id:
            raise ValueError("action proposal user must match trusted identity")
        if (
            proposal.workspace.workspace_id != self.context.workspace.workspace_id
            or proposal.workspace.app_id != self.context.workspace.app_id
        ):
            raise ValueError("action proposal workspace must match current context")
        if (
            confirmation.proposal_id != proposal.proposal_id
            or confirmation.bound_user_id != identity.user_id
            or confirmation.bound_workspace_id != self.context.workspace.workspace_id
            or confirmation.parameter_hash != proposal.parameter_hash
        ):
            raise ValueError(
                "confirmation must match proposal, identity, workspace, and parameters"
            )
        return self


class ExecuteApprovedActionResponse(AdapterResponse):
    """Return the owning application's explicit receipt; never infer success."""

    receipt: AdapterExecutionReceipt

    @model_validator(mode="after")
    def validate_execution_receipt(self) -> ExecuteApprovedActionResponse:
        if self.receipt.owner_app_id != self.app_id:
            raise ValueError("execution receipt must match response app")
        if self.receipt.request_id != self.request_id:
            raise ValueError("execution receipt must match response request ID")
        if self.responded_at < self.receipt.received_at:
            raise ValueError("adapter response cannot precede receipt arrival")
        return self


class LogFeedbackRequest(ContextBoundAdapterRequest):
    """Deliver a non-authoritative feedback signal with replay protection."""

    feedback: RecommendationFeedback
    idempotency_key: IdempotencyKey

    @model_validator(mode="after")
    def validate_feedback_bindings(self) -> LogFeedbackRequest:
        identity = self.trusted_identity
        if identity.user_id is None or self.feedback.user_id != identity.user_id:
            raise ValueError("feedback user must match trusted identity")
        if self.feedback.workspace != self.context.workspace:
            raise ValueError("feedback workspace must match current context")
        if self.feedback.request_id != self.request_id:
            raise ValueError("feedback request ID must match adapter request")
        return self


class FeedbackAcknowledgement(DomainModel):
    """Owning-adapter acknowledgement of feedback delivery, not an action receipt."""

    data_policy: ClassVar[ModelDataPolicy] = _RESPONSE_POLICY

    feedback_id: Identifier
    adapter_reference: Identifier
    accepted_at: UtcDatetime


class LogFeedbackResponse(AdapterResponse):
    """Return an explicit feedback-delivery acknowledgement."""

    acknowledgement: FeedbackAcknowledgement


@runtime_checkable
class OrkaApplicationAdapter(Protocol):
    """Explicit async contract implemented by every owning Orka application."""

    @property
    def metadata(self) -> AdapterMetadata:
        """Return immutable adapter identity, version, and capability metadata."""
        ...

    async def get_app_metadata(self, request: GetAppMetadataRequest) -> GetAppMetadataResponse:
        """Return owning-application metadata."""
        ...

    async def resolve_current_user(
        self, request: ResolveCurrentUserRequest
    ) -> ResolveCurrentUserResponse:
        """Resolve current identity without trusting browser claims."""
        ...

    async def resolve_context(self, request: ResolveContextRequest) -> ResolveContextResponse:
        """Resolve page, workspace, and selected entity."""
        ...

    async def get_user_permissions(
        self, request: GetUserPermissionsRequest
    ) -> GetUserPermissionsResponse:
        """Return fresh explicit authorization facts."""
        ...

    async def get_page_metadata(self, request: GetPageMetadataRequest) -> GetPageMetadataResponse:
        """Return metadata for the verified page."""
        ...

    async def get_selected_entity_summary(
        self, request: GetSelectedEntitySummaryRequest
    ) -> GetSelectedEntitySummaryResponse:
        """Return a permission-filtered selected-entity summary."""
        ...

    async def get_available_features(
        self, request: GetAvailableFeaturesRequest
    ) -> GetAvailableFeaturesResponse:
        """Return currently available feature IDs."""
        ...

    async def get_available_actions(
        self, request: GetAvailableActionsRequest
    ) -> GetAvailableActionsResponse:
        """Return currently available catalogued action IDs."""
        ...

    async def get_recent_user_events(
        self, request: GetRecentUserEventsRequest
    ) -> GetRecentUserEventsResponse:
        """Return bounded meaningful owning-application events."""
        ...

    async def search_allowed_records(
        self, request: SearchAllowedRecordsRequest
    ) -> SearchAllowedRecordsResponse:
        """Search only records and fields authorized by the owning application."""
        ...

    async def execute_approved_action(
        self, request: ExecuteApprovedActionRequest
    ) -> ExecuteApprovedActionResponse:
        """Revalidate and execute one fully bound approved action."""
        ...

    async def log_feedback(self, request: LogFeedbackRequest) -> LogFeedbackResponse:
        """Deliver a non-authoritative feedback signal."""
        ...
