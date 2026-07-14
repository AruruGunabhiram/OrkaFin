"""Safe failures raised by trusted context orchestration."""

from fastapi import status

from orkafin.core.errors import DomainError
from orkafin.domain.errors import ErrorCode


class IdentityUnverifiedContextError(DomainError):
    """No trusted session identity was available for context resolution."""

    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = ErrorCode.IDENTITY_UNVERIFIED
    public_message = "Sign-in verification is required before this information can be shown."


class ContextAccessDeniedError(DomainError):
    """Trusted application facts deny the requested application or page."""

    status_code = status.HTTP_403_FORBIDDEN
    error_code = ErrorCode.CONTEXT_ACCESS_DENIED
    public_message = "This area is not available for the verified account."


class CandidateAccessDeniedError(DomainError):
    """Trusted application facts deny the selected candidate read."""

    status_code = status.HTTP_403_FORBIDDEN
    error_code = ErrorCode.CANDIDATE_ACCESS_DENIED
    public_message = (
        "The requested candidate information is not available for the verified account."
    )


class AppNotSupportedError(DomainError):
    """The requested application has no configured V1 adapter."""

    status_code = status.HTTP_404_NOT_FOUND
    error_code = ErrorCode.APP_NOT_SUPPORTED
    public_message = "The requested application is not supported."


class PageNotSupportedError(DomainError):
    """The requested page is not known to the configured application adapter."""

    status_code = status.HTTP_404_NOT_FOUND
    error_code = ErrorCode.PAGE_NOT_SUPPORTED
    public_message = "The requested application page is not supported."


class ContextUnavailableError(DomainError):
    """Trusted context responses were incomplete or internally inconsistent."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = ErrorCode.ADAPTER_UNAVAILABLE
    public_message = "Trusted application context is unavailable. No application data was returned."
