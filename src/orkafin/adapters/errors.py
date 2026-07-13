"""Explicit adapter failure schemas, exceptions, and wire-to-runtime mapping."""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from pydantic import model_validator

from orkafin.adapters.base import ADAPTER_CONTRACT_VERSION, AdapterContractVersion
from orkafin.core.errors import AdapterError as CoreAdapterError
from orkafin.domain.base import (
    DataClassification,
    DataOwner,
    DomainModel,
    Identifier,
    LowercaseIdentifier,
    ModelDataPolicy,
    PersistencePolicy,
    ShortText,
    UtcDatetime,
)
from orkafin.domain.identifiers import RequestId


class AdapterErrorCode(StrEnum):
    """Stable failure vocabulary shared by all application adapters."""

    UNAVAILABLE = "unavailable"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    VALIDATION_FAILED = "validation_failed"
    CONFLICT = "conflict"
    TIMEOUT = "timeout"
    INTERNAL_FAILURE = "internal_failure"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"


_RETRYABLE_CODES = frozenset(
    {
        AdapterErrorCode.UNAVAILABLE,
        AdapterErrorCode.TIMEOUT,
    }
)


class AdapterFailure(DomainModel):
    """Versioned safe failure response returned instead of an operation response."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.OWNING_APPLICATION,
        classification=DataClassification.INTERNAL,
        persistence=PersistencePolicy.NEVER,
    )

    adapter_contract_version: AdapterContractVersion = ADAPTER_CONTRACT_VERSION
    request_id: RequestId
    app_id: LowercaseIdentifier
    adapter_response_id: Identifier
    code: AdapterErrorCode
    safe_message: ShortText
    retryable: bool
    failure_reference: Identifier | None = None
    failed_at: UtcDatetime

    @model_validator(mode="after")
    def validate_retry_policy(self) -> AdapterFailure:
        if self.retryable != (self.code in _RETRYABLE_CODES):
            raise ValueError("adapter failure retryable flag must match the contract policy")
        return self


class AdapterError(CoreAdapterError):
    """Base typed adapter exception with safe fields only."""

    code: ClassVar[AdapterErrorCode]
    retryable: ClassVar[bool] = False
    default_message: ClassVar[str] = "The owning application could not complete the request."

    def __init__(
        self,
        *,
        request_id: RequestId | None = None,
        app_id: str | None = None,
        safe_message: str | None = None,
        adapter_response_id: str | None = None,
        failure_reference: str | None = None,
    ) -> None:
        self.request_id = request_id
        self.app_id = app_id
        self.adapter_response_id = adapter_response_id
        self.failure_reference = failure_reference
        self.public_message = safe_message or self.default_message
        super().__init__(self.public_message)


class AdapterUnavailableError(AdapterError):
    code = AdapterErrorCode.UNAVAILABLE
    retryable = True
    default_message = "The owning application is currently unavailable."


class AdapterUnauthorizedError(AdapterError):
    code = AdapterErrorCode.UNAUTHORIZED
    default_message = "Trusted application identity could not be verified."


class AdapterForbiddenError(AdapterError):
    code = AdapterErrorCode.FORBIDDEN
    default_message = "The owning application denied this request."


class AdapterNotFoundError(AdapterError):
    code = AdapterErrorCode.NOT_FOUND
    default_message = "The requested application resource is unavailable."


class AdapterValidationFailedError(AdapterError):
    code = AdapterErrorCode.VALIDATION_FAILED
    default_message = "The owning application rejected the request."


class AdapterConflictError(AdapterError):
    code = AdapterErrorCode.CONFLICT
    default_message = "The owning application detected a conflicting state."


class AdapterTimeoutError(AdapterError):
    code = AdapterErrorCode.TIMEOUT
    retryable = True
    default_message = "The owning application did not confirm an outcome in time."


class AdapterInternalFailureError(AdapterError):
    code = AdapterErrorCode.INTERNAL_FAILURE
    default_message = "The owning application encountered an internal failure."


class AdapterUnsupportedCapabilityError(AdapterError):
    code = AdapterErrorCode.UNSUPPORTED_CAPABILITY
    default_message = "The owning application does not support this capability."


_ERROR_TYPES: dict[AdapterErrorCode, type[AdapterError]] = {
    AdapterErrorCode.UNAVAILABLE: AdapterUnavailableError,
    AdapterErrorCode.UNAUTHORIZED: AdapterUnauthorizedError,
    AdapterErrorCode.FORBIDDEN: AdapterForbiddenError,
    AdapterErrorCode.NOT_FOUND: AdapterNotFoundError,
    AdapterErrorCode.VALIDATION_FAILED: AdapterValidationFailedError,
    AdapterErrorCode.CONFLICT: AdapterConflictError,
    AdapterErrorCode.TIMEOUT: AdapterTimeoutError,
    AdapterErrorCode.INTERNAL_FAILURE: AdapterInternalFailureError,
    AdapterErrorCode.UNSUPPORTED_CAPABILITY: AdapterUnsupportedCapabilityError,
}


def adapter_error_from_failure(failure: AdapterFailure) -> AdapterError:
    """Map a validated failure response to its exact runtime exception type."""
    error_type = _ERROR_TYPES[failure.code]
    return error_type(
        request_id=failure.request_id,
        app_id=failure.app_id,
        safe_message=failure.safe_message,
        adapter_response_id=failure.adapter_response_id,
        failure_reference=failure.failure_reference,
    )
