"""Provider interface intentionally isolated from retrieval, adapters, and routing."""

from __future__ import annotations

from typing import Protocol

from orkafin.providers.contracts import ProviderDraft, ProviderRequest


class ResponseProvider(Protocol):
    """Generate wording from already-minimized, server-approved request data only."""

    def generate(self, request: ProviderRequest) -> ProviderDraft:
        """Return an untrusted typed draft for service-side validation."""
