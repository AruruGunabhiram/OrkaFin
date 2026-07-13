"""Request-scoped, permission-filtered candidate summary contracts."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, ClassVar, Literal

from pydantic import Field, model_validator

from orkafin.domain.base import (
    DataClassification,
    DataOwner,
    DomainModel,
    HandlingRule,
    Identifier,
    ModelDataPolicy,
    PersistencePolicy,
    SensitiveFieldPolicy,
    ShortText,
    UtcDatetime,
)
from orkafin.domain.identifiers import Permission, RequestId, SafeReference


class CandidateFieldSensitivity(StrEnum):
    """Owning-application classification for a returned candidate field."""

    STANDARD = "standard"
    SENSITIVE = "sensitive"
    RESTRICTED = "restricted"


class CandidateTextValue(DomainModel):
    """Bounded text returned for one visible field."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKA_ATS,
        classification=DataClassification.RESTRICTED,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
    )

    kind: Literal["text"] = "text"
    value: ShortText


class CandidateDateValue(DomainModel):
    """Calendar-date candidate value without invented timezone semantics."""

    data_policy: ClassVar[ModelDataPolicy] = CandidateTextValue.data_policy

    kind: Literal["date"] = "date"
    value: date


class CandidateTimestampValue(DomainModel):
    """UTC candidate timestamp value."""

    data_policy: ClassVar[ModelDataPolicy] = CandidateTextValue.data_policy

    kind: Literal["timestamp"] = "timestamp"
    value: UtcDatetime


class CandidateNumberValue(DomainModel):
    """Strict numeric candidate value."""

    data_policy: ClassVar[ModelDataPolicy] = CandidateTextValue.data_policy

    kind: Literal["number"] = "number"
    value: int | float


class CandidateIntegerValue(DomainModel):
    """Strict integer candidate value preserving adapter type information."""

    data_policy: ClassVar[ModelDataPolicy] = CandidateTextValue.data_policy

    kind: Literal["integer"] = "integer"
    value: int


class CandidateBooleanValue(DomainModel):
    """Strict boolean candidate value."""

    data_policy: ClassVar[ModelDataPolicy] = CandidateTextValue.data_policy

    kind: Literal["boolean"] = "boolean"
    value: bool


class CandidateReferenceValue(DomainModel):
    """Safe internal candidate reference without credentials or query data."""

    data_policy: ClassVar[ModelDataPolicy] = CandidateTextValue.data_policy

    kind: Literal["reference"] = "reference"
    value: SafeReference


CandidateFieldValue = Annotated[
    CandidateTextValue
    | CandidateDateValue
    | CandidateTimestampValue
    | CandidateIntegerValue
    | CandidateNumberValue
    | CandidateBooleanValue
    | CandidateReferenceValue,
    Field(discriminator="kind"),
]


class VisibleCandidateField(DomainModel):
    """One field that OrkaATS has explicitly allowed for this response."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKA_ATS,
        classification=DataClassification.RESTRICTED,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
        sensitive_fields=(
            SensitiveFieldPolicy(
                field_name="value",
                classification=DataClassification.RESTRICTED,
                rules=(HandlingRule.MINIMIZE, HandlingRule.REDACT_FROM_LOGS),
            ),
        ),
    )

    field_id: Identifier
    label: ShortText
    sensitivity: CandidateFieldSensitivity
    visibility: Literal["visible"] = "visible"
    value: CandidateFieldValue


class CandidateVisibilitySummary(DomainModel):
    """Safe redaction counts that never enumerate hidden field IDs or values."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKA_ATS,
        classification=DataClassification.CONFIDENTIAL,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
    )

    visible_field_count: int = Field(ge=0, le=100)
    redacted_field_count: int = Field(ge=0, le=100)
    redaction_applied: bool
    explanation_code: Literal[
        "all_requested_fields_visible",
        "field_permissions_applied",
        "minimum_summary_only",
    ]

    @model_validator(mode="after")
    def match_redaction_flag(self) -> CandidateVisibilitySummary:
        if self.redaction_applied != (self.redacted_field_count > 0):
            raise ValueError("redaction_applied must match the redacted field count")
        return self


class CandidateNotesExcerpt(DomainModel):
    """Exceptional, explicitly permitted notes excerpt; never trusted as instruction."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKA_ATS,
        classification=DataClassification.RESTRICTED,
        persistence=PersistencePolicy.NEVER,
        sensitive_fields=(
            SensitiveFieldPolicy(
                field_name="content",
                classification=DataClassification.RESTRICTED,
                rules=(
                    HandlingRule.MINIMIZE,
                    HandlingRule.REDACT_FROM_LOGS,
                    HandlingRule.NEVER_PERSIST,
                    HandlingRule.OMIT_BY_DEFAULT,
                ),
            ),
        ),
    )

    content: Annotated[str, Field(min_length=1, max_length=1_000, strict=True)]
    trust_label: Literal["untrusted_content"] = "untrusted_content"
    sensitivity_label: Literal["sensitive_candidate_notes"] = "sensitive_candidate_notes"
    included_by_explicit_permission: Permission


class CandidateSummary(DomainModel):
    """Controlled OrkaATS view; explicitly not an OrkaFin persistence model."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKA_ATS,
        classification=DataClassification.RESTRICTED,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
        sensitive_fields=(
            SensitiveFieldPolicy(
                field_name="visible_fields",
                classification=DataClassification.RESTRICTED,
                rules=(HandlingRule.MINIMIZE, HandlingRule.REDACT_FROM_LOGS),
            ),
            SensitiveFieldPolicy(
                field_name="notes_excerpt",
                classification=DataClassification.RESTRICTED,
                rules=(
                    HandlingRule.OMIT_BY_DEFAULT,
                    HandlingRule.REDACT_FROM_LOGS,
                    HandlingRule.NEVER_PERSIST,
                ),
            ),
        ),
    )
    model_config = {
        **DomainModel.model_config,
        "json_schema_extra": {
            "examples": [
                {
                    "schema_version": "v1",
                    "candidate_id": "CAND-1001",
                    "visible_fields": [
                        {
                            "schema_version": "v1",
                            "field_id": "display_name",
                            "label": "Candidate name",
                            "sensitivity": "standard",
                            "visibility": "visible",
                            "value": {
                                "schema_version": "v1",
                                "kind": "text",
                                "value": "Sample Candidate",
                            },
                        }
                    ],
                    "visibility": {
                        "schema_version": "v1",
                        "visible_field_count": 1,
                        "redacted_field_count": 2,
                        "redaction_applied": True,
                        "explanation_code": "field_permissions_applied",
                    },
                    "source_adapter_response_id": "adapter-response-001",
                    "valid_for_request_id": "00000000-0000-4000-8000-000000000001",
                    "retrieved_at": "2026-07-13T20:00:00Z",
                }
            ]
        },
    }

    candidate_id: Identifier
    visible_fields: tuple[VisibleCandidateField, ...] = Field(max_length=100)
    visibility: CandidateVisibilitySummary
    notes_excerpt: CandidateNotesExcerpt | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_adapter_response_id: Identifier
    valid_for_request_id: RequestId
    retrieved_at: UtcDatetime

    @model_validator(mode="after")
    def match_visible_count(self) -> CandidateSummary:
        if self.visibility.visible_field_count != len(self.visible_fields):
            raise ValueError("visible_field_count must match visible_fields")
        if len({field.field_id for field in self.visible_fields}) != len(self.visible_fields):
            raise ValueError("candidate summary field IDs must be unique")
        return self
