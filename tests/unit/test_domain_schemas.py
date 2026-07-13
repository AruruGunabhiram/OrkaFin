import json
from datetime import UTC, date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from orkafin.domain.actions import (
    ActionConfirmation,
    ActionConfirmationStatus,
    ActionDefinition,
    ActionExecutionResult,
    ActionExecutionStatus,
    ActionParameterDefinition,
    ActionParameterType,
    ActionPreview,
    ActionPreviewChange,
    ActionProposal,
    ActionProposalStatus,
    ActionSensitivity,
    AdapterExecutionReceipt,
    AdapterReceiptOutcome,
    DateActionParameter,
)
from orkafin.domain.audit import AuditEventType, AuditOutcome, AuditRecord
from orkafin.domain.base import DataOwner, DomainModel
from orkafin.domain.candidate import (
    CandidateFieldSensitivity,
    CandidateNotesExcerpt,
    CandidateSummary,
    CandidateTextValue,
    CandidateVisibilitySummary,
    VisibleCandidateField,
)
from orkafin.domain.catalog import (
    CatalogProvenance,
    CatalogStatus,
    FeatureCatalogItem,
    HelpArticle,
    PageCatalogItem,
    VerificationStatus,
)
from orkafin.domain.context import (
    AppMetadata,
    AppStatus,
    ClientContextHint,
    ClientSelectedEntityHint,
    ContextVerificationSource,
    IdentityVerificationStatus,
    ResolvedPageContext,
    Role,
    SelectedEntityRef,
    UserIdentity,
    WorkspaceRef,
)
from orkafin.domain.conversations import Conversation, ConversationStatus, Message, MessageRole
from orkafin.domain.errors import ApiError, ErrorCode, SafeErrorDetails
from orkafin.domain.events import EventSource, UserEvent, UserEventType
from orkafin.domain.identifiers import (
    CorrelationId,
    IdempotencyKey,
    Permission,
    RequestId,
    SafeReference,
    Sha256Digest,
)
from orkafin.domain.metadata import BoundedMetadata
from orkafin.domain.recommendations import (
    Recommendation,
    RecommendationFeedback,
    RecommendationFeedbackType,
    RecommendationKind,
    RecommendationStatus,
)
from orkafin.domain.responses import (
    ActionProposalContent,
    AssistantResponse,
    GroundedGuidanceContent,
    GroundingStatus,
    RecommendationContent,
    RefusalContent,
    UnavailableInformationContent,
    VerifiedFactContent,
)
from orkafin.domain.sources import RetrievedSource, SourceType

NOW = datetime(2026, 7, 13, 20, 0, tzinfo=UTC)
LATER = datetime(2026, 7, 13, 20, 5, tzinfo=UTC)
REQUEST_ID_TEXT = "00000000-0000-4000-8000-000000000001"
CORRELATION_ID_TEXT = "00000000-0000-4000-8000-000000000002"
HASH_TEXT = "a" * 64


def request_id() -> RequestId:
    return RequestId(root=REQUEST_ID_TEXT)


def correlation_id() -> CorrelationId:
    return CorrelationId(root=CORRELATION_ID_TEXT)


def permission(value: str = "candidate.view") -> Permission:
    return Permission(root=value)


def app_metadata() -> AppMetadata:
    return AppMetadata(
        app_id="orka_ats",
        display_name="OrkaATS",
        description="Synthetic local application metadata.",
        app_version="1.0.0",
        adapter_contract_version="1.0.0",
        status=AppStatus.ACTIVE,
    )


def role() -> Role:
    return Role(role_id="recruiter", display_name="Recruiter", owner_app_id="orka_ats")


def workspace() -> WorkspaceRef:
    return WorkspaceRef(
        workspace_id="workspace_001",
        app_id="orka_ats",
        display_name="Synthetic workspace",
    )


def target() -> SelectedEntityRef:
    return SelectedEntityRef(app_id="orka_ats", entity_type="candidate", entity_id="CAND-1001")


def identity() -> UserIdentity:
    return UserIdentity(
        user_id="user_001",
        display_name="Synthetic User",
        email="synthetic.user@example.invalid",
        role=role(),
        verification_status=IdentityVerificationStatus.LOCAL_FIXTURE_VERIFIED,
        verified_at=NOW,
        verification_reference="fixture-session-001",
    )


