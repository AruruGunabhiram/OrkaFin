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
    ADAPTER_UNAVAILABLE = "adapter_unavailable"
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
