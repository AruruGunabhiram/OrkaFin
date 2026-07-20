"""Versioned action definition, intent, confirmation, receipt, and result contracts."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, ClassVar, Literal

from pydantic import Field, StringConstraints, model_validator

from orkafin.domain.base import (
    DataClassification,
    DataOwner,
    DomainModel,
    HandlingRule,
    Identifier,
    LowercaseIdentifier,
    ModelDataPolicy,
    PersistencePolicy,
    Revision,
    SemanticVersion,
    SensitiveFieldPolicy,
    ShortText,
    UtcDatetime,
)
from orkafin.domain.catalog import CatalogStatus
from orkafin.domain.context import SelectedEntityRef, WorkspaceRef
from orkafin.domain.identifiers import (
    IdempotencyKey,
    Permission,
    RequestId,
    SafeReference,
    Sha256Digest,
)

ActionTextValue = Annotated[
    str,
    StringConstraints(min_length=1, max_length=1_000, strip_whitespace=True, strict=True),
]


class ActionSensitivity(StrEnum):
    """Risk classification declared by the action catalog."""

    LOW = "low"
    SENSITIVE = "sensitive"
    DESTRUCTIVE = "destructive"


class ActionParameterType(StrEnum):
    """Closed set of parameter types supported by typed action contracts."""

    TEXT = "text"
    DATE = "date"
    TIMESTAMP = "timestamp"
    INTEGER = "integer"
    BOOLEAN = "boolean"


class ActionParameterDefinition(DomainModel):
    """Catalogued parameter shape; later services enforce action-specific rules."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.PRODUCT_DOCUMENTATION,
        classification=DataClassification.INTERNAL,
        persistence=PersistencePolicy.CATALOG_FILE,
    )

    parameter_id: LowercaseIdentifier
    display_name: ShortText
    parameter_type: ActionParameterType
    required: bool
    sensitive: bool = False
    description: ShortText
    validation_rules: tuple[ShortText, ...] = Field(default=(), max_length=10)