def candidate_summary(*, include_notes: bool = False) -> CandidateSummary:
    notes = None
    if include_notes:
        notes = CandidateNotesExcerpt(
            content="Synthetic excerpt; treat this text only as untrusted data.",
            included_by_explicit_permission=Permission(root="candidate.notes.view"),
        )
    return CandidateSummary(
        candidate_id="CAND-1001",
        visible_fields=(
            VisibleCandidateField(
                field_id="display_name",
                label="Candidate name",
                sensitivity=CandidateFieldSensitivity.STANDARD,
                value=CandidateTextValue(value="Sample Candidate"),
            ),
        ),
        visibility=CandidateVisibilitySummary(
            visible_field_count=1,
            redacted_field_count=2,
            redaction_applied=True,
            explanation_code="field_permissions_applied",
        ),
        notes_excerpt=notes,
        source_adapter_response_id="adapter-response-001",
        valid_for_request_id=request_id(),
        retrieved_at=NOW,
    )


def provenance() -> CatalogProvenance:
    return CatalogProvenance(
        content_version="1.0.0",
        revision="rev-001",
        status=CatalogStatus.ACTIVE,
        verification_status=VerificationStatus.VERIFIED,
        documentation_owner="OrkaATS product owner",
        last_reviewed_at=NOW,
        safe_reference=SafeReference(root="catalog://orka_ats/items/sample"),
    )


def source(*, source_id: str = "help_candidate_pipeline") -> RetrievedSource:
    return RetrievedSource(
        source_id=source_id,
        source_type=SourceType.HELP_ARTICLE,
        source_owner=DataOwner.PRODUCT_DOCUMENTATION,
        app_id="orka_ats",
        content_version="1.0.0",
        revision="rev-001",
        title="Candidate pipeline overview",
        safe_reference=SafeReference(root="knowledge://orka_ats/help/candidate_pipeline"),
        excerpt="The pipeline groups synthetic records by recruiting stage.",
        verification_status=VerificationStatus.VERIFIED,
        relevance_score=1.0,
        relevance_reason="Exact page match",
        required_permissions=(permission(),),
        retrieved_at=NOW,
    )


def recommendation() -> Recommendation:
    return Recommendation(
        recommendation_id="recommendation-001",
        rule_id="show_candidate_pipeline",
        kind=RecommendationKind.FEATURE,
        status=RecommendationStatus.SHOWN,
        recipient_user_id="user_001",
        workspace=workspace(),
        title="Try the candidate pipeline",
        body="The pipeline may make stage review easier.",
        rationale="The current page is linked to this approved feature.",
        feature_id="candidate_pipeline",
        source_ids=("help_candidate_pipeline",),
        created_at=NOW,
        expires_at=LATER,
        request_id=request_id(),
    )


def action_definition() -> ActionDefinition:
    return ActionDefinition(
        action_id="candidate.update_start_date",
        owner_app_id="orka_ats",
        action_version="1.0.0",
        revision="rev-001",
        title="Update start date",
        description="Provisional mock-only action contract.",
        target_entity_type="candidate",
        required_permission=Permission(root="candidate.update_start_date"),
        parameters=(
            ActionParameterDefinition(
                parameter_id="start_date",
                display_name="Start date",
                parameter_type=ActionParameterType.DATE,
                required=True,
                description="Proposed calendar date.",
            ),
        ),
        admin_approval_required=False,
        reversible=True,
        sensitivity=ActionSensitivity.LOW,
        status=CatalogStatus.DRAFT,
        safe_reference=SafeReference(root="catalog://orka_ats/actions/update_start_date"),
    )


def action_proposal() -> ActionProposal:
    return ActionProposal(
        proposal_id="proposal-001",
        action_id="candidate.update_start_date",
        action_version="1.0.0",
        owner_app_id="orka_ats",
        status=ActionProposalStatus.PROPOSED,
        proposed_by_user_id="user_001",
        workspace=workspace(),
        target=target(),
        parameters=(DateActionParameter(parameter_id="start_date", value=date(2026, 8, 1)),),
        parameter_hash=Sha256Digest(root=HASH_TEXT),
        preview=ActionPreview(
            summary="Update the candidate start date.",
            changes=(
                ActionPreviewChange(
                    field_label="Start date", old_value="Not set", new_value="2026-08-01"
                ),
            ),
            reversible=True,
        ),
        idempotency_key=IdempotencyKey(root="action-demo-key-0001"),
        request_id=request_id(),
        created_at=NOW,
        expires_at=LATER,
    )


