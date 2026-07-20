"""Safe failures for proposal and confirmation state transitions."""

from fastapi import status

from orkafin.core.errors import DomainError
from orkafin.domain.errors import ErrorCode


class ActionNotAvailableError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = ErrorCode.ACTION_NOT_AVAILABLE
    public_message = "The requested action is not available."


class ActionAccessDeniedError(DomainError):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = ErrorCode.ACTION_ACCESS_DENIED
    public_message = "This action is not available for the verified account."


class ActionInputInvalidError(DomainError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    error_code = ErrorCode.ACTION_INPUT_INVALID
    public_message = "The proposed action value is not valid."


class ActionProposalNotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = ErrorCode.ACTION_PROPOSAL_NOT_FOUND
    public_message = "The requested action proposal is unavailable."


class ActionConfirmationInvalidError(DomainError):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = ErrorCode.ACTION_CONFIRMATION_INVALID
    public_message = "The action confirmation could not be verified."


class ActionConfirmationExpiredError(DomainError):
    status_code = status.HTTP_410_GONE
    error_code = ErrorCode.ACTION_CONFIRMATION_EXPIRED
    public_message = "The action confirmation has expired. No action was executed."


class ActionStateConflictError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    error_code = ErrorCode.ACTION_STATE_CONFLICT
    public_message = "The action proposal is no longer confirmable. No action was executed."


class ActionExecutionAccessDeniedError(DomainError):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = ErrorCode.ACTION_ACCESS_DENIED
    public_message = "Execution permission is no longer available. No changes were made."


class ActionExecutionStateConflictError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    error_code = ErrorCode.ACTION_STATE_CONFLICT
    public_message = "The approved action conflicts with current state. No changes were made."
