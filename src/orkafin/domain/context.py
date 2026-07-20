"""Untrusted client hints and request-scoped verified context contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar, Literal

from pydantic import Field, model_validator

from orkafin.domain.base import (
    DataClassification,
    DataOwner,
    DomainModel,
    EmailAddress,
    HandlingRule,
    Identifier,
    LowercaseIdentifier,
    ModelDataPolicy,
    PersistencePolicy,
    SemanticVersion,
    SensitiveFieldPolicy,
    ShortText,
    UtcDatetime,
)
from orkafin.domain.candidate import CandidateSummary
from orkafin.domain.identifiers import Permission, RequestId


class AppStatus(StrEnum):
    """Availability state advertised by an owning application."""

    ACTIVE = "active"
    DISABLED = "disabled"
    MAINTENANCE = "maintenance"


class AppMetadata(DomainModel):
    """Versioned metadata supplied by an owning Orka application."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.OWNING_APPLICATION,
        classification=DataClassification.INTERNAL,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
    )
    model_config = {
        **DomainModel.model_config,
        "json_schema_extra": {
            "examples": [
                {
                    "schema_version": "v1",
                    "app_id": "orka_ats",
                    "display_name": "OrkaATS",
                    "description": "Synthetic local recruiting application metadata.",
                    "app_version": "1.0.0",
                    "adapter_contract_version": "1.0.0",
                    "status": "active",
                }
            ]
        },
    }

    app_id: LowercaseIdentifier
    display_name: ShortText
    description: ShortText
    app_version: SemanticVersion
    adapter_contract_version: SemanticVersion
    status: AppStatus


class Role(DomainModel):
    """Owning-application role label; role alone never grants access."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.OWNING_APPLICATION,
        classification=DataClassification.CONFIDENTIAL,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
    )

    role_id: LowercaseIdentifier
    display_name: ShortText
    owner_app_id: LowercaseIdentifier


class WorkspaceRef(DomainModel):
    """Minimal owning-application workspace reference."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.OWNING_APPLICATION,
        classification=DataClassification.CONFIDENTIAL,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
    )

    workspace_id: Identifier
    app_id: LowercaseIdentifier
    display_name: ShortText | None = None


class SelectedEntityRef(DomainModel):
    """Minimal entity reference; it carries no visibility grant."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.OWNING_APPLICATION,
        classification=DataClassification.CONFIDENTIAL,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
    )

    app_id: LowercaseIdentifier
    entity_type: LowercaseIdentifier
    entity_id: Identifier


class ClientSelectedEntityHint(DomainModel):
    """Untrusted client-selected entity hint; never a visibility decision."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.CLIENT,
        classification=DataClassification.CONFIDENTIAL,
        persistence=PersistencePolicy.NEVER,
    )

    type: LowercaseIdentifier
    id: Identifier


class IdentityVerificationStatus(StrEnum):
    """How an identity was established for the current response."""

    UNVERIFIED = "unverified"
    LOCAL_FIXTURE_VERIFIED = "local_fixture_verified"
    ADAPTER_VERIFIED = "adapter_verified"


