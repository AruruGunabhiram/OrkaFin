"""Public contracts for the single mock-only confirmed-action proof of concept."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, ClassVar, Literal

from pydantic import Field, StringConstraints, field_validator

from orkafin.domain.actions import (
    ActionConfirmationStatus,
    ActionPreviewChange,
    ActionProposalStatus,
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
from orkafin.domain.context import ClientContextHint

IsoDateText = Annotated[
    str,
    StringConstraints(
        min_length=10,
        max_length=10,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        strict=True,
    ),
]
ConfirmationToken = Annotated[
    str,
    StringConstraints(
        min_length=43,
        max_length=128,
        pattern=r"^[A-Za-z0-9_-]+$",
        strict=True,
    ),
]


class UpdateStartDateParameters(DomainModel):
    """Exact input schema for ``candidate.update_start_date`` and no other action."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.CLIENT,
        classification=DataClassification.CONFIDENTIAL,
        persistence=PersistencePolicy.NEVER,
    )

    start_date: IsoDateText

    @field_validator("start_date")
    @classmethod
    def require_calendar_date(cls, value: str) -> str:
        try:
            date.fromisoformat(value)
        except ValueError as error:
            raise ValueError("start_date must be a real ISO calendar date") from error
        return value

    @property
    def date_value(self) -> date:
        """Return the already validated calendar date."""
        return date.fromisoformat(self.start_date)


class ActionProposalRequest(DomainModel):
    """Untrusted intent plus navigation hints; identity and permissions are absent."""

    data_policy: ClassVar[ModelDataPolicy] = UpdateStartDateParameters.data_policy

    action_id: LowercaseIdentifier
    parameters: UpdateStartDateParameters
    context: ClientContextHint


class ActionConfirmationDecision(StrEnum):
    """The only explicit user responses to a confirmation challenge."""

    ACCEPT = "accept"
    REJECT = "reject"


class ActionConfirmationRequest(DomainModel):
    """One confirmation response bound again to exact parameters and current context."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.CLIENT,
        classification=DataClassification.SECRET,
        persistence=PersistencePolicy.NEVER,
        sensitive_fields=(
            SensitiveFieldPolicy(
                field_name="confirmation_token",
                classification=DataClassification.SECRET,
                rules=(HandlingRule.NEVER_PERSIST, HandlingRule.REDACT_FROM_LOGS),
            ),
        ),
    )

    decision: Literal["accept", "reject"]
    confirmation_token: ConfirmationToken
    parameters: UpdateStartDateParameters
    context: ClientContextHint


class ActionProposalPreview(DomainModel):
    """Complete safe preview shown before the user confirms or cancels."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.CONFIDENTIAL,
        persistence=PersistencePolicy.NEVER,
        sensitive_fields=(
            SensitiveFieldPolicy(
                field_name="changes",
                classification=DataClassification.CONFIDENTIAL,
                rules=(HandlingRule.MINIMIZE, HandlingRule.REDACT_FROM_LOGS),
            ),
        ),
    )

    action_id: LowercaseIdentifier
    action_version: SemanticVersion
    owning_app_id: LowercaseIdentifier
    owning_app_display_name: ShortText
    target_candidate_id: Identifier
    affected_user_id: Identifier
    affected_user_display_name: ShortText | None = None
    affected_workspace_id: Identifier
    affected_workspace_display_name: ShortText | None = None
    summary: ShortText
    changes: tuple[ActionPreviewChange, ...] = Field(min_length=1, max_length=5)
    reversible: bool
    warnings: tuple[ShortText, ...] = Field(min_length=1, max_length=10)


class ActionConfirmationChallenge(DomainModel):
    """Plaintext challenge returned once; only its SHA-256 digest is persisted."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.SECRET,
        persistence=PersistencePolicy.NEVER,
        sensitive_fields=(
            SensitiveFieldPolicy(
                field_name="confirmation_token",
                classification=DataClassification.SECRET,
                rules=(HandlingRule.NEVER_PERSIST, HandlingRule.REDACT_FROM_LOGS),
            ),
        ),
    )

    confirmation_token: ConfirmationToken
    expires_at: UtcDatetime


class ActionProposalResponse(DomainModel):
    """Created proposal with preview and a one-time confirmation challenge."""

    data_policy: ClassVar[ModelDataPolicy] = ActionProposalPreview.data_policy

    proposal_id: Identifier
    proposal_status: Literal[ActionProposalStatus.PROPOSED] = ActionProposalStatus.PROPOSED
    preview: ActionProposalPreview
    confirmation: ActionConfirmationChallenge
    expires_at: UtcDatetime
    execution_ready: Literal[False] = False
    execution_enabled: Literal[False] = False
    execution_state: Literal["not_started"] = "not_started"


class ActionConfirmationResponse(DomainModel):
    """Confirmation-only result; no execution record or adapter call is represented."""

    data_policy: ClassVar[ModelDataPolicy] = ActionProposalPreview.data_policy

    proposal_id: Identifier
    proposal_status: ActionProposalStatus
    confirmation_status: ActionConfirmationStatus
    execution_ready: bool
    execution_enabled: Literal[False] = False
    execution_state: Literal["not_started"] = "not_started"
    message: ShortText