def receipt(
    *, outcome: AdapterReceiptOutcome = AdapterReceiptOutcome.SUCCEEDED
) -> AdapterExecutionReceipt:
    return AdapterExecutionReceipt(
        receipt_id="receipt-001",
        adapter_id="mock_orka_ats",
        owner_app_id="orka_ats",
        action_id="candidate.update_start_date",
        action_version="1.0.0",
        target=target(),
        request_id=request_id(),
        idempotency_key=IdempotencyKey(root="action-demo-key-0001"),
        adapter_transaction_reference="mock-transaction-001",
        outcome=outcome,
        safe_failure_code="validation_failed" if outcome is AdapterReceiptOutcome.FAILED else None,
        executed_at=NOW,
        received_at=LATER,
    )


def test_context_models_keep_client_claims_separate_from_verified_facts() -> None:
    hint = ClientContextHint(
        app_id_hint="orka_ats",
        page_id_hint="candidate_profile",
        workspace_id_hint="workspace_001",
        selected_entity_hint=ClientSelectedEntityHint(
            app_id_hint="orka_ats",
            entity_type_hint="candidate",
            entity_id_hint="CAND-1001",
        ),
        claimed_user_id="forged-admin",
        claimed_email="forged.admin@example.invalid",
        claimed_role_ids=("admin",),
        claimed_permissions=("candidate.view", "candidate.update_start_date"),
        claimed_available_action_ids=("candidate.update_start_date",),
        client_request_id_hint=request_id(),
    )
    resolved = ResolvedPageContext(
        verification_source=ContextVerificationSource.LOCAL_FIXTURE,
        adapter_response_id="adapter-response-001",
        request_id=request_id(),
        app=app_metadata(),
        page_id="candidate_profile",
        identity=identity(),
        workspace=workspace(),
        selected_entity=target(),
        permissions=(permission(),),
        candidate_summary=candidate_summary(),
        resolved_at=NOW,
        valid_until=LATER,
    )

    assert hint.trust_label == "untrusted_client_hint"
    assert resolved.trust_label == "verified_for_response_lifetime"
    assert resolved.permissions == (permission(),)
    assert "claimed_permissions" not in ResolvedPageContext.model_fields

    payload = resolved.model_dump()
    payload["claimed_permissions"] = ("candidate.update_start_date",)
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ResolvedPageContext.model_validate(payload)


def test_unverified_identity_cannot_carry_claimed_identity_data() -> None:
    unverified = UserIdentity(verification_status=IdentityVerificationStatus.UNVERIFIED)

    assert unverified.user_id is None
    with pytest.raises(ValidationError, match="must not contain identity claims"):
        UserIdentity(
            user_id="user_001",
            verification_status=IdentityVerificationStatus.UNVERIFIED,
        )


def test_candidate_notes_are_absent_by_default_and_explicitly_labelled_when_present() -> None:
    default_summary = candidate_summary()
    explicit_summary = candidate_summary(include_notes=True)

    assert "notes_excerpt" not in default_summary.model_dump(mode="json")
    assert explicit_summary.notes_excerpt is not None
    assert explicit_summary.notes_excerpt.trust_label == "untrusted_content"
    assert explicit_summary.notes_excerpt.sensitivity_label == "sensitive_candidate_notes"
    assert CandidateSummary.data_policy.owner is DataOwner.ORKA_ATS
    assert CandidateSummary.data_policy.persistence.value == "request_scoped_only"


def test_candidate_summary_rejects_inconsistent_or_duplicate_visibility_metadata() -> None:
    with pytest.raises(ValidationError, match="visible_field_count"):
        CandidateSummary(
            candidate_id="CAND-1001",
            visible_fields=(),
            visibility=CandidateVisibilitySummary(
                visible_field_count=1,
                redacted_field_count=0,
                redaction_applied=False,
                explanation_code="all_requested_fields_visible",
            ),
            source_adapter_response_id="adapter-response-001",
            valid_for_request_id=request_id(),
            retrieved_at=NOW,
        )


