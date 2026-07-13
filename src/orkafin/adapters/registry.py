"""Dependency-injected adapter factory registry with no global mutable state."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from orkafin.adapters.base import (
    ADAPTER_CONTRACT_VERSION,
    AdapterCapability,
    OrkaApplicationAdapter,
)
from orkafin.adapters.errors import (
    AdapterConflictError,
    AdapterError,
    AdapterInternalFailureError,
    AdapterNotFoundError,
    AdapterUnsupportedCapabilityError,
)
from orkafin.domain.base import LowercaseIdentifier
from orkafin.domain.identifiers import RequestId

AdapterFactory = Callable[[], OrkaApplicationAdapter]


@dataclass(frozen=True, slots=True)
class AdapterRegistration:
    """One owning application and its injected adapter factory."""

    app_id: LowercaseIdentifier
    factory: AdapterFactory


class AdapterRegistry:
    """Resolve configured application adapters and validate their declarations."""

    def __init__(self, registrations: Iterable[AdapterRegistration] = ()) -> None:
        self._factories: dict[str, AdapterFactory] = {}
        self._instances: dict[str, OrkaApplicationAdapter] = {}
        for registration in registrations:
            if registration.app_id in self._factories:
                raise AdapterConflictError(
                    app_id=registration.app_id,
                    safe_message="More than one adapter is registered for the application.",
                )
            self._factories[registration.app_id] = registration.factory

    @property
    def registered_app_ids(self) -> tuple[str, ...]:
        """Return deterministic configured app IDs without constructing adapters."""
        return tuple(sorted(self._factories))

    def resolve(
        self,
        app_id: LowercaseIdentifier,
        *,
        required_capability: AdapterCapability | None = None,
        request_id: RequestId | None = None,
    ) -> OrkaApplicationAdapter:
        """Resolve and validate one lazily constructed adapter instance."""
        factory = self._factories.get(app_id)
        if factory is None:
            raise AdapterNotFoundError(request_id=request_id, app_id=app_id)

        adapter = self._instances.get(app_id)
        if adapter is None:
            try:
                candidate = factory()
            except AdapterError:
                raise
            except Exception as error:
                raise AdapterInternalFailureError(request_id=request_id, app_id=app_id) from error
            if not isinstance(candidate, OrkaApplicationAdapter):
                raise AdapterInternalFailureError(
                    request_id=request_id,
                    app_id=app_id,
                    safe_message="The configured application adapter is invalid.",
                )
            adapter = candidate
            self._validate_metadata(adapter, app_id=app_id, request_id=request_id)
            self._instances[app_id] = adapter

        if required_capability is not None and not adapter.metadata.supports(required_capability):
            raise AdapterUnsupportedCapabilityError(request_id=request_id, app_id=app_id)
        return adapter

    @staticmethod
    def _validate_metadata(
        adapter: OrkaApplicationAdapter,
        *,
        app_id: str,
        request_id: RequestId | None,
    ) -> None:
        metadata = adapter.metadata
        if metadata.owning_app_id != app_id:
            raise AdapterConflictError(
                request_id=request_id,
                app_id=app_id,
                safe_message="The configured adapter does not match the application.",
            )
        if metadata.adapter_contract_version != ADAPTER_CONTRACT_VERSION:
            raise AdapterConflictError(
                request_id=request_id,
                app_id=app_id,
                safe_message="The configured adapter contract version is incompatible.",
            )
