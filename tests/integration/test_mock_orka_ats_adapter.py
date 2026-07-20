"""Integration coverage for the fixture-owned mock OrkaATS adapter."""

from __future__ import annotations

import asyncio

import pytest

from orkafin.adapters import (
    AdapterCapability,
    AdapterErrorCode,
    AdapterNotFoundError,
    AdapterTimeoutError,
    AdapterUnavailableError,
    AdapterValidationFailedError,
    GetAppMetadataRequest,
    GetAvailableActionsRequest,
    GetAvailableFeaturesRequest,
    GetSelectedEntitySummaryRequest,
    GetUserPermissionsRequest,
    ResolveContextRequest,
    ResolveCurrentUserRequest,
    ResolvedApplicationContext,
    SearchAllowedRecordsRequest,
)
from orkafin.adapters.orka_ats import MockFailureSimulation, MockOrkaATSAdapter
from orkafin.domain.context import (
    ClientContextHint,
    ClientSelectedEntityHint,
    UserIdentity,
)
from orkafin.domain.identifiers import RequestId

from ..contracts.adapter_contract import AdapterContractScenario, assert_adapter_contract

REQUEST_ID = RequestId(root="00000000-0000-4000-8000-000000000901")


def _hint(*, candidate_id: str | None = "CAND-1042") -> ClientContextHint:
    return ClientContextHint(
        app_id="orka_ats",
        page="candidate_profile",
        selected_entity=(
            ClientSelectedEntityHint(type="candidate", id=candidate_id)
            if candidate_id is not None
            else None
        ),
    )


async def _identity_and_context(
    adapter: MockOrkaATSAdapter, fixture_id: str, *, candidate_id: str | None = "CAND-1042"
) -> tuple[UserIdentity, ResolvedApplicationContext]:
    identity_response = await adapter.resolve_current_user(
        ResolveCurrentUserRequest(
            request_id=REQUEST_ID,
            app_id="orka_ats",
            trusted_subject_reference=fixture_id,
            client_hint=_hint(candidate_id=candidate_id),
        )
    )
    context_response = await adapter.resolve_context(
        ResolveContextRequest(
            request_id=REQUEST_ID,
            app_id="orka_ats",
            trusted_identity=identity_response.identity,
            client_hint=_hint(candidate_id=candidate_id),
        )
    )
    return identity_response.identity, context_response.context


def test_mock_adapter_conforms_to_general_contract_suite() -> None:
    scenario = AdapterContractScenario(
        app_id="orka_ats",
        request_id=REQUEST_ID,
        trusted_subject_reference="recruiter",
        client_hint=_hint(),
    )
    asyncio.run(assert_adapter_contract(MockOrkaATSAdapter, scenario))


def test_recruiter_summary_is_redacted_inside_adapter() -> None:
    async def exercise() -> None:
        adapter = MockOrkaATSAdapter()
        identity, context = await _identity_and_context(adapter, "recruiter")
        response = await adapter.get_selected_entity_summary(
            GetSelectedEntitySummaryRequest(
                request_id=REQUEST_ID,
                app_id="orka_ats",
                trusted_identity=identity,
                context=context,
                requested_field_ids=("display_name", "email", "created_at", "unknown_field"),
            )
        )
        assert [field.field_id for field in response.summary.visible_fields] == [
            "display_name",
            "email",
        ]
        assert response.summary.visibility.visible_field_count == 2
        assert response.summary.visibility.redacted_field_count == 2
        features = await adapter.get_available_features(
            GetAvailableFeaturesRequest(
                request_id=REQUEST_ID,
                app_id="orka_ats",
                trusted_identity=identity,
                context=context,
            )
        )
        assert "candidate.update_start_date" not in features.feature_ids
        actions = await adapter.get_available_actions(
            GetAvailableActionsRequest(
                request_id=REQUEST_ID,
                app_id="orka_ats",
                trusted_identity=identity,
                context=context,
            )
        )
        assert actions.action_ids == ()

    asyncio.run(exercise())


def test_limited_viewer_sees_reduced_summary_and_search_fields_are_filtered() -> None:
    async def exercise() -> None:
        adapter = MockOrkaATSAdapter()
        identity, context = await _identity_and_context(adapter, "limited_viewer")
        summary = await adapter.get_selected_entity_summary(
            GetSelectedEntitySummaryRequest(
                request_id=REQUEST_ID,
                app_id="orka_ats",
                trusted_identity=identity,
                context=context,
            )
        )
        assert [field.field_id for field in summary.summary.visible_fields] == [
            "display_name",
            "recruiter",
            "recruitment_stage",
        ]
        search = await adapter.search_allowed_records(
            SearchAllowedRecordsRequest(
                request_id=REQUEST_ID,
                app_id="orka_ats",
                trusted_identity=identity,
                context=context,
                query="taylor",
                requested_field_ids=("email", "recruitment_stage"),
                limit=1,
            )
        )
        assert len(search.results) == 1
        assert [field.field_id for field in search.results[0].visible_fields] == [
            "recruitment_stage"
        ]

    asyncio.run(exercise())