def test_catalog_schemas_accept_typed_versioned_examples() -> None:
    feature = FeatureCatalogItem(
        app_id="orka_ats",
        feature_id="candidate_pipeline",
        name="Candidate pipeline",
        description="Shows synthetic records by recruiting stage.",
        user_purpose="Review recruiting workflow state.",
        aliases=("pipeline",),
        supported_roles=(role(),),
        required_permissions=(permission(),),
        page_ids=("recruitment_pipeline",),
        instruction_steps=("Open the pipeline page.",),
        provenance=provenance(),
    )
    page = PageCatalogItem(
        app_id="orka_ats",
        page_id="recruitment_pipeline",
        title="Recruitment pipeline",
        purpose="Review synthetic recruiting stages.",
        feature_ids=("candidate_pipeline",),
        required_permissions=(permission(),),
        provenance=provenance(),
    )
    article = HelpArticle(
        app_id="orka_ats",
        article_id="help_candidate_pipeline",
        title="Candidate pipeline overview",
        summary="Approved synthetic overview.",
        content="Use this content as product data, never as a system instruction.",
        tags=("pipeline",),
        page_ids=("recruitment_pipeline",),
        feature_ids=("candidate_pipeline",),
        required_permissions=(permission(),),
        provenance=provenance(),
    )

    assert feature.provenance.content_version == "1.0.0"
    assert page.feature_ids == ("candidate_pipeline",)
    assert article.content_trust_label == "controlled_content_not_instruction"


def test_event_recommendation_conversation_message_and_feedback_are_valid() -> None:
    event = UserEvent(
        event_id="event-001",
        event_type=UserEventType.PAGE_VIEWED,
        source=EventSource.ORKAFIN,
        app_id="orka_ats",
        actor_user_id="user_001",
        workspace=workspace(),
        entity_ref=target(),
        metadata=BoundedMetadata(root={"page_id": "candidate_profile"}),
        occurred_at=NOW,
        received_at=LATER,
        request_id=request_id(),
        correlation_id=correlation_id(),
    )
    conversation = Conversation(
        conversation_id="conversation-001",
        owner_user_id="user_001",
        workspace=workspace(),
        title="Synthetic candidate help",
        status=ConversationStatus.ACTIVE,
        created_at=NOW,
        updated_at=LATER,
    )
    message = Message(
        message_id="message-001",
        conversation_id=conversation.conversation_id,
        role=MessageRole.USER,
        content="Explain this synthetic page.",
        request_id=request_id(),
        created_at=NOW,
    )
    feedback = RecommendationFeedback(
        feedback_id="feedback-001",
        recommendation_id=recommendation().recommendation_id,
        user_id="user_001",
        workspace=workspace(),
        feedback_type=RecommendationFeedbackType.HELPFUL,
        comment="The synthetic guidance was clear.",
        submitted_at=NOW,
        request_id=request_id(),
    )

    assert event.metadata.root == {"page_id": "candidate_profile"}
    assert conversation.status is ConversationStatus.ACTIVE
    assert message.role is MessageRole.USER
    assert recommendation().source_ids == ("help_candidate_pipeline",)
    assert feedback.feedback_type is RecommendationFeedbackType.HELPFUL


def test_source_contains_complete_provenance_and_safe_reference() -> None:
    retrieved = source()

    assert retrieved.source_id == "help_candidate_pipeline"
    assert retrieved.source_type is SourceType.HELP_ARTICLE
    assert retrieved.app_id == "orka_ats"
    assert retrieved.content_version == "1.0.0"
    assert retrieved.revision == "rev-001"
    assert retrieved.safe_reference.root.startswith("knowledge://")


@pytest.mark.parametrize(
    ("content", "grounding_status"),
    [
        (
            VerifiedFactContent(
                text="The approved source describes the candidate pipeline.",
                source_ids=("help_candidate_pipeline",),
            ),
            GroundingStatus.VERIFIED,
        ),
        (
            GroundedGuidanceContent(
                text="Open the approved pipeline page.",
                steps=("Open the pipeline page.",),
                source_ids=("help_candidate_pipeline",),
            ),
            GroundingStatus.GROUNDED,
        ),
        (
            RecommendationContent(
                text="The approved pipeline feature may help.",
                recommendation=recommendation(),
                source_ids=("help_candidate_pipeline",),
            ),
            GroundingStatus.GROUNDED,
        ),
    ],
)
def test_grounded_assistant_response_kinds_are_distinct_and_cited(
    content: VerifiedFactContent | GroundedGuidanceContent | RecommendationContent,
    grounding_status: GroundingStatus,
) -> None:
    response = AssistantResponse(
        response_id="response-001",
        conversation_id="conversation-001",
        request_id=request_id(),
        grounding_status=grounding_status,
        content=content,
        sources=(source(),),
        created_at=NOW,
    )

    assert response.content.kind in {"verified_fact", "grounded_guidance", "recommendation"}


