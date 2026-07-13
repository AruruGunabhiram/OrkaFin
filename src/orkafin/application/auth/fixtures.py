"""Validated synthetic users for the local identity test harness only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar, Literal

import yaml  # type: ignore[import-untyped]
from pydantic import Field, ValidationError, model_validator

from orkafin.application.permissions.models import (
    AuthorizationSource,
    TrustedAuthorizationFacts,
)
from orkafin.domain.base import (
    DataClassification,
    DataOwner,
    DomainModel,
    EmailAddress,
    Identifier,
    LowercaseIdentifier,
    ModelDataPolicy,
    PersistencePolicy,
    ShortText,
)
from orkafin.domain.context import IdentityVerificationStatus, Role


class FixtureConfigurationError(ValueError):
    """A controlled local fixture is missing or invalid."""


class LocalFixtureIdentity(DomainModel):
    """Static synthetic identity data; verification time is set by the resolver."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.RESTRICTED,
        persistence=PersistencePolicy.CATALOG_FILE,
    )

    verification_status: IdentityVerificationStatus
    user_id: Identifier | None = None
    display_name: ShortText | None = None
    email: EmailAddress | None = None
    role: Role | None = None

    @model_validator(mode="after")
    def validate_local_fixture_identity(self) -> LocalFixtureIdentity:
        values = (self.user_id, self.display_name, self.email, self.role)
        if self.verification_status is IdentityVerificationStatus.UNVERIFIED:
            if any(value is not None for value in values):
                raise ValueError("unverified local fixture must not contain identity claims")
            return self
        if self.verification_status is not IdentityVerificationStatus.LOCAL_FIXTURE_VERIFIED:
            raise ValueError("local fixture cannot claim adapter verification")
        if self.user_id is None or self.role is None:
            raise ValueError("verified local fixture requires user_id and role")
        return self


class LocalFixtureUser(DomainModel):
    """Identity and separate trusted authorization facts for one synthetic user."""

    data_policy: ClassVar[ModelDataPolicy] = LocalFixtureIdentity.data_policy

    fixture_id: LowercaseIdentifier
    identity: LocalFixtureIdentity
    authorization: TrustedAuthorizationFacts | None = None

    @model_validator(mode="after")
    def keep_role_separate_from_authorization(self) -> LocalFixtureUser:
        if self.identity.verification_status is IdentityVerificationStatus.UNVERIFIED:
            if self.authorization is not None:
                raise ValueError("unverified fixture cannot carry authorization facts")
            return self
        if self.authorization is None:
            raise ValueError("verified fixture requires explicit authorization facts")
        if self.authorization.source is not AuthorizationSource.LOCAL_FIXTURE:
            raise ValueError("local fixture authorization must identify the local fixture source")
        role = self.identity.role
        assert role is not None
        if role.owner_app_id != self.authorization.app_id:
            raise ValueError("fixture role owner must match authorization app")
        return self


class LocalFixtureUserSet(DomainModel):
    """Version-controlled synthetic local identities pending human policy review."""

    data_policy: ClassVar[ModelDataPolicy] = LocalFixtureIdentity.data_policy

    fixture_kind: Literal["synthetic_local_identity_test_harness"]
    policy_status: Literal["provisional_human_review_required"]
    users: tuple[LocalFixtureUser, ...] = Field(min_length=1, max_length=25)

    @model_validator(mode="after")
    def require_unique_fixture_ids(self) -> LocalFixtureUserSet:
        fixture_ids = tuple(user.fixture_id for user in self.users)
        if len(fixture_ids) != len(set(fixture_ids)):
            raise ValueError("local fixture user IDs must be unique")
        return self

    def find_user(self, fixture_id: str | None) -> LocalFixtureUser | None:
        """Return an exact trusted fixture selection without using browser claims."""
        if fixture_id is None:
            return None
        return next((user for user in self.users if user.fixture_id == fixture_id), None)


def load_local_fixture_users(path: Path | str) -> LocalFixtureUserSet:
    """Load the explicit local test harness; never use this as production authentication."""
    fixture_path = Path(path).resolve()
    if not fixture_path.is_file():
        raise FixtureConfigurationError(f"local fixture file does not exist: {fixture_path}")
    try:
        raw = yaml.safe_load(fixture_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise FixtureConfigurationError("local fixture file contains invalid YAML") from error
    if not isinstance(raw, dict):
        raise FixtureConfigurationError("local fixture file must contain a YAML mapping")
    try:
        return LocalFixtureUserSet.model_validate_json(json.dumps(raw, default=str))
    except ValidationError as error:
        raise FixtureConfigurationError(f"invalid local identity fixtures: {error}") from error