class UserIdentity(DomainModel):
    """Identity result from a trusted resolver, including explicit verification state."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.OWNING_APPLICATION,
        classification=DataClassification.RESTRICTED,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
        sensitive_fields=(
            SensitiveFieldPolicy(
                field_name="email",
                classification=DataClassification.RESTRICTED,
                rules=(HandlingRule.MINIMIZE, HandlingRule.REDACT_FROM_LOGS),
            ),
        ),
    )

    user_id: Identifier | None = None
    display_name: ShortText | None = None
    email: EmailAddress | None = None
    role: Role | None = None
    verification_status: IdentityVerificationStatus
    verified_at: UtcDatetime | None = None
    verification_reference: Identifier | None = None

    @model_validator(mode="after")
    def validate_verification_evidence(self) -> UserIdentity:
        if self.verification_status is IdentityVerificationStatus.UNVERIFIED:
            if any(
                value is not None
                for value in (
                    self.user_id,
                    self.display_name,
                    self.email,
                    self.role,
                    self.verified_at,
                    self.verification_reference,
                )
            ):
                raise ValueError("unverified identity must not contain identity claims")
            return self
        if self.user_id is None or self.role is None or self.verified_at is None:
            raise ValueError("verified identity requires user_id, role, and verified_at")
        if self.verification_reference is None:
            raise ValueError("verified identity requires a verification reference")
        return self


class ResolvedUserIdentity(DomainModel):
    """Verified identity facts safe to disclose in a resolved-context response."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.OWNING_APPLICATION,
        classification=DataClassification.RESTRICTED,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
        sensitive_fields=(
            SensitiveFieldPolicy(
                field_name="user_id",
                classification=DataClassification.RESTRICTED,
                rules=(HandlingRule.MINIMIZE, HandlingRule.REDACT_FROM_LOGS),
            ),
        ),
    )

    user_id: Identifier
    display_name: ShortText | None = None
    role: Role
    verification_status: IdentityVerificationStatus
    verified_at: UtcDatetime
    verification_reference: Identifier

    @model_validator(mode="after")
    def require_verified_identity(self) -> ResolvedUserIdentity:
        if self.verification_status is IdentityVerificationStatus.UNVERIFIED:
            raise ValueError("resolved response identity must be verified")
        return self

    @classmethod
    def from_verified(cls, identity: UserIdentity) -> ResolvedUserIdentity:
        """Minimize a verified internal identity without exposing its email address."""
        if (
            identity.verification_status is IdentityVerificationStatus.UNVERIFIED
            or identity.user_id is None
            or identity.role is None
            or identity.verified_at is None
            or identity.verification_reference is None
        ):
            raise ValueError("resolved response identity requires verified identity evidence")
        return cls(
            user_id=identity.user_id,
            display_name=identity.display_name,
            role=identity.role,
            verification_status=identity.verification_status,
            verified_at=identity.verified_at,
            verification_reference=identity.verification_reference,
        )


class ClientContextHint(DomainModel):
    """Browser-provided navigation and selection hints; never authorization facts."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.CLIENT,
        classification=DataClassification.CONFIDENTIAL,
        persistence=PersistencePolicy.NEVER,
    )
    model_config = {
        **DomainModel.model_config,
        "json_schema_extra": {
            "examples": [
                {
                    "schema_version": "v1",
                    "app_id": "orka_ats",
                    "page": "candidate_profile",
                    "selected_entity": {
                        "schema_version": "v1",
                        "type": "candidate",
                        "id": "CAND-1001",
                    },
                }
            ]
        },
    }

    trust_label: ClassVar[Literal["untrusted_client_hint"]] = "untrusted_client_hint"
    app_id: LowercaseIdentifier
    page: LowercaseIdentifier
    selected_entity: ClientSelectedEntityHint | None = None


class ContextVerificationSource(StrEnum):
    """Trusted resolver used to produce a resolved context."""

    LOCAL_FIXTURE = "local_fixture"
    APPLICATION_ADAPTER = "application_adapter"


class ContextComponentTrust(DomainModel):
    """Source evidence for one resolved component, never for a client hint."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.INTERNAL,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
    )

    trust_label: Literal["trusted_for_response_lifetime"] = "trusted_for_response_lifetime"
    verification_source: ContextVerificationSource
    source_response_id: Identifier


class ResolvedContextTrust(DomainModel):
    """Per-component trust and provenance for a resolved page context."""

    data_policy: ClassVar[ModelDataPolicy] = ContextComponentTrust.data_policy

    app: ContextComponentTrust
    identity: ContextComponentTrust
    page: ContextComponentTrust
    workspace: ContextComponentTrust
    selected_entity: ContextComponentTrust | None = None
    permissions: ContextComponentTrust
    available_actions: ContextComponentTrust
    available_features: ContextComponentTrust | None = None
    candidate_summary: ContextComponentTrust | None = None


