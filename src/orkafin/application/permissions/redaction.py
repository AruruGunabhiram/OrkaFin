"""Candidate field redaction driven only by trusted authorization facts."""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal

from pydantic import Field, model_validator

from orkafin.application.permissions.evaluator import PermissionEvaluator
from orkafin.application.permissions.models import (
    AuthorizationContext,
    AuthorizationDecision,
)
from orkafin.domain.base import (
    DataClassification,
    DataOwner,
    DomainModel,
    HandlingRule,
    Identifier,
    LowercaseIdentifier,
    ModelDataPolicy,
    PersistencePolicy,
    SensitiveFieldPolicy,
    ShortText,
    UtcDatetime,
)
from orkafin.domain.candidate import (
    CandidateFieldSensitivity,
    CandidateFieldValue,
    CandidateNotesExcerpt,
    CandidateSummary,
    CandidateVisibilitySummary,
    VisibleCandidateField,
)
from orkafin.domain.context import SelectedEntityRef
from orkafin.domain.identifiers import Permission, RequestId


class CandidateSourceField(DomainModel):
    """One request-scoped adapter field before defense-in-depth redaction."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKA_ATS,
        classification=DataClassification.RESTRICTED,
        persistence=PersistencePolicy.NEVER,
        sensitive_fields=(
            SensitiveFieldPolicy(
                field_name="value",
                classification=DataClassification.RESTRICTED,
                rules=(
                    HandlingRule.MINIMIZE,
                    HandlingRule.REDACT_FROM_LOGS,
                    HandlingRule.NEVER_PERSIST,
                ),
            ),
        ),
    )

    field_id: Identifier
    label: ShortText
    sensitivity: CandidateFieldSensitivity
    value: CandidateFieldValue


class CandidateSourceNotes(DomainModel):
    """Sensitive untrusted notes supplied only at a controlled adapter boundary."""

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
                    HandlingRule.OMIT_BY_DEFAULT,
                    HandlingRule.REDACT_FROM_LOGS,
                    HandlingRule.NEVER_PERSIST,
                ),
            ),
        ),
    )

    trust_label: Literal["untrusted_content"] = "untrusted_content"
    content: Annotated[str, Field(min_length=1, max_length=1_000, strict=True)]


class CandidateRedactionInput(DomainModel):
    """Request-scoped candidate input that must never be stored or logged."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKA_ATS,
        classification=DataClassification.RESTRICTED,
        persistence=PersistencePolicy.NEVER,
        sensitive_fields=(
            SensitiveFieldPolicy(
                field_name="fields",
                classification=DataClassification.RESTRICTED,
                rules=(HandlingRule.MINIMIZE, HandlingRule.REDACT_FROM_LOGS),
            ),
            SensitiveFieldPolicy(
                field_name="notes",
                classification=DataClassification.RESTRICTED,
                rules=(HandlingRule.OMIT_BY_DEFAULT, HandlingRule.NEVER_PERSIST),
            ),
        ),
    )

    app_id: LowercaseIdentifier
    candidate_id: Identifier
    fields: tuple[CandidateSourceField, ...] = Field(max_length=100)
    notes: CandidateSourceNotes | None = None

    @model_validator(mode="after")
    def require_unique_fields(self) -> CandidateRedactionInput:
        field_ids = tuple(field.field_id for field in self.fields)
        if len(field_ids) != len(set(field_ids)):
            raise ValueError("candidate source field IDs must be unique")
        return self


class CandidateRedactionResult(DomainModel):
    """Summary when authorized, or a value-free safe denial decision."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.RESTRICTED,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
    )

    decision: AuthorizationDecision
    summary: CandidateSummary | None = None

    @model_validator(mode="after")
    def match_decision_to_summary(self) -> CandidateRedactionResult:
        if self.decision.allowed != (self.summary is not None):
            raise ValueError("authorized redaction must return a summary and denial must not")
        return self


class CandidateSummaryRedactor:
    """Create the established CandidateSummary contract from permitted fields only."""

    _NOTES_FIELD_ID = "notes_excerpt"

    def __init__(
        self,
        evaluator: PermissionEvaluator,
        *,
        candidate_view_permission: Permission,
        candidate_notes_permission: Permission,
    ) -> None:
        self._evaluator = evaluator
        self._candidate_view_permission = candidate_view_permission
        self._candidate_notes_permission = candidate_notes_permission

    def redact(
        self,
        source: CandidateRedactionInput,
        *,
        context: AuthorizationContext,
        request_id: RequestId,
        retrieved_at: UtcDatetime,
    ) -> CandidateRedactionResult:
        """Return no candidate payload unless record access is explicitly allowed."""
        record = SelectedEntityRef(
            app_id=source.app_id,
            entity_type="candidate",
            entity_id=source.candidate_id,
        )
        record_decision = self._evaluator.check_record(
            context,
            record=record,
            required_permission=self._candidate_view_permission,
        )
        if not record_decision.allowed:
            return CandidateRedactionResult(decision=record_decision)

        visible_fields: list[VisibleCandidateField] = []
        redacted_field_count = 0
        for field in source.fields:
            decision = self._evaluator.check_field(
                context,
                record=record,
                field_id=field.field_id,
                required_permission=self._candidate_view_permission,
            )
            if decision.allowed:
                visible_fields.append(
                    VisibleCandidateField(
                        field_id=field.field_id,
                        label=field.label,
                        sensitivity=field.sensitivity,
                        value=field.value,
                    )
                )
            else:
                redacted_field_count += 1

        notes_excerpt = None
        if source.notes is not None:
            notes_decision = self._evaluator.check_field(
                context,
                record=record,
                field_id=self._NOTES_FIELD_ID,
                required_permission=self._candidate_notes_permission,
            )
            if notes_decision.allowed:
                notes_excerpt = CandidateNotesExcerpt(
                    content=source.notes.content,
                    included_by_explicit_permission=self._candidate_notes_permission,
                )

        explanation_code: Literal[
            "all_requested_fields_visible",
            "field_permissions_applied",
            "minimum_summary_only",
        ]
        if redacted_field_count == 0:
            explanation_code = "all_requested_fields_visible"
        elif visible_fields:
            explanation_code = "field_permissions_applied"
        else:
            explanation_code = "minimum_summary_only"

        facts = context.facts
        assert facts is not None
        summary = CandidateSummary(
            candidate_id=source.candidate_id,
            visible_fields=tuple(visible_fields),
            visibility=CandidateVisibilitySummary(
                visible_field_count=len(visible_fields),
                redacted_field_count=redacted_field_count,
                redaction_applied=redacted_field_count > 0,
                explanation_code=explanation_code,
            ),
            notes_excerpt=notes_excerpt,
            source_adapter_response_id=facts.adapter_response_id,
            valid_for_request_id=request_id,
            retrieved_at=retrieved_at,
        )
        return CandidateRedactionResult(decision=record_decision, summary=summary)