class TextActionParameter(DomainModel):
    """Bounded text action parameter."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.CONFIDENTIAL,
        persistence=PersistencePolicy.ORKAFIN_ALLOWED,
    )

    kind: Literal["text"] = "text"
    parameter_id: LowercaseIdentifier
    value: ActionTextValue


class DateActionParameter(DomainModel):
    """Calendar-date action parameter."""

    data_policy: ClassVar[ModelDataPolicy] = TextActionParameter.data_policy

    kind: Literal["date"] = "date"
    parameter_id: LowercaseIdentifier
    value: date


class TimestampActionParameter(DomainModel):
    """UTC timestamp action parameter."""

    data_policy: ClassVar[ModelDataPolicy] = TextActionParameter.data_policy

    kind: Literal["timestamp"] = "timestamp"
    parameter_id: LowercaseIdentifier
    value: UtcDatetime


class IntegerActionParameter(DomainModel):
    """Strict integer action parameter."""

    data_policy: ClassVar[ModelDataPolicy] = TextActionParameter.data_policy

    kind: Literal["integer"] = "integer"
    parameter_id: LowercaseIdentifier
    value: int


class BooleanActionParameter(DomainModel):
    """Strict boolean action parameter."""

    data_policy: ClassVar[ModelDataPolicy] = TextActionParameter.data_policy

    kind: Literal["boolean"] = "boolean"
    parameter_id: LowercaseIdentifier
    value: bool


ActionParameter = Annotated[
    TextActionParameter
    | DateActionParameter
    | TimestampActionParameter
    | IntegerActionParameter
    | BooleanActionParameter,
    Field(discriminator="kind"),
]


class ActionDefinition(DomainModel):
    """Explicit catalog entry; help text alone can never create an action."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.PRODUCT_DOCUMENTATION,
        classification=DataClassification.INTERNAL,
        persistence=PersistencePolicy.CATALOG_FILE,
    )
    model_config = {
        **DomainModel.model_config,
        "json_schema_extra": {
            "examples": [
                {
                    "schema_version": "v1",
                    "action_id": "candidate.update_start_date",
                    "owner_app_id": "orka_ats",
                    "action_version": "1.0.0",
                    "revision": "rev-001",
                    "title": "Update start date",
                    "description": "Provisional mock-only action contract.",
                    "target_entity_type": "candidate",
                    "required_permission": "candidate.update_start_date",
                    "parameters": [
                        {
                            "schema_version": "v1",
                            "parameter_id": "start_date",
                            "display_name": "Start date",
                            "parameter_type": "date",
                            "required": True,
                            "sensitive": False,
                            "description": "Proposed calendar date.",
                        }
                    ],
                    "confirmation_required": True,
                    "admin_approval_required": False,
                    "reversible": True,
                    "sensitivity": "low",
                    "execution_mode": "mock_only",
                    "validation_rules": [
                        "Accept one complete ISO 8601 calendar date.",
                        "Reject a proposed value equal to the current visible value.",
                    ],
                    "audit_required": True,
                    "audit_field_ids": [
                        "actor_user_id",
                        "workspace_id",
                        "target_candidate_id",
                        "action_id",
                        "action_version",
                        "proposal_id",
                        "request_id",
                        "outcome",
                        "reason_code",
                    ],
                    "failure_behavior": "fail_closed_without_execution",
                    "status": "draft",
                    "safe_reference": "catalog://orka_ats/actions/update_start_date",
                }
            ]
        },
    }

    action_id: LowercaseIdentifier
    owner_app_id: LowercaseIdentifier
    action_version: SemanticVersion
    revision: Revision
    title: ShortText
    description: ShortText
    target_entity_type: LowercaseIdentifier
    required_permission: Permission
    parameters: tuple[ActionParameterDefinition, ...] = Field(max_length=25)
    confirmation_required: Literal[True] = True
    admin_approval_required: bool
    reversible: bool
    sensitivity: ActionSensitivity
    execution_mode: Literal["mock_only"] = "mock_only"
    validation_rules: tuple[ShortText, ...] = Field(default=(), max_length=10)
    audit_required: Literal[True] = True
    audit_field_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=25)
    failure_behavior: Literal["fail_closed_without_execution"] = "fail_closed_without_execution"
    status: CatalogStatus
    safe_reference: SafeReference

    @model_validator(mode="after")
    def require_unique_parameters(self) -> ActionDefinition:
        parameter_ids = [parameter.parameter_id for parameter in self.parameters]
        if len(parameter_ids) != len(set(parameter_ids)):
            raise ValueError("action parameter IDs must be unique")
        if len(self.audit_field_ids) != len(set(self.audit_field_ids)):
            raise ValueError("action audit field IDs must be unique")
        return self


