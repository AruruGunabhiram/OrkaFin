"""Validated scalar value objects used across domain boundaries."""

from __future__ import annotations

from typing import Annotated, ClassVar
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import ConfigDict, RootModel, StringConstraints, field_validator

from orkafin.domain.base import (
    DataClassification,
    DataOwner,
    ModelDataPolicy,
    PersistencePolicy,
)

CanonicalUuidText = Annotated[
    str,
    StringConstraints(
        min_length=36,
        max_length=36,
        pattern=(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
            r"[0-9a-f]{4}-[0-9a-f]{12}$"
        ),
        strict=True,
    ),
]
PermissionText = Annotated[
    str,
    StringConstraints(
        min_length=3,
        max_length=96,
        pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$",
        strict=True,
    ),
]
SafeReferenceText = Annotated[
    str,
    StringConstraints(min_length=10, max_length=256, strip_whitespace=True, strict=True),
]
Sha256Text = Annotated[
    str,
    StringConstraints(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$", strict=True),
]
IdempotencyKeyText = Annotated[
    str,
    StringConstraints(
        min_length=16,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
        strict=True,
    ),
]


class _StrictRootModel(RootModel[str]):
    model_config = ConfigDict(frozen=True, strict=True)
    data_policy: ClassVar[ModelDataPolicy]


class RequestId(RootModel[CanonicalUuidText]):
    """Canonical UUID request identifier, serialized as a plain string."""

    model_config = ConfigDict(frozen=True, strict=True)
    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.INTERNAL,
        persistence=PersistencePolicy.VALUE_OBJECT,
    )

    @field_validator("root")
    @classmethod
    def require_canonical_uuid(cls, value: str) -> str:
        parsed = UUID(value)
        if str(parsed) != value:
            raise ValueError("request ID must be a lowercase canonical UUID")
        return value


class CorrelationId(RequestId):
    """Canonical UUID used to correlate work beyond a single request."""


class Permission(RootModel[PermissionText]):
    """Namespaced owning-application permission such as ``candidate.view``."""

    model_config = ConfigDict(frozen=True, strict=True)
    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.OWNING_APPLICATION,
        classification=DataClassification.CONFIDENTIAL,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
    )


class SafeReference(RootModel[SafeReferenceText]):
    """Non-secret internal source URI that cannot contain query data or credentials."""

    model_config = ConfigDict(frozen=True, strict=True)
    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.SOURCE_DECLARED,
        classification=DataClassification.INTERNAL,
        persistence=PersistencePolicy.VALUE_OBJECT,
    )

    @field_validator("root")
    @classmethod
    def require_internal_reference(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"adapter", "app", "catalog", "knowledge"}:
            raise ValueError("safe reference must use an approved internal URI scheme")
        if not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("safe reference must identify an internal owner without credentials")
        if parsed.query or parsed.fragment:
            raise ValueError("safe reference must not contain query or fragment data")
        if not parsed.path or parsed.path == "/" or ".." in parsed.path.split("/"):
            raise ValueError("safe reference must contain a non-traversing resource path")
        return value


class Sha256Digest(RootModel[Sha256Text]):
    """Lowercase SHA-256 digest value."""

    model_config = ConfigDict(frozen=True, strict=True)
    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.SECRET,
        persistence=PersistencePolicy.ORKAFIN_ALLOWED,
    )


class IdempotencyKey(RootModel[IdempotencyKeyText]):
    """Bounded replay-safe key passed through an owning adapter."""

    model_config = ConfigDict(frozen=True, strict=True)
    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.CONFIDENTIAL,
        persistence=PersistencePolicy.ORKAFIN_ALLOWED,
    )
