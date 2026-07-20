from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from orkafin.application.auth import (
    IdentityResolutionRequest,
    LocalFixtureIdentityResolver,
    LocalFixtureUserSet,
    load_local_fixture_users,
)
from orkafin.application.permissions import (
    AuthorizationContext,
    AuthorizationDecisionCode,
    CandidateRedactionInput,
    CandidateSourceField,
    CandidateSourceNotes,
    CandidateSummaryRedactor,
    PermissionEvaluator,
    RecordVisibilityGrant,
    TrustedAuthorizationFacts,
)
from orkafin.domain.candidate import (
    CandidateDateValue,
    CandidateFieldSensitivity,
    CandidateTextValue,
    CandidateTimestampValue,
)
from orkafin.domain.context import (
    ClientContextHint,
    IdentityVerificationStatus,
    SelectedEntityRef,
)
from orkafin.domain.identifiers import Permission, RequestId

NOW = datetime(2026, 7, 13, 20, 0, tzinfo=UTC)
REQUEST_ID = RequestId(root="00000000-0000-4000-8000-000000000071")
FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "users.yaml"
VIEW = Permission(root="candidate.view")
CREATE = Permission(root="candidate.create")
NOTES = Permission(root="candidate.notes.view")
UPDATE_START_DATE = Permission(root="candidate.update_start_date")
KNOWN_PERMISSIONS = (VIEW, CREATE, NOTES, UPDATE_START_DATE)


def fixture_users() -> LocalFixtureUserSet:
    return load_local_fixture_users(FIXTURE_PATH)


def resolver() -> LocalFixtureIdentityResolver:
    return LocalFixtureIdentityResolver(fixture_users(), clock=lambda: NOW)


def evaluator() -> PermissionEvaluator:
    return PermissionEvaluator(known_permissions=KNOWN_PERMISSIONS)


def context_for(fixture_id: str) -> AuthorizationContext:
    fixtures = fixture_users()
    fixture = fixtures.find_user(fixture_id)
    assert fixture is not None
    return AuthorizationContext(
        identity=resolver().resolve_identity(
            IdentityResolutionRequest(trusted_subject_id=fixture_id)
        ),
        facts=fixture.authorization,
    )


def candidate_record(candidate_id: str = "CAND-1001") -> SelectedEntityRef:
    return SelectedEntityRef(
        app_id="orka_ats",
        entity_type="candidate",
        entity_id=candidate_id,
    )


def candidate_source(candidate_id: str = "CAND-1001") -> CandidateRedactionInput:
    return CandidateRedactionInput(
        app_id="orka_ats",
        candidate_id=candidate_id,
        fields=(
            CandidateSourceField(
                field_id="display_name",
                label="Candidate name",
                sensitivity=CandidateFieldSensitivity.STANDARD,
                value=CandidateTextValue(value="Synthetic Candidate"),
            ),
            CandidateSourceField(
                field_id="recruitment_stage",
                label="Recruitment stage",
                sensitivity=CandidateFieldSensitivity.STANDARD,
                value=CandidateTextValue(value="Synthetic Stage"),
            ),
            CandidateSourceField(
                field_id="recruiter",
                label="Recruiter",
                sensitivity=CandidateFieldSensitivity.STANDARD,
                value=CandidateTextValue(value="Synthetic Recruiter"),
            ),
            CandidateSourceField(
                field_id="email",
                label="Email",
                sensitivity=CandidateFieldSensitivity.SENSITIVE,
                value=CandidateTextValue(value="candidate.fixture@example.invalid"),
            ),
            CandidateSourceField(
                field_id="start_date",
                label="Start date",
                sensitivity=CandidateFieldSensitivity.SENSITIVE,
                value=CandidateDateValue(value=date(2026, 8, 1)),
            ),
            CandidateSourceField(
                field_id="resume_link",
                label="Resume link",
                sensitivity=CandidateFieldSensitivity.RESTRICTED,
                value=CandidateTextValue(value="app://synthetic-resume-reference"),
            ),
            CandidateSourceField(
                field_id="created_at",
                label="Created at",
                sensitivity=CandidateFieldSensitivity.SENSITIVE,
                value=CandidateTimestampValue(value=NOW),
            ),
            CandidateSourceField(
                field_id="updated_at",
                label="Updated at",
                sensitivity=CandidateFieldSensitivity.SENSITIVE,
                value=CandidateTimestampValue(value=NOW),
            ),
            CandidateSourceField(
                field_id="api_secret",
                label="Secret",
                sensitivity=CandidateFieldSensitivity.RESTRICTED,
                value=CandidateTextValue(value="SYNTHETIC-HIDDEN-VALUE"),
            ),
        ),
        notes=CandidateSourceNotes(content="SYNTHETIC-PRIVATE-NOTE"),
    )


