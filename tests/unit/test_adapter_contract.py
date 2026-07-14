from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from orkafin.adapters import (
    ADAPTER_CONTRACT_VERSION,
    AdapterCapability,
    AdapterConflictError,
    AdapterError,
    AdapterErrorCode,
    AdapterFailure,
    AdapterForbiddenError,
    AdapterInternalFailureError,
    AdapterNotFoundError,
    AdapterRegistration,
    AdapterRegistry,
    AdapterRequest,
    AdapterResponse,
    AdapterTimeoutError,
    AdapterUnauthorizedError,
    AdapterUnavailableError,
    AdapterUnsupportedCapabilityError,
    AdapterValidationFailedError,
    ExecuteApprovedActionRequest,
    ExecuteApprovedActionResponse,
    GetAvailableFeaturesRequest,
    ResolveContextRequest,
    ResolveCurrentUserRequest,
    adapter_error_from_failure,
)
from orkafin.core.dependencies import build_dependencies
from orkafin.core.settings import Settings
from orkafin.domain.actions import (
    AdapterExecutionReceipt,
    AdapterReceiptOutcome,
)
from orkafin.domain.context import ClientContextHint, SelectedEntityRef
from orkafin.domain.identifiers import IdempotencyKey, RequestId

from ..contracts.adapter_contract import AdapterContractScenario, assert_adapter_contract
from ..contracts.fake_adapter import APP_ID, MinimalContractFakeAdapter

REQUEST_ID = RequestId(root="00000000-0000-4000-8000-000000000081")
NOW = datetime(2026, 7, 13, 20, 0, tzinfo=UTC)


def scenario() -> AdapterContractScenario:
    return AdapterContractScenario(
        app_id=APP_ID,
        request_id=REQUEST_ID,
        trusted_subject_reference="sample-subject",
        client_hint=ClientContextHint(app_id=APP_ID, page="home_page"),
    )


def test_minimal_fake_conforms_to_reusable_adapter_contract_suite() -> None:
    asyncio.run(assert_adapter_contract(MinimalContractFakeAdapter, scenario()))


def test_unadvertised_capability_raises_explicit_unsupported_error() -> None:
    async def exercise() -> None:
        adapter = MinimalContractFakeAdapter()
        identity_response = await adapter.resolve_current_user(
            ResolveCurrentUserRequest(
                request_id=REQUEST_ID,
                app_id=APP_ID,
                trusted_subject_reference="sample-subject",
            )
        )
        context_response = await adapter.resolve_context(
            ResolveContextRequest(
                request_id=REQUEST_ID,
                app_id=APP_ID,
                trusted_identity=identity_response.identity,
                client_hint=scenario().client_hint,
            )
        )
        request = GetAvailableFeaturesRequest(
            request_id=REQUEST_ID,
            app_id=APP_ID,
            trusted_identity=identity_response.identity,
            context=context_response.context,
        )
        with pytest.raises(AdapterUnsupportedCapabilityError) as caught:
            await adapter.get_available_features(request)
        assert caught.value.code is AdapterErrorCode.UNSUPPORTED_CAPABILITY

    asyncio.run(exercise())


@pytest.mark.parametrize(
    ("code", "error_type", "retryable"),
    [
        (AdapterErrorCode.UNAVAILABLE, AdapterUnavailableError, True),
        (AdapterErrorCode.UNAUTHORIZED, AdapterUnauthorizedError, False),
        (AdapterErrorCode.FORBIDDEN, AdapterForbiddenError, False),
        (AdapterErrorCode.NOT_FOUND, AdapterNotFoundError, False),
        (AdapterErrorCode.VALIDATION_FAILED, AdapterValidationFailedError, False),
        (AdapterErrorCode.CONFLICT, AdapterConflictError, False),
        (AdapterErrorCode.TIMEOUT, AdapterTimeoutError, True),
        (AdapterErrorCode.INTERNAL_FAILURE, AdapterInternalFailureError, False),
        (
            AdapterErrorCode.UNSUPPORTED_CAPABILITY,
            AdapterUnsupportedCapabilityError,
            False,
        ),
    ],
)
def test_adapter_failure_maps_to_exact_typed_error(
    code: AdapterErrorCode,
    error_type: type[AdapterError],
    retryable: bool,
) -> None:
    failure = AdapterFailure(
        request_id=REQUEST_ID,
        app_id=APP_ID,
        adapter_response_id="adapter-failure-response",
        code=code,
        safe_message="The application reported a safe failure.",
        retryable=retryable,
        failure_reference="failure-reference",
        failed_at=NOW,
    )

    error = adapter_error_from_failure(failure)

    assert type(error) is error_type
    assert error.code is code
    assert error.retryable is retryable
    assert error.request_id == REQUEST_ID
    assert error.public_message == failure.safe_message


