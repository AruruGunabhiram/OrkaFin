"""Request-correlation IDs and middleware."""

from __future__ import annotations

from contextvars import ContextVar, Token
from uuid import UUID, uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

REQUEST_ID_HEADER = "X-Request-ID"
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def new_request_id() -> str:
    """Return a canonical UUID4 request ID."""
    return str(uuid4())


def is_valid_request_id(value: str | None) -> bool:
    """Accept canonical UUID text and reject unbounded arbitrary header values."""
    if not isinstance(value, str):
        return False
    try:
        parsed = UUID(value)
    except (AttributeError, ValueError):
        return False
    return str(parsed) == value.lower()


def resolve_request_id(incoming_id: str | None, *, accept_incoming: bool) -> str:
    """Use an allowed, syntactically valid caller ID or generate a new one."""
    if accept_incoming and incoming_id is not None and is_valid_request_id(incoming_id):
        return incoming_id.lower()
    return new_request_id()


def get_request_id() -> str | None:
    """Get the ID associated with the active request, if one exists."""
    return _request_id.get()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a request ID to request state, context, response, and log records."""

    def __init__(self, app: ASGIApp, *, accept_incoming: bool) -> None:
        super().__init__(app)
        self._accept_incoming = accept_incoming

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = resolve_request_id(
            request.headers.get(REQUEST_ID_HEADER),
            accept_incoming=self._accept_incoming,
        )
        request.state.request_id = request_id
        context_token: Token[str | None] = _request_id.set(request_id)
        try:
            response = await call_next(request)
        finally:
            _request_id.reset(context_token)

        response.headers[REQUEST_ID_HEADER] = request_id
        return response