def redactor() -> CandidateSummaryRedactor:
    return CandidateSummaryRedactor(
        evaluator(),
        candidate_view_permission=VIEW,
        candidate_notes_permission=NOTES,
    )


def test_client_navigation_cannot_select_or_elevate_fixture_identity() -> None:
    hint = ClientContextHint(
        app_id="orka_ats",
        page="candidate_profile",
    )
    identity = resolver().resolve_identity(
        IdentityResolutionRequest(
            trusted_subject_id="limited_viewer",
            client_hint=hint,
        )
    )
    limited_fixture = fixture_users().find_user("limited_viewer")
    assert limited_fixture is not None
    context = AuthorizationContext(
        identity=identity,
        facts=limited_fixture.authorization,
    )

    assert identity.role is not None
    assert identity.role.role_id == "limited_viewer"
    assert identity.email == "limited.fixture@example.invalid"
    action = evaluator().check_action(
        context,
        app_id="orka_ats",
        action_id="candidate.update_start_date",
        required_permission=UPDATE_START_DATE,
        target=candidate_record(),
    )
    result = redactor().redact(
        candidate_source(),
        context=context,
        request_id=REQUEST_ID,
        retrieved_at=NOW,
    )

    assert action.code is AuthorizationDecisionCode.PERMISSION_MISSING
    assert result.summary is not None
    assert {field.field_id for field in result.summary.visible_fields} == {
        "display_name",
        "recruiter",
        "recruitment_stage",
    }


def test_missing_and_unverified_identity_receive_no_candidate_data() -> None:
    admin = fixture_users().find_user("admin")
    assert admin is not None
    missing_context = AuthorizationContext(identity=None, facts=admin.authorization)
    missing = redactor().redact(
        candidate_source(),
        context=missing_context,
        request_id=REQUEST_ID,
        retrieved_at=NOW,
    )
    unverified_identity = resolver().resolve_identity(
        IdentityResolutionRequest(trusted_subject_id="unverified")
    )
    unverified = redactor().redact(
        candidate_source(),
        context=AuthorizationContext(identity=unverified_identity),
        request_id=REQUEST_ID,
        retrieved_at=NOW,
    )

    assert missing.summary is None
    assert missing.decision.code is AuthorizationDecisionCode.IDENTITY_MISSING
    assert unverified_identity.verification_status is IdentityVerificationStatus.UNVERIFIED
    assert unverified.summary is None
    assert unverified.decision.code is AuthorizationDecisionCode.IDENTITY_UNVERIFIED
    assert "SYNTHETIC-HIDDEN-VALUE" not in unverified.model_dump_json()
    assert "SYNTHETIC-PRIVATE-NOTE" not in unverified.model_dump_json()


def test_record_visibility_is_explicit_and_independent_of_recruiter_role() -> None:
    context = context_for("recruiter")

    allowed = evaluator().check_record(
        context,
        record=candidate_record("CAND-1001"),
        required_permission=VIEW,
    )
    denied = evaluator().check_record(
        context,
        record=candidate_record("CAND-1002"),
        required_permission=VIEW,
    )

    assert allowed.allowed is True
    assert denied.allowed is False
    assert denied.code is AuthorizationDecisionCode.RECORD_ACCESS_DENIED
    assert "CAND-1002" not in denied.model_dump_json()


def test_candidate_summary_redacts_fields_by_exact_trusted_grants() -> None:
    result = redactor().redact(
        candidate_source(),
        context=context_for("limited_viewer"),
        request_id=REQUEST_ID,
        retrieved_at=NOW,
    )

    assert result.summary is not None
    assert tuple(field.field_id for field in result.summary.visible_fields) == (
        "display_name",
        "recruitment_stage",
        "recruiter",
    )
    assert result.summary.visibility.visible_field_count == 3
    assert result.summary.visibility.redacted_field_count == 6
    assert result.summary.visibility.explanation_code == "field_permissions_applied"
    assert result.summary.notes_excerpt is None
    serialized = result.model_dump_json()
    assert "api_secret" not in serialized
    assert "SYNTHETIC-HIDDEN-VALUE" not in serialized
    assert "SYNTHETIC-PRIVATE-NOTE" not in serialized
    assert "candidate.fixture@example.invalid" not in serialized


