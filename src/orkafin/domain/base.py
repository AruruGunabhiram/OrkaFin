"""Shared validation, ownership, and data-handling policy for domain contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated, ClassVar, Literal

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, StringConstraints

SchemaVersion = Literal["v1"]

Identifier = Annotated[
    str,
    StringConstraints(
        min_length=3,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
        strict=True,
    ),
]
LowercaseIdentifier = Annotated[
    str,
    StringConstraints(
        min_length=3,
        max_length=64,
        pattern=r"^[a-z][a-z0-9]*(?:[._:-][a-z0-9]+)*$",
        strict=True,
    ),
]
ShortText = Annotated[
    str,
    StringConstraints(min_length=1, max_length=500, strip_whitespace=True, strict=True),
]
LongText = Annotated[
    str,
    StringConstraints(min_length=1, max_length=16_000, strip_whitespace=True, strict=True),
]
EmailAddress = Annotated[
    str,
    StringConstraints(
        min_length=3,
        max_length=254,
        pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
        strict=True,
    ),
]
SemanticVersion = Annotated[
    str,
    StringConstraints(
        min_length=5,
        max_length=32,
        pattern=r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$",
        strict=True,
    ),
]
Revision = Annotated[
    str,
    StringConstraints(
        min_length=2,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
        strict=True,
    ),
]


def _require_utc(value: datetime) -> datetime:
    """Reject naive or non-UTC timestamps and normalize the UTC tzinfo object."""
    if value.utcoffset() != timedelta(0):
        raise ValueError("timestamp must use UTC (offset +00:00 or Z)")
    return value


UtcDatetime = Annotated[AwareDatetime, AfterValidator(_require_utc)]


class DataOwner(StrEnum):
    """Authoritative owner of a domain payload."""

    CLIENT = "client"
    ORKAFIN = "orkafin"
    ORKA_ATS = "orka_ats"
    OWNING_APPLICATION = "owning_application"
    PRODUCT_DOCUMENTATION = "product_documentation"
    SOURCE_DECLARED = "source_declared"


class DataClassification(StrEnum):
    """Maximum sensitivity represented by a model or field."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    SECRET = "secret"


class PersistencePolicy(StrEnum):
    """Whether and where a payload may be retained."""

    VALUE_OBJECT = "value_object"
    ORKAFIN_ALLOWED = "orkafin_allowed"
    REQUEST_SCOPED_ONLY = "request_scoped_only"
    CATALOG_FILE = "catalog_file"
    NEVER = "never"


class HandlingRule(StrEnum):
    """Required handling for a sensitive field."""

    MINIMIZE = "minimize"
    REDACT_FROM_LOGS = "redact_from_logs"
    OMIT_BY_DEFAULT = "omit_by_default"
    NEVER_PERSIST = "never_persist"
    INTERNAL_ONLY = "internal_only"
    HASH_ONLY = "hash_only"


@dataclass(frozen=True, slots=True)
class SensitiveFieldPolicy:
    """Classification and mandatory handling for one model field."""

    field_name: str
    classification: DataClassification
    rules: tuple[HandlingRule, ...]


@dataclass(frozen=True, slots=True)
class ModelDataPolicy:
    """Ownership and data-handling metadata attached to every domain model."""

    owner: DataOwner
    classification: DataClassification
    persistence: PersistencePolicy
    sensitive_fields: tuple[SensitiveFieldPolicy, ...] = ()


class DomainModel(BaseModel):
    """Frozen, strict, versioned base for structured domain payloads."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
    )

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.INTERNAL,
        persistence=PersistencePolicy.NEVER,
    )

    schema_version: SchemaVersion = "v1"