class ResolvedPageContext(DomainModel):
    """Adapter/resolver-verified facts valid only for the represented response lifetime."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.OWNING_APPLICATION,
        classification=DataClassification.RESTRICTED,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
        sensitive_fields=(
            SensitiveFieldPolicy(
                field_name="identity",
                classification=DataClassification.RESTRICTED,
                rules=(HandlingRule.MINIMIZE, HandlingRule.REDACT_FROM_LOGS),
            ),
            SensitiveFieldPolicy(
                field_name="candidate_summary",
                classification=DataClassification.RESTRICTED,
                rules=(HandlingRule.MINIMIZE, HandlingRule.NEVER_PERSIST),
            ),
        ),
    )

    trust_label: Literal["verified_for_response_lifetime"] = "verified_for_response_lifetime"
    verification_source: ContextVerificationSource
    adapter_response_id: Identifier
    component_trust: ResolvedContextTrust
    request_id: RequestId
    app: AppMetadata
    page_id: LowercaseIdentifier
    identity: ResolvedUserIdentity
    workspace: WorkspaceRef
    selected_entity: SelectedEntityRef | None = None
    permissions: tuple[Permission, ...] = Field(max_length=100)
    available_feature_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=100)
    available_action_ids: tuple[LowercaseIdentifier, ...] = Field(default=(), max_length=50)
    candidate_summary: CandidateSummary | None = None
    resolved_at: UtcDatetime
    valid_until: UtcDatetime

    @model_validator(mode="after")
    def validate_verified_context(self) -> ResolvedPageContext:
        if self.identity.verification_status is IdentityVerificationStatus.UNVERIFIED:
            raise ValueError("resolved context requires a verified identity")
        if self.workspace.app_id != self.app.app_id:
            raise ValueError("workspace app must match resolved app")
        if self.identity.role.owner_app_id != self.app.app_id:
            raise ValueError("identity role owner must match resolved app")
        if self.selected_entity is not None and self.selected_entity.app_id != self.app.app_id:
            raise ValueError("selected entity app must match resolved app")
        if self.candidate_summary is not None:
            if self.selected_entity is None or self.selected_entity.entity_type != "candidate":
                raise ValueError("candidate summary requires a selected candidate reference")
            if self.candidate_summary.candidate_id != self.selected_entity.entity_id:
                raise ValueError("candidate summary must match the selected entity")
            if self.candidate_summary.valid_for_request_id != self.request_id:
                raise ValueError("candidate summary must be bound to the resolved request")
        if (self.component_trust.selected_entity is None) != (self.selected_entity is None):
            raise ValueError("selected entity trust evidence must match selected entity presence")
        if (self.component_trust.candidate_summary is None) != (self.candidate_summary is None):
            raise ValueError("candidate summary trust evidence must match summary presence")
        context_response_ids = [
            self.component_trust.app.source_response_id,
            self.component_trust.workspace.source_response_id,
        ]
        if self.component_trust.selected_entity is not None:
            context_response_ids.append(self.component_trust.selected_entity.source_response_id)
        if any(response_id != self.adapter_response_id for response_id in context_response_ids):
            raise ValueError("application context trust must match the context adapter response")
        if (
            self.candidate_summary is not None
            and self.component_trust.candidate_summary is not None
            and self.component_trust.candidate_summary.source_response_id
            != self.candidate_summary.source_adapter_response_id
        ):
            raise ValueError("candidate summary trust must match the summary adapter response")
        if self.valid_until < self.resolved_at:
            raise ValueError("valid_until must not precede resolved_at")
        if len(set(self.permissions)) != len(self.permissions):
            raise ValueError("resolved permissions must be unique")
        return self
