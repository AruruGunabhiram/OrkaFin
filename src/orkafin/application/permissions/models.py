"""Typed trusted authorization facts and safe decisions for application services."""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar, Literal

from pydantic import Field, field_validator, model_validator

from orkafin.domain.base import (
    DataClassification,
    DataOwner,
    DomainModel,
    Identifier,
    LowercaseIdentifier,
    ModelDataPolicy,
    PersistencePolicy,
    ShortText,
)
from orkafin.domain.context import SelectedEntityRef, UserIdentity
from orkafin.domain.identifiers import Permission


class AuthorizationSource(StrEnum):
    """Trusted source that produced request-scoped authorization facts."""

    LOCAL_FIXTURE = "local_fixture"
    APPLICATION_ADAPTER = "application_adapter"


class RecordVisibilityGrant(DomainModel):
    """Adapter-verified visibility for one record and its explicitly allowed fields."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.OWNING_APPLICATION,
        classification=DataClassification.RESTRICTED,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
    )

    record: SelectedEntityRef
    visible_field_ids: tuple[Identifier, ...] = Field(default=(), max_length=100)

    @field_validator("visible_field_ids")
    @classmethod
    def require_unique_fields(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("visible field IDs must be unique")
        return values


class TrustedAuthorizationFacts(DomainModel):
    """Facts verified by the owning adapter or the explicit local test harness."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.OWNING_APPLICATION,
        classification=DataClassification.RESTRICTED,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
    )

    trust_label: Literal["trusted_application_authorization_facts"] = (
        "trusted_application_authorization_facts"
    )
    source: AuthorizationSource
    adapter_response_id: Identifier
    app_id: LowercaseIdentifier
    app_access: bool
    allowed_page_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=100)
    permissions: tuple[Permission, ...] = Field(default=(), max_length=100)
    records: tuple[RecordVisibilityGrant, ...] = Field(default=(), max_length=100)
    available_action_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=50)

    @model_validator(mode="after")
    def validate_trusted_facts(self) -> TrustedAuthorizationFacts:
        collections = (
            (self.allowed_page_ids, "allowed page IDs"),
            (tuple(permission.root for permission in self.permissions), "permissions"),
            (self.available_action_ids, "available action IDs"),
            (
                tuple(
                    (grant.record.app_id, grant.record.entity_type, grant.record.entity_id)
                    for grant in self.records
                ),
                "record visibility grants",
            ),
        )
        for values, label in collections:
            if len(values) != len(set(values)):
                raise ValueError(f"{label} must be unique")
        if any(grant.record.app_id != self.app_id for grant in self.records):
            raise ValueError("record grants must belong to the authorized app")
        if not self.app_access and any(
            (self.allowed_page_ids, self.permissions, self.records, self.available_action_ids)
        ):
            raise ValueError("denied app access cannot carry narrower authorization grants")
        return self


class AuthorizationContext(DomainModel):
    """Verified identity and independently trusted application authorization facts."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.RESTRICTED,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
    )

    identity: UserIdentity | None = None
    facts: TrustedAuthorizationFacts | None = None


class AuthorizationCheck(StrEnum):
    """Authorization scope evaluated without route-specific logic."""

    APP = "app"
    PAGE = "page"
    RECORD = "record"
    FIELD = "field"
    PERMISSION = "permission"
    ACTION = "action"


class AuthorizationDecisionCode(StrEnum):
    """Stable safe decision codes suitable for bounded audits and user messages."""

    ALLOWED = "allowed"
    IDENTITY_MISSING = "identity_missing"
    IDENTITY_UNVERIFIED = "identity_unverified"
    TRUSTED_FACTS_MISSING = "trusted_facts_missing"
    APP_ACCESS_DENIED = "app_access_denied"
    PAGE_ACCESS_DENIED = "page_access_denied"
    RECORD_ACCESS_DENIED = "record_access_denied"
    FIELD_ACCESS_DENIED = "field_access_denied"
    ACTION_ACCESS_DENIED = "action_access_denied"
    PERMISSION_MISSING = "permission_missing"
    PERMISSION_UNKNOWN = "permission_unknown"


class AuthorizationDecision(DomainModel):
    """A value-free decision: no requested IDs, hidden fields, or claims are echoed."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.INTERNAL,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
    )

    check: AuthorizationCheck
    allowed: bool
    code: AuthorizationDecisionCode
    safe_message: ShortText

    @model_validator(mode="after")
    def match_allowed_code(self) -> AuthorizationDecision:
        if self.allowed != (self.code is AuthorizationDecisionCode.ALLOWED):
            raise ValueError("allowed decisions must use the allowed code and denials must not")
        return self
