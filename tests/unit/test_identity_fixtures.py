from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from orkafin.application.auth import (
    FixtureConfigurationError,
    IdentityResolutionRequest,
    IdentityResolver,
    LocalFixtureIdentityResolver,
    load_local_fixture_users,
)
from orkafin.domain.context import IdentityVerificationStatus

NOW = datetime(2026, 7, 13, 20, 0, tzinfo=UTC)
FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "users.yaml"


def test_local_fixture_file_contains_only_explicit_synthetic_user_kinds() -> None:
    fixtures = load_local_fixture_users(FIXTURE_PATH)

    assert fixtures.fixture_kind == "synthetic_local_identity_test_harness"
    assert fixtures.policy_status == "provisional_human_review_required"
    assert {user.fixture_id for user in fixtures.users} == {
        "admin",
        "recruiter",
        "limited_viewer",
        "unverified",
    }
    for user in fixtures.users:
        if user.identity.email is not None:
            assert user.identity.email.endswith("@example.invalid")
        if user.identity.verification_status is IdentityVerificationStatus.UNVERIFIED:
            assert user.authorization is None


def test_local_resolver_implements_interface_and_fails_closed_for_unknown_selection() -> None:
    fixtures = load_local_fixture_users(FIXTURE_PATH)
    resolver = LocalFixtureIdentityResolver(fixtures, clock=lambda: NOW)

    assert isinstance(resolver, IdentityResolver)
    verified = resolver.resolve_identity(IdentityResolutionRequest(trusted_subject_id="recruiter"))
    unknown = resolver.resolve_identity(
        IdentityResolutionRequest(trusted_subject_id="unknown-fixture")
    )
    missing = resolver.resolve_identity(IdentityResolutionRequest())

    assert verified.verification_status is IdentityVerificationStatus.LOCAL_FIXTURE_VERIFIED
    assert verified.verified_at == NOW
    assert verified.verification_reference == "local-fixture:recruiter"
    assert unknown == missing
    assert unknown.verification_status is IdentityVerificationStatus.UNVERIFIED
    assert unknown.user_id is None
    assert unknown.role is None


def test_fixture_loader_rejects_duplicate_users(tmp_path: Path) -> None:
    malformed = tmp_path / "users.yaml"
    malformed.write_text(
        """fixture_kind: synthetic_local_identity_test_harness
policy_status: provisional_human_review_required
users:
  - fixture_id: unverified
    identity:
      verification_status: unverified
  - fixture_id: unverified
    identity:
      verification_status: unverified
""",
        encoding="utf-8",
    )

    with pytest.raises(FixtureConfigurationError, match="user IDs must be unique"):
        load_local_fixture_users(malformed)


def test_fixture_loader_rejects_authorization_for_unverified_identity(tmp_path: Path) -> None:
    malformed = tmp_path / "users.yaml"
    malformed.write_text(
        """fixture_kind: synthetic_local_identity_test_harness
policy_status: provisional_human_review_required
users:
  - fixture_id: unverified
    identity:
      verification_status: unverified
    authorization:
      source: local_fixture
      adapter_response_id: fixture-authz-unverified
      app_id: orka_ats
      app_access: false
""",
        encoding="utf-8",
    )

    with pytest.raises(FixtureConfigurationError, match="cannot carry authorization facts"):
        load_local_fixture_users(malformed)