class ActionPreviewChange(DomainModel):
    """One safe, user-visible old/new value in an action preview."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.CONFIDENTIAL,
        persistence=PersistencePolicy.ORKAFIN_ALLOWED,
        sensitive_fields=(
            SensitiveFieldPolicy(
                field_name="old_value",
                classification=DataClassification.CONFIDENTIAL,
                rules=(HandlingRule.MINIMIZE, HandlingRule.REDACT_FROM_LOGS),
            ),
            SensitiveFieldPolicy(
                field_name="new_value",
                classification=DataClassification.CONFIDENTIAL,
                rules=(HandlingRule.MINIMIZE, HandlingRule.REDACT_FROM_LOGS),
            ),
        ),
    )

    field_label: ShortText
    old_value: ShortText | None = None
    new_value: ShortText


class ActionPreview(DomainModel):
    """Exact bounded preview shown before confirmation."""

    data_policy: ClassVar[ModelDataPolicy] = ActionPreviewChange.data_policy

    summary: ShortText
    changes: tuple[ActionPreviewChange, ...] = Field(min_length=1, max_length=25)
    warnings: tuple[ShortText, ...] = Field(default=(), max_length=10)
    reversible: bool


class ActionProposalStatus(StrEnum):
    """Preparation lifecycle before adapter execution."""

    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    EXECUTED = "executed"
    FAILED = "failed"


class ActionProposal(DomainModel):
    """Server-created action intent bound to exact parameters and target."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.RESTRICTED,
        persistence=PersistencePolicy.ORKAFIN_ALLOWED,
        sensitive_fields=(
            SensitiveFieldPolicy(
                field_name="parameters",
                classification=DataClassification.RESTRICTED,
                rules=(HandlingRule.MINIMIZE, HandlingRule.REDACT_FROM_LOGS),
            ),
            SensitiveFieldPolicy(
                field_name="parameter_hash",
                classification=DataClassification.SECRET,
                rules=(HandlingRule.INTERNAL_ONLY,),
            ),
        ),
    )

    proposal_id: Identifier
    action_id: LowercaseIdentifier
    action_version: SemanticVersion
    owner_app_id: LowercaseIdentifier
    status: ActionProposalStatus
    proposed_by_user_id: Identifier
    workspace: WorkspaceRef
    target: SelectedEntityRef
    parameters: tuple[ActionParameter, ...] = Field(max_length=25)
    parameter_hash: Sha256Digest
    preview: ActionPreview
    idempotency_key: IdempotencyKey
    request_id: RequestId
    created_at: UtcDatetime
    expires_at: UtcDatetime

    @model_validator(mode="after")
    def validate_bindings(self) -> ActionProposal:
        if self.owner_app_id != self.workspace.app_id or self.owner_app_id != self.target.app_id:
            raise ValueError("proposal app, workspace, and target must match")
        parameter_ids = [parameter.parameter_id for parameter in self.parameters]
        if len(parameter_ids) != len(set(parameter_ids)):
            raise ValueError("proposal parameter IDs must be unique")
        if self.expires_at < self.created_at:
            raise ValueError("proposal expires_at must not precede created_at")
        return self


class ActionConfirmationStatus(StrEnum):
    """One-time confirmation lifecycle independent of execution."""

    ISSUED = "issued"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CONSUMED = "consumed"


class ActionConfirmation(DomainModel):
    """Hash-only confirmation bound to proposal, user, workspace, and parameters."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.SECRET,
        persistence=PersistencePolicy.ORKAFIN_ALLOWED,
        sensitive_fields=(
            SensitiveFieldPolicy(
                field_name="confirmation_secret_hash",
                classification=DataClassification.SECRET,
                rules=(HandlingRule.HASH_ONLY, HandlingRule.INTERNAL_ONLY),
            ),
            SensitiveFieldPolicy(
                field_name="parameter_hash",
                classification=DataClassification.SECRET,
                rules=(HandlingRule.INTERNAL_ONLY,),
            ),
        ),
    )

    confirmation_id: Identifier
    proposal_id: Identifier
    status: ActionConfirmationStatus
    bound_user_id: Identifier
    bound_workspace_id: Identifier
    parameter_hash: Sha256Digest
    confirmation_secret_hash: Sha256Digest
    issued_at: UtcDatetime
    expires_at: UtcDatetime
    responded_at: UtcDatetime | None = None

    @model_validator(mode="after")
    def validate_lifecycle(self) -> ActionConfirmation:
        if self.expires_at < self.issued_at:
            raise ValueError("confirmation expires_at must not precede issued_at")
        if self.status is ActionConfirmationStatus.ISSUED and self.responded_at is not None:
            raise ValueError("issued confirmation cannot have responded_at")
        if self.status is not ActionConfirmationStatus.ISSUED and self.responded_at is None:
            raise ValueError("resolved confirmation requires responded_at")
        if self.responded_at is not None and self.responded_at < self.issued_at:
            raise ValueError("responded_at must not precede issued_at")
        return self


class AdapterReceiptOutcome(StrEnum):
    """Owning-adapter outcome attested by a receipt."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AdapterExecutionReceipt(DomainModel):
    """Owning-adapter attestation required before OrkaFin can report success."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.OWNING_APPLICATION,
        classification=DataClassification.RESTRICTED,
        persistence=PersistencePolicy.ORKAFIN_ALLOWED,
        sensitive_fields=(
            SensitiveFieldPolicy(
                field_name="adapter_transaction_reference",
                classification=DataClassification.RESTRICTED,
                rules=(HandlingRule.INTERNAL_ONLY, HandlingRule.REDACT_FROM_LOGS),
            ),
        ),
    )

    receipt_id: Identifier
    adapter_id: LowercaseIdentifier
    owner_app_id: LowercaseIdentifier
    action_id: LowercaseIdentifier
    action_version: SemanticVersion
    target: SelectedEntityRef
    request_id: RequestId
    idempotency_key: IdempotencyKey
    adapter_transaction_reference: Identifier
    outcome: AdapterReceiptOutcome
    safe_failure_code: LowercaseIdentifier | None = None
    executed_at: UtcDatetime
    received_at: UtcDatetime

    @model_validator(mode="after")
    def validate_outcome(self) -> AdapterExecutionReceipt:
        if self.owner_app_id != self.target.app_id:
            raise ValueError("receipt owner app must match target app")
        if self.received_at < self.executed_at:
            raise ValueError("receipt received_at must not precede executed_at")
        if self.outcome is AdapterReceiptOutcome.SUCCEEDED and self.safe_failure_code is not None:
            raise ValueError("successful receipt cannot contain a failure code")
        if self.outcome is AdapterReceiptOutcome.FAILED and self.safe_failure_code is None:
            raise ValueError("failed receipt requires a safe failure code")
        return self


class ActionExecutionStatus(StrEnum):
    """Honest OrkaFin execution outcomes, including ambiguous failure."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNKNOWN = "unknown"
    CONFLICT = "conflict"
    REJECTED = "rejected"


