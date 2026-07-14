"""Typed identity resolution with a fail-closed synthetic local implementation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import ClassVar, Literal, Protocol, runtime_checkable

from orkafin.application.auth.fixtures import LocalFixtureUserSet
from orkafin.domain.base import (
    DataClassification,
    DataOwner,
    DomainModel,
    Identifier,
    ModelDataPolicy,
    PersistencePolicy,
)
from orkafin.domain.context import (
    ClientContextHint,
    IdentityVerificationStatus,
    UserIdentity,
)


class IdentityResolutionRequest(DomainModel):
    """Server-created identity selection plus non-authoritative client navigation."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.RESTRICTED,
        persistence=PersistencePolicy.NEVER,
    )

    trust_label: Literal["trusted_server_identity_selection"] = "trusted_server_identity_selection"
    trusted_subject_id: Identifier | None = None
    client_hint: ClientContextHint | None = None


@runtime_checkable
class IdentityResolver(Protocol):
    """Resolve request identity without treating client navigation as authority."""

    def resolve_identity(self, request: IdentityResolutionRequest) -> UserIdentity:
        """Return a verified identity or the claim-free unverified identity."""
        ...


class LocalFixtureIdentityResolver:
    """TEST HARNESS ONLY: resolve an explicit trusted synthetic fixture selection."""

    def __init__(
        self,
        fixtures: LocalFixtureUserSet,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._fixtures = fixtures
        self._clock = clock or (lambda: datetime.now(UTC))

    def resolve_identity(self, request: IdentityResolutionRequest) -> UserIdentity:
        """Ignore client navigation and resolve only the trusted server selection."""
        fixture = self._fixtures.find_user(request.trusted_subject_id)
        if (
            fixture is None
            or fixture.identity.verification_status is IdentityVerificationStatus.UNVERIFIED
        ):
            return UserIdentity(verification_status=IdentityVerificationStatus.UNVERIFIED)

        identity = fixture.identity
        assert identity.user_id is not None
        assert identity.role is not None
        return UserIdentity(
            user_id=identity.user_id,
            display_name=identity.display_name,
            email=identity.email,
            role=identity.role,
            verification_status=IdentityVerificationStatus.LOCAL_FIXTURE_VERIFIED,
            verified_at=self._clock(),
            verification_reference=f"local-fixture:{fixture.fixture_id}",
        )