def test_adapter_failure_rejects_incorrect_retry_mapping() -> None:
    with pytest.raises(ValidationError, match="retryable flag"):
        AdapterFailure(
            request_id=REQUEST_ID,
            app_id=APP_ID,
            adapter_response_id="adapter-failure-response",
            code=AdapterErrorCode.TIMEOUT,
            safe_message="The application timed out.",
            retryable=False,
            failed_at=NOW,
        )


def test_registry_resolves_injected_factory_once_and_checks_capabilities() -> None:
    created: list[MinimalContractFakeAdapter] = []

    def factory() -> MinimalContractFakeAdapter:
        adapter = MinimalContractFakeAdapter()
        created.append(adapter)
        return adapter

    registry = AdapterRegistry((AdapterRegistration(app_id=APP_ID, factory=factory),))

    first = registry.resolve(APP_ID, required_capability=AdapterCapability.GET_APP_METADATA)
    second = registry.resolve(APP_ID)

    assert first is second
    assert created == [first]
    assert registry.registered_app_ids == (APP_ID,)
    with pytest.raises(AdapterUnsupportedCapabilityError):
        registry.resolve(APP_ID, required_capability=AdapterCapability.SEARCH_ALLOWED_RECORDS)
    with pytest.raises(AdapterNotFoundError):
        registry.resolve("missing_app")


def test_registry_rejects_duplicate_app_registration() -> None:
    registration = AdapterRegistration(app_id=APP_ID, factory=MinimalContractFakeAdapter)
    with pytest.raises(AdapterConflictError):
        AdapterRegistry((registration, registration))


def test_dependency_builder_accepts_injected_adapter_registry() -> None:
    registry = AdapterRegistry(
        (AdapterRegistration(app_id=APP_ID, factory=MinimalContractFakeAdapter),)
    )

    dependencies = build_dependencies(Settings(), adapter_registry=registry)

    assert dependencies.adapter_registry is registry


def execution_receipt() -> AdapterExecutionReceipt:
    return AdapterExecutionReceipt(
        receipt_id="receipt-contract-001",
        adapter_id="sample_contract_fake",
        owner_app_id=APP_ID,
        action_id="record.update",
        action_version="1.0.0",
        target=SelectedEntityRef(app_id=APP_ID, entity_type="record", entity_id="REC-001"),
        request_id=REQUEST_ID,
        idempotency_key=IdempotencyKey(root="adapter-contract-key-0001"),
        adapter_transaction_reference="transaction-reference-001",
        outcome=AdapterReceiptOutcome.SUCCEEDED,
        executed_at=NOW,
        received_at=NOW,
    )


def test_execution_response_accepts_only_matching_versioned_receipt() -> None:
    receipt = execution_receipt()
    response = ExecuteApprovedActionResponse(
        request_id=REQUEST_ID,
        app_id=APP_ID,
        adapter_response_id="adapter-execution-response",
        responded_at=NOW,
        receipt=receipt,
    )

    assert response.adapter_contract_version == ADAPTER_CONTRACT_VERSION
    assert response.receipt.adapter_transaction_reference == "transaction-reference-001"
    assert response.receipt.target.entity_type == "record"

    payload = response.model_dump(mode="python")
    payload["app_id"] = "other_app"
    with pytest.raises(ValidationError, match="receipt must match response app"):
        ExecuteApprovedActionResponse.model_validate(payload)


def test_failed_execution_receipt_requires_explicit_failure_code() -> None:
    payload = execution_receipt().model_dump(mode="python")
    payload["outcome"] = AdapterReceiptOutcome.FAILED
    with pytest.raises(ValidationError, match="failed receipt requires a safe failure code"):
        AdapterExecutionReceipt.model_validate(payload)


def test_every_adapter_request_and_response_inherits_both_versions() -> None:
    def descendants(model: type[AdapterRequest] | type[AdapterResponse]) -> set[type[object]]:
        found: set[type[object]] = set()
        pending = list(model.__subclasses__())
        while pending:
            child = pending.pop()
            found.add(child)
            pending.extend(child.__subclasses__())
        return found

    models = descendants(AdapterRequest) | descendants(AdapterResponse)
    assert models
    for model in models:
        assert model.model_fields["schema_version"].default == "v1"
        assert model.model_fields["adapter_contract_version"].default == ADAPTER_CONTRACT_VERSION


def test_action_execution_request_structurally_requires_every_write_guard() -> None:
    required_fields = {
        "action_definition",
        "trusted_identity",
        "context",
        "proposal",
        "confirmation",
        "idempotency_key",
        "request_id",
    }

    assert required_fields.issubset(ExecuteApprovedActionRequest.model_fields)
    assert all(
        ExecuteApprovedActionRequest.model_fields[field_name].is_required()
        for field_name in required_fields
    )
