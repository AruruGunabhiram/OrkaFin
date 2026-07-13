"""Identity resolution boundary and explicit local test fixtures."""

from orkafin.application.auth.fixtures import (
    FixtureConfigurationError,
    LocalFixtureIdentity,
    LocalFixtureUser,
    LocalFixtureUserSet,
    load_local_fixture_users,
)
from orkafin.application.auth.resolver import (
    IdentityResolutionRequest,
    IdentityResolver,
    LocalFixtureIdentityResolver,
)
from orkafin.application.auth.session import (
    MissingTrustedSessionResolver,
    StaticTrustedSessionResolver,
    TrustedSessionResolver,
)

__all__ = [
    "FixtureConfigurationError",
    "IdentityResolutionRequest",
    "IdentityResolver",
    "LocalFixtureIdentity",
    "LocalFixtureIdentityResolver",
    "LocalFixtureUser",
    "LocalFixtureUserSet",
    "MissingTrustedSessionResolver",
    "StaticTrustedSessionResolver",
    "TrustedSessionResolver",
    "load_local_fixture_users",
]