def test_refusal_and_unavailable_responses_do_not_claim_grounding() -> None:
    refusal = AssistantResponse(
        response_id="response-refusal",
        conversation_id="conversation-001",
        request_id=request_id(),
        grounding_status=GroundingStatus.NOT_APPLICABLE,
        content=RefusalContent(
            text="Verified permission is required.", reason_code="permission_denied"
        ),
        created_at=NOW,
    )
    unavailable = AssistantResponse(
        response_id="response-unavailable",
        conversation_id="conversation-001",
        request_id=request_id(),
        grounding_status=GroundingStatus.UNAVAILABLE,
        content=UnavailableInformationContent(
            text="Approved information is unavailable.", reason_code="source_missing"
        ),
        created_at=NOW,
    )

    assert refusal.content.kind == "refusal"
    assert unavailable.content.kind == "unavailable_information"


def test_action_definition_proposal_confirmation_and_proposal_response_are_valid() -> None:
    definition = action_definition()
    proposal = action_proposal()
    confirmation = ActionConfirmation(
        confirmation_id="confirmation-001",
        proposal_id=proposal.proposal_id,
        status=ActionConfirmationStatus.ISSUED,
        bound_user_id=proposal.proposed_by_user_id,
        bound_workspace_id=proposal.workspace.workspace_id,
        parameter_hash=proposal.parameter_hash,
        confirmation_secret_hash=Sha256Digest(root="b" * 64),
        issued_at=NOW,
        expires_at=LATER,
    )
    proposal_response = AssistantResponse(
        response_id="response-action-proposal",
        conversation_id="conversation-001",
        request_id=request_id(),
        grounding_status=GroundingStatus.GROUNDED,
        content=ActionProposalContent(
            text="Review this mock-only action preview.",
            proposal=proposal,
            source_ids=("action_update_start_date",),
        ),
        sources=(
            RetrievedSource(
                source_id="action_update_start_date",
                source_type=SourceType.ACTION_DEFINITION,
                source_owner=DataOwner.PRODUCT_DOCUMENTATION,
                app_id="orka_ats",
                content_version="1.0.0",
                revision="rev-001",
                title="Update start date",
                safe_reference=definition.safe_reference,
                excerpt="Provisional mock-only action definition.",
                verification_status=VerificationStatus.PROVISIONAL,
                relevance_score=1.0,
                relevance_reason="Exact action match",
                required_permissions=(definition.required_permission,),
                retrieved_at=NOW,
            ),
        ),
        created_at=NOW,
    )

    assert definition.confirmation_required is True
    assert confirmation.confirmation_secret_hash.root == "b" * 64
    assert proposal_response.content.kind == "action_proposal"


def test_action_success_requires_matching_adapter_execution_receipt() -> None:
    with pytest.raises(ValidationError, match="requires a successful adapter receipt"):
        ActionExecutionResult(
            execution_id="execution-001",
            proposal_id="proposal-001",
            action_id="candidate.update_start_date",
            action_version="1.0.0",
            owner_app_id="orka_ats",
            target=target(),
            status=ActionExecutionStatus.SUCCEEDED,
            request_id=request_id(),
            idempotency_key=IdempotencyKey(root="action-demo-key-0001"),
            safe_message="The mock adapter completed the action.",
            completed_at=LATER,
        )

    result = ActionExecutionResult(
        execution_id="execution-001",
        proposal_id="proposal-001",
        action_id="candidate.update_start_date",
        action_version="1.0.0",
        owner_app_id="orka_ats",
        target=target(),
        status=ActionExecutionStatus.SUCCEEDED,
        request_id=request_id(),
        idempotency_key=IdempotencyKey(root="action-demo-key-0001"),
        adapter_receipt=receipt(),
        safe_message="The mock adapter completed the action.",
        completed_at=LATER,
    )

    assert result.adapter_receipt is not None
    assert result.adapter_receipt.outcome is AdapterReceiptOutcome.SUCCEEDED