def test_admin_is_still_redacted_and_notes_are_excluded_by_default() -> None:
    result = redactor().redact(
        candidate_source(),
        context=context_for("admin"),
        request_id=REQUEST_ID,
        retrieved_at=NOW,
    )

    assert result.summary is not None
    assert len(result.summary.visible_fields) == 8
    assert result.summary.visibility.redacted_field_count == 1
    assert result.summary.notes_excerpt is None
    serialized = result.model_dump_json()
    assert "api_secret" not in serialized
    assert "SYNTHETIC-HIDDEN-VALUE" not in serialized
    assert "SYNTHETIC-PRIVATE-NOTE" not in serialized


def test_notes_require_both_specific_permission_and_field_grant() -> None:
    base_context = context_for("limited_viewer")
    base_facts = base_context.facts
    assert base_facts is not None
    original_grant = base_facts.records[0]
    facts = TrustedAuthorizationFacts(
        source=base_facts.source,
        adapter_response_id="fixture-authz-explicit-notes",
        app_id=base_facts.app_id,
        app_access=True,
        allowed_page_ids=base_facts.allowed_page_ids,
        permissions=(*base_facts.permissions, NOTES),
        records=(
            RecordVisibilityGrant(
                record=original_grant.record,
                visible_field_ids=(*original_grant.visible_field_ids, "notes_excerpt"),
            ),
        ),
        available_action_ids=(),
    )
    context = AuthorizationContext(identity=base_context.identity, facts=facts)

    result = redactor().redact(
        candidate_source(),
        context=context,
        request_id=REQUEST_ID,
        retrieved_at=NOW,
    )

    assert result.summary is not None
    assert result.summary.notes_excerpt is not None
    assert result.summary.notes_excerpt.trust_label == "untrusted_content"
    assert result.summary.notes_excerpt.sensitivity_label == "sensitive_candidate_notes"
    assert result.summary.notes_excerpt.included_by_explicit_permission == NOTES


def test_action_requires_permission_availability_and_record_visibility() -> None:
    recruiter = evaluator().check_action(
        context_for("recruiter"),
        app_id="orka_ats",
        action_id="candidate.update_start_date",
        required_permission=UPDATE_START_DATE,
        target=candidate_record(),
    )
    admin = evaluator().check_action(
        context_for("admin"),
        app_id="orka_ats",
        action_id="candidate.update_start_date",
        required_permission=UPDATE_START_DATE,
        target=candidate_record(),
    )

    assert recruiter.code is AuthorizationDecisionCode.PERMISSION_MISSING
    assert admin.code is AuthorizationDecisionCode.ALLOWED


def test_unknown_permissions_and_omitted_trusted_facts_deny_by_default() -> None:
    admin_context = context_for("admin")
    unknown = evaluator().check_permission(
        admin_context,
        app_id="orka_ats",
        permission=Permission(root="candidate.export"),
    )
    role_only = evaluator().check_app(
        AuthorizationContext(identity=admin_context.identity),
        app_id="orka_ats",
    )

    assert unknown.code is AuthorizationDecisionCode.PERMISSION_UNKNOWN
    assert role_only.code is AuthorizationDecisionCode.TRUSTED_FACTS_MISSING


def test_page_and_safe_denial_messages_do_not_reveal_requested_scope() -> None:
    context = context_for("limited_viewer")
    page = evaluator().check_page(
        context,
        app_id="orka_ats",
        page_id="candidate_creation_form",
    )
    field = evaluator().check_field(
        context,
        record=candidate_record(),
        field_id="api_secret",
        required_permission=VIEW,
    )

    assert page.code is AuthorizationDecisionCode.PAGE_ACCESS_DENIED
    assert field.code is AuthorizationDecisionCode.FIELD_ACCESS_DENIED
    serialized = f"{page.model_dump_json()} {field.model_dump_json()}"
    for forbidden in (
        "candidate_creation_form",
        "api_secret",
        "candidate.view",
        "CAND-1001",
        "SYNTHETIC-HIDDEN-VALUE",
    ):
        assert forbidden not in serialized