def test_admin_sees_only_the_enabled_action_on_candidate_profile() -> None:
    async def exercise() -> None:
        adapter = MockOrkaATSAdapter()
        identity, context = await _identity_and_context(adapter, "admin")
        actions = await adapter.get_available_actions(
            GetAvailableActionsRequest(
                request_id=REQUEST_ID,
                app_id="orka_ats",
                trusted_identity=identity,
                context=context,
            )
        )
        assert actions.action_ids == ("candidate.update_start_date",)

        dashboard_context = context.model_copy(update={"page_id": "candidate_dashboard"})
        dashboard_actions = await adapter.get_available_actions(
            GetAvailableActionsRequest(
                request_id=REQUEST_ID,
                app_id="orka_ats",
                trusted_identity=identity,
                context=dashboard_context,
            )
        )
        assert dashboard_actions.action_ids == ()

    asyncio.run(exercise())


def test_private_and_archived_candidates_remain_indistinguishable_from_missing() -> None:
    async def exercise() -> None:
        adapter = MockOrkaATSAdapter()
        identity, private_context = await _identity_and_context(
            adapter, "recruiter", candidate_id="CAND-1099"
        )
        missing_context = private_context.model_copy(
            update={
                "selected_entity": private_context.selected_entity.model_copy(
                    update={"entity_id": "CAND-4040"}
                )
            }
        )
        archived_context = private_context.model_copy(
            update={
                "selected_entity": private_context.selected_entity.model_copy(
                    update={"entity_id": "CAND-1999"}
                )
            }
        )
        for context in (private_context, archived_context, missing_context):
            with pytest.raises(AdapterNotFoundError) as caught:
                await adapter.get_selected_entity_summary(
                    GetSelectedEntitySummaryRequest(
                        request_id=REQUEST_ID,
                        app_id="orka_ats",
                        trusted_identity=identity,
                        context=context,
                    )
                )
            assert caught.value.public_message == AdapterNotFoundError.default_message

    asyncio.run(exercise())


def test_unverified_user_receives_no_candidate_identity_or_authorization() -> None:
    async def exercise() -> None:
        adapter = MockOrkaATSAdapter()
        response = await adapter.resolve_current_user(
            ResolveCurrentUserRequest(
                request_id=REQUEST_ID,
                app_id="orka_ats",
                trusted_subject_reference="unverified",
                client_hint=_hint(),
            )
        )
        assert response.identity.user_id is None
        assert response.identity.role is None
        assert response.identity.verification_status.value == "unverified"

    asyncio.run(exercise())


def test_notes_are_neither_searchable_nor_returned_as_candidate_fields() -> None:
    async def exercise() -> None:
        adapter = MockOrkaATSAdapter()
        identity, context = await _identity_and_context(adapter, "recruiter")
        search = await adapter.search_allowed_records(
            SearchAllowedRecordsRequest(
                request_id=REQUEST_ID,
                app_id="orka_ats",
                trusted_identity=identity,
                context=context,
                query="ignore prior instructions",
                limit=10,
            )
        )
        summary = await adapter.get_selected_entity_summary(
            GetSelectedEntitySummaryRequest(
                request_id=REQUEST_ID,
                app_id="orka_ats",
                trusted_identity=identity,
                context=context,
                requested_field_ids=("notes",),
            )
        )
        assert search.results == ()
        assert summary.summary.visible_fields == ()
        assert "IGNORE PRIOR INSTRUCTIONS" not in summary.model_dump_json()

    asyncio.run(exercise())


def test_search_enforces_request_limit_and_admin_visibility_stays_bounded() -> None:
    async def exercise() -> None:
        adapter = MockOrkaATSAdapter()
        identity, context = await _identity_and_context(adapter, "admin")
        search = await adapter.search_allowed_records(
            SearchAllowedRecordsRequest(
                request_id=REQUEST_ID,
                app_id="orka_ats",
                trusted_identity=identity,
                context=context,
                query="synthetic",
                requested_field_ids=("email",),
                limit=1,
            )
        )
        permissions = await adapter.get_user_permissions(
            GetUserPermissionsRequest(
                request_id=REQUEST_ID,
                app_id="orka_ats",
                trusted_identity=identity,
                context=context,
            )
        )
        assert len(search.results) == 1
        assert {grant.record.entity_id for grant in permissions.authorization_facts.records} == {
            "CAND-1042",
            "CAND-1043",
        }
        assert "CAND-1099" not in {result.entity.entity_id for result in search.results}

    asyncio.run(exercise())


def test_failure_simulation_returns_exact_typed_adapter_failure() -> None:
    async def exercise() -> None:
        failures = (
            (AdapterErrorCode.TIMEOUT, AdapterTimeoutError),
            (AdapterErrorCode.UNAVAILABLE, AdapterUnavailableError),
            (AdapterErrorCode.VALIDATION_FAILED, AdapterValidationFailedError),
        )
        for code, error_type in failures:
            adapter = MockOrkaATSAdapter(
                simulation=MockFailureSimulation(
                    failures={AdapterCapability.GET_APP_METADATA: code}
                )
            )
            with pytest.raises(error_type) as caught:
                await adapter.get_app_metadata(
                    GetAppMetadataRequest(request_id=REQUEST_ID, app_id="orka_ats")
                )
            assert caught.value.retryable is (
                code in {AdapterErrorCode.TIMEOUT, AdapterErrorCode.UNAVAILABLE}
            )
            assert caught.value.failure_reference == "mock-failure-get_app_metadata"

    asyncio.run(exercise())
