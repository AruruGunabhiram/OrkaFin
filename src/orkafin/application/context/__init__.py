"""Trusted context resolution application boundary."""

from orkafin.application.context.errors import (
    AppNotSupportedError,
    CandidateAccessDeniedError,
    ContextAccessDeniedError,
    ContextUnavailableError,
    IdentityUnverifiedContextError,
    PageNotSupportedError,
)
from orkafin.application.context.service import AuditRecorder, TrustedContextResolutionService

__all__ = [
    "AuditRecorder",
    "AppNotSupportedError",
    "CandidateAccessDeniedError",
    "ContextAccessDeniedError",
    "ContextUnavailableError",
    "IdentityUnverifiedContextError",
    "PageNotSupportedError",
    "TrustedContextResolutionService",
]