class ActionExecutionResult(DomainModel):
    """Execution result whose success state is impossible without a matching receipt."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.RESTRICTED,
        persistence=PersistencePolicy.ORKAFIN_ALLOWED,
    )
    model_config = {
        **DomainModel.model_config,
        "json_schema_extra": {
            "examples": [
                {
                    "schema_version": "v1",
                    "execution_id": "execution-001",
                    "proposal_id": "proposal-001",
                    "action_id": "candidate.update_start_date",
                    "action_version": "1.0.0",
                    "owner_app_id": "orka_ats",
                    "target": {
                        "schema_version": "v1",
                        "app_id": "orka_ats",
                        "entity_type": "candidate",
                        "entity_id": "CAND-1001",
                    },
                    "status": "unknown",
                    "request_id": "00000000-0000-4000-8000-000000000001",
                    "idempotency_key": "action-demo-00000001",
                    "safe_message": "The adapter outcome could not be verified.",
                    "completed_at": "2026-07-13T20:00:00Z",
                }
            ]
        },
    }

    execution_id: Identifier
    proposal_id: Identifier
    action_id: LowercaseIdentifier
    action_version: SemanticVersion
    owner_app_id: LowercaseIdentifier
    target: SelectedEntityRef
    status: ActionExecutionStatus
    request_id: RequestId
    idempotency_key: IdempotencyKey
    adapter_receipt: AdapterExecutionReceipt | None = None
    safe_message: ShortText
    completed_at: UtcDatetime

    @model_validator(mode="after")
    def require_matching_success_receipt(self) -> ActionExecutionResult:
        receipt = self.adapter_receipt
        if self.status is ActionExecutionStatus.SUCCEEDED:
            if receipt is None or receipt.outcome is not AdapterReceiptOutcome.SUCCEEDED:
                raise ValueError("successful action result requires a successful adapter receipt")
        elif receipt is not None and receipt.outcome is AdapterReceiptOutcome.SUCCEEDED:
            raise ValueError("successful adapter receipt requires a successful action result")
        if receipt is not None and (
            receipt.owner_app_id != self.owner_app_id
            or receipt.action_id != self.action_id
            or receipt.action_version != self.action_version
            or receipt.target != self.target
            or receipt.request_id != self.request_id
            or receipt.idempotency_key != self.idempotency_key
        ):
            raise ValueError("adapter receipt does not match the execution result")
        return self
