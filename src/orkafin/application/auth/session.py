"""Trusted transport/session subject resolution independent of browser hints."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from orkafin.domain.base import Identifier, LowercaseIdentifier
from orkafin.domain.identifiers import RequestId


@runtime_checkable
class TrustedSessionResolver(Protocol):
    """Resolve an opaque owning-application subject from trusted server state."""

    def resolve_subject_reference(
        self, *, app_id: LowercaseIdentifier, request_id: RequestId
    ) -> Identifier | None:
        """Return a trusted session subject, or ``None`` when no session is verified."""
        ...


class MissingTrustedSessionResolver:
    """Fail-closed resolver used until trusted local session state is configured."""

    def resolve_subject_reference(
        self, *, app_id: LowercaseIdentifier, request_id: RequestId
    ) -> None:
        del app_id, request_id
        return None


class StaticTrustedSessionResolver:
    """TEST HARNESS ONLY: server-injected synthetic adapter session selection."""

    def __init__(self, subject_reference: Identifier | None) -> None:
        self._subject_reference = subject_reference

    def resolve_subject_reference(
        self, *, app_id: LowercaseIdentifier, request_id: RequestId
    ) -> Identifier | None:
        del app_id, request_id
        return self._subject_reference
