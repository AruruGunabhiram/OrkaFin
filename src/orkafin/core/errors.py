"""Safe, versioned API errors and central exception handlers."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from orkafin.core.logging import get_logger
from orkafin.core.request_id import REQUEST_ID_HEADER, get_request_id, new_request_id
from orkafin.domain.errors import ApiError, ErrorCode, SafeErrorDetails
from orkafin.domain.identifiers import RequestId


class DomainError(Exception):
    """A known application failure with a safe, generic public message."""

    public_message = "The request could not be completed."
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = ErrorCode.DOMAIN_ERROR


class AdapterError(Exception):
    """A known dependency failure that must not be described as successful."""

    public_message = "A required dependency is currently unavailable."


def _request_id_for(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None) or get_request_id()
    return request_id if isinstance(request_id, str) else new_request_id()


def _error_response(
    *,
    request: Request,
    status_code: int,
    code: ErrorCode,
    message: str,
    details: SafeErrorDetails | None = None,
) -> JSONResponse:
    request_id = _request_id_for(request)
    body = ApiError(
        code=code,
        message=message,
        request_id=RequestId(root=request_id),
        details=details,
    ).model_dump(exclude_none=True, mode="json")
    return JSONResponse(
        status_code=status_code,
        content=body,
        headers={REQUEST_ID_HEADER: request_id},
    )


def _validation_details(error: RequestValidationError) -> SafeErrorDetails:
    fields = [".".join(str(part) for part in issue["loc"]) for issue in error.errors()]
    return SafeErrorDetails(root={"fields": tuple(fields)})


def install_exception_handlers(application: FastAPI, *, debug: bool) -> None:
    """Install safe central handlers without exposing exception values or traces."""
    logger = get_logger("api.errors")

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            request=request,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code=ErrorCode.VALIDATION_ERROR,
            message="Request validation failed.",
            details=_validation_details(error),
        )

    @application.exception_handler(DomainError)
    async def handle_domain_error(request: Request, error: DomainError) -> JSONResponse:
        logger.warning("domain_error", extra={"error_type": type(error).__name__})
        return _error_response(
            request=request,
            status_code=error.status_code,
            code=error.error_code,
            message=error.public_message,
        )

    @application.exception_handler(AdapterError)
    async def handle_adapter_error(request: Request, error: AdapterError) -> JSONResponse:
        logger.warning("adapter_error", extra={"error_type": type(error).__name__})
        return _error_response(
            request=request,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code=ErrorCode.ADAPTER_UNAVAILABLE,
            message=f"{error.public_message} No application data was returned.",
        )

    @application.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
        logger.error("unexpected_error", extra={"error_type": type(error).__name__})
        return _error_response(
            request=request,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code=ErrorCode.INTERNAL_ERROR,
            message="An unexpected error occurred.",
            details=(
                SafeErrorDetails(root={"error_type": type(error).__name__}) if debug else None
            ),
        )