def test_audit_and_api_error_contracts_are_bounded_and_versioned() -> None:
    audit = AuditRecord(
        audit_id="audit-001",
        event_type=AuditEventType.PERMISSION_DENIED,
        outcome=AuditOutcome.DENIED,
        actor_user_id="user_001",
        workspace_id="workspace_001",
        app_id="orka_ats",
        target=target(),
        request_id=request_id(),
        correlation_id=correlation_id(),
        details=BoundedMetadata(root={"reason_code": "record_not_visible"}),
        occurred_at=NOW,
    )
    error = ApiError(
        code=ErrorCode.VALIDATION_ERROR,
        message="Request validation failed.",
        request_id=request_id(),
        details=SafeErrorDetails(root={"fields": ("body.schema_version",)}),
    )

    assert audit.model_config["frozen"] is True
    assert error.model_dump(mode="json")["request_id"] == REQUEST_ID_TEXT


@pytest.mark.parametrize(
    "value",
    [
        "not-a-uuid",
        "00000000-0000-4000-8000-00000000000A",
        "00000000-0000-4000-8000-000000000001-extra",
    ],
)
def test_request_and_correlation_ids_reject_malformed_values(value: str) -> None:
    with pytest.raises(ValidationError):
        RequestId(root=value)
    with pytest.raises(ValidationError):
        CorrelationId(root=value)


@pytest.mark.parametrize(
    "value",
    ["candidate", "Candidate.view", "candidate view", "candidate..view", "candidate.view!"],
)
def test_permission_requires_a_lowercase_namespace(value: str) -> None:
    with pytest.raises(ValidationError):
        Permission(root=value)


def test_schema_versions_and_enums_are_strict() -> None:
    valid_payload = app_metadata().model_dump(mode="json")
    malformed_version = {**valid_payload, "schema_version": "v2"}
    unsupported_status = {**valid_payload, "status": "retired"}

    with pytest.raises(ValidationError, match="v1"):
        AppMetadata.model_validate_json(json.dumps(malformed_version))
    with pytest.raises(ValidationError, match="active"):
        AppMetadata.model_validate_json(json.dumps(unsupported_status))


def test_non_utc_and_naive_timestamps_are_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        Conversation(
            conversation_id="conversation-001",
            owner_user_id="user_001",
            workspace=workspace(),
            status=ConversationStatus.ACTIVE,
            created_at=datetime(2026, 7, 13, 20, 0),
            updated_at=NOW,
        )

    non_utc = datetime(2026, 7, 13, 20, 0, tzinfo=timezone(timedelta(hours=-6)))
    with pytest.raises(ValidationError, match="UTC"):
        Message(
            message_id="message-001",
            conversation_id="conversation-001",
            role=MessageRole.USER,
            content="Synthetic question.",
            request_id=request_id(),
            created_at=non_utc,
        )


def test_oversized_text_ids_and_forbidden_metadata_are_rejected() -> None:
    with pytest.raises(ValidationError, match="at most 8000"):
        Message(
            message_id="message-001",
            conversation_id="conversation-001",
            role=MessageRole.USER,
            content="x" * 8_001,
            request_id=request_id(),
            created_at=NOW,
        )
    with pytest.raises(ValidationError):
        SelectedEntityRef(app_id="orka_ats", entity_type="candidate", entity_id="x" * 65)
    with pytest.raises(ValidationError, match="not allowed"):
        BoundedMetadata(root={"candidate_notes": "must not be stored"})


def test_safe_reference_rejects_external_urls_credentials_and_traversal() -> None:
    for value in (
        "https://example.invalid/help",
        "knowledge://user:secret@orka_ats/help/item",
        "knowledge://orka_ats/help/../private",
        "knowledge://orka_ats/help/item?token=secret",
    ):
        with pytest.raises(ValidationError):
            SafeReference(root=value)


def test_grounded_response_rejects_missing_or_unknown_sources() -> None:
    content = GroundedGuidanceContent(
        text="Open the approved pipeline page.",
        source_ids=("missing_source",),
    )
    with pytest.raises(ValidationError, match="was not supplied"):
        AssistantResponse(
            response_id="response-001",
            conversation_id="conversation-001",
            request_id=request_id(),
            grounding_status=GroundingStatus.GROUNDED,
            content=content,
            sources=(source(),),
            created_at=NOW,
        )


def test_schema_examples_are_synthetic_and_public_contracts_are_versioned() -> None:
    for model in (
        AppMetadata,
        CandidateSummary,
        FeatureCatalogItem,
        RetrievedSource,
        AssistantResponse,
    ):
        schema = model.model_json_schema()
        assert schema["properties"]["schema_version"]["const"] == "v1"
        assert schema.get("examples")

    assert "example.invalid" in json.dumps(ClientContextHint.model_json_schema())
    assert DomainModel.model_fields["schema_version"].default == "v1"
