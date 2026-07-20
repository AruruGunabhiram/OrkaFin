"""Safe versioned API error contract shared by domain and HTTP layers."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, ClassVar

from pydantic import (
    ConfigDict,
    RootModel,
    StrictBool,
    StrictInt,
    StrictStr,
    StringConstraints,
    model_validator,
)

from orkafin.domain.base import (
    DataClassification,
    DataOwner,
    DomainModel,
    ModelDataPolicy,
    PersistencePolicy,
    ShortText,
)
from orkafin.domain.identifiers import RequestId

ErrorDetailKey = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=48,
        pattern=r"^[a-z][a-z0-9_]*$",
        strict=True,
    ),
]
ErrorDetailValue = StrictStr | StrictInt | StrictBool | tuple[StrictStr, ...]


class ErrorCode(StrEnum):
    """Stable public error codes for V1 API clients."""

    VALIDATION_ERROR = "validation_error"
    DOMAIN_ERROR = "domain_error"
    IDENTITY_UNVERIFIED = "identity_unverified"
    CONTEXT_ACCESS_DENIED = "context_access_denied"
    CANDIDATE_ACCESS_DENIED = "candidate_access_denied"
    APP_NOT_SUPPORTED = "app_not_supported"
    PAGE_NOT_SUPPORTED = "page_not_supported"
    ADAPTER_UNAVAILABLE = "adapter_unavailable"
    ACTION_NOT_AVAILABLE = "action_not_available"
    ACTION_ACCESS_DENIED = "action_access_denied"
    ACTION_INPUT_INVALID = "action_input_invalid"
    ACTION_PROPOSAL_NOT_FOUND = "action_proposal_not_found"
    ACTION_CONFIRMATION_INVALID = "action_confirmation_invalid"
    ACTION_CONFIRMATION_EXPIRED = "action_confirmation_expired"
    ACTION_STATE_CONFLICT = "action_state_conflict"
    INTERNAL_ERROR = "internal_error"


class SafeErrorDetails(RootModel[dict[ErrorDetailKey, ErrorDetailValue]]):
    """Bounded public details that cannot carry arbitrary exception payloads."""

    model_config = ConfigDict(frozen=True, strict=True)
    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.INTERNAL,
        persistence=PersistencePolicy.NEVER,
    )

    @model_validator(mode="after")
    def validate_bounds(self) -> SafeErrorDetails:
        if len(self.root) > 8:
            raise ValueError("error details may contain at most 8 entries")
        for value in self.root.values():
            if isinstance(value, str) and len(value) > 256:
                raise ValueError("error detail strings may contain at most 256 characters")
            if isinstance(value, tuple) and (
                len(value) > 25 or any(len(item) > 128 for item in value)
            ):
                raise ValueError("error detail lists exceed public response limits")
        return self


class ApiError(DomainModel):
    """Safe public error response returned by every central handler."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.INTERNAL,
        persistence=PersistencePolicy.NEVER,
    )

    code: ErrorCode
    message: ShortText
    request_id: RequestId
    details: SafeErrorDetails | None = None
