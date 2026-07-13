from __future__ import annotations

import asyncio
import io
import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from orkafin.adapters import (
    AdapterCapability,
    AdapterConflictError,
    AdapterErrorCode,
    AdapterFailure,
    AdapterForbiddenError,
    AdapterInternalFailureError,
    AdapterTimeoutError,
    AdapterUnavailableError,
    ExecuteApprovedActionResponse,
    GetAppMetadataRequest,
    GetAppMetadataResponse,
)
from orkafin.adapters.orka_ats import (
    AppsScriptAdapterConfig,
    AppsScriptFailureEnvelope,
    AppsScriptOrkaATSAdapter,
    AppsScriptRequestEnvelope,
    AppsScriptSuccessEnvelope,
    HttpTransportResponse,
    HttpTransportTimeoutError,
)
from orkafin.domain.context import AppMetadata, AppStatus
from orkafin.domain.identifiers import RequestId

NOW = datetime(2026, 7, 13, 20, 0, tzinfo=UTC)
REQUEST_ID = RequestId(root="00000000-0000-4000-8000-000000000110")
ENDPOINT = "https://example.invalid/orka-ats-adapter"


class RecordingTransport:
    def __init__(
        self,
        response: HttpTransportResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, object]] = []

    async def post(
        self,
        *,
        url: str,
        body: bytes,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> HttpTransportResponse:
        self.calls.append(
            {
                "url": url,
                "body": body,
                "headers": headers,
                "timeout_seconds": timeout_seconds,
            }
        )
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


def request() -> GetAppMetadataRequest:
    return GetAppMetadataRequest(request_id=REQUEST_ID, app_id="orka_ats")


def app_response(*, description: str = "Synthetic OrkaATS metadata.") -> GetAppMetadataResponse:
    return GetAppMetadataResponse(
        request_id=REQUEST_ID,
        app_id="orka_ats",
        adapter_response_id="apps-script-response-001",
        responded_at=NOW,
        app_metadata=AppMetadata(
            app_id="orka_ats",
            display_name="OrkaATS",
            description=description,
            app_version="1.0.0",
            adapter_contract_version="1.0.0",
            status=AppStatus.ACTIVE,
        ),
    )


def success_transport_response(
    response: GetAppMetadataResponse | ExecuteApprovedActionResponse,
    *,
    operation: AdapterCapability = AdapterCapability.GET_APP_METADATA,
) -> HttpTransportResponse:
    envelope = AppsScriptSuccessEnvelope(
        operation=operation,
        request_id=REQUEST_ID,
        app_id="orka_ats",
        adapter_response_id=response.adapter_response_id,
        responded_at=response.responded_at,
        outcome="success",
        payload=response.model_dump(mode="json"),
    )
    return HttpTransportResponse(status_code=200, body=envelope.model_dump_json().encode())


def enabled_adapter(transport: RecordingTransport) -> AppsScriptOrkaATSAdapter:
    return AppsScriptOrkaATSAdapter(
        transport=transport,
        config=AppsScriptAdapterConfig(enabled=True, endpoint_url=ENDPOINT),
    )


def run_get_metadata(adapter: AppsScriptOrkaATSAdapter) -> GetAppMetadataResponse:
    return asyncio.run(adapter.get_app_metadata(request()))


def test_success_parsing_serializes_typed_envelope_and_propagates_request_id() -> None:
    transport = RecordingTransport(success_transport_response(app_response()))
    adapter = enabled_adapter(transport)

    parsed = run_get_metadata(adapter)

    assert parsed == app_response()
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["url"] == ENDPOINT
    assert call["timeout_seconds"] == 5.0
    headers = call["headers"]
    assert isinstance(headers, dict)
    assert headers["X-OrkaFin-Request-ID"] == REQUEST_ID.root
    body = call["body"]
    assert isinstance(body, bytes)
    envelope = AppsScriptRequestEnvelope.model_validate_json(body)
    assert envelope.operation is AdapterCapability.GET_APP_METADATA
    assert envelope.request_id == REQUEST_ID
    assert envelope.payload == request().model_dump(mode="json")


@pytest.mark.parametrize(
    ("field", "value"),
    [("schema_version", "v2"), ("adapter_contract_version", "2.0.0")],
)
def test_version_mismatch_fails_closed_as_contract_conflict(field: str, value: str) -> None:
    response = success_transport_response(app_response())
    payload = json.loads(response.body)
    payload[field] = value
    transport = RecordingTransport(
        HttpTransportResponse(status_code=200, body=json.dumps(payload).encode())
    )

    with pytest.raises(AdapterConflictError, match="incompatible"):
        run_get_metadata(enabled_adapter(transport))


def test_transport_timeout_maps_to_typed_timeout_without_a_success() -> None:
    transport = RecordingTransport(error=HttpTransportTimeoutError("sensitive transport detail"))

    with pytest.raises(AdapterTimeoutError) as caught:
        run_get_metadata(enabled_adapter(transport))

    assert caught.value.request_id == REQUEST_ID
    assert caught.value.retryable is True


@pytest.mark.parametrize("body", [b"{", b"[]", b'{"outcome":"success"}'])
def test_malformed_success_response_maps_to_safe_internal_failure(body: bytes) -> None:
    transport = RecordingTransport(HttpTransportResponse(status_code=200, body=body))

    with pytest.raises(AdapterInternalFailureError, match="invalid response"):
        run_get_metadata(enabled_adapter(transport))


def test_permission_denial_maps_valid_failure_envelope() -> None:
    failure = AdapterFailure(
        request_id=REQUEST_ID,
        app_id="orka_ats",
        adapter_response_id="apps-script-denial-001",
        code=AdapterErrorCode.FORBIDDEN,
        safe_message="OrkaATS denied access to this context.",
        retryable=False,
        failure_reference="denial-reference-001",
        failed_at=NOW,
    )
    envelope = AppsScriptFailureEnvelope(
        operation=AdapterCapability.GET_APP_METADATA,
        request_id=REQUEST_ID,
        app_id="orka_ats",
        adapter_response_id=failure.adapter_response_id,
        responded_at=NOW,
        outcome="failure",
        failure=failure,
    )
    transport = RecordingTransport(
        HttpTransportResponse(status_code=403, body=envelope.model_dump_json().encode())
    )

    with pytest.raises(AdapterForbiddenError) as caught:
        run_get_metadata(enabled_adapter(transport))

    assert caught.value.request_id == REQUEST_ID
    assert caught.value.failure_reference == "denial-reference-001"


def test_invalid_action_receipt_is_rejected_during_typed_response_parsing() -> None:
    response = app_response()
    envelope = AppsScriptSuccessEnvelope(
        operation=AdapterCapability.EXECUTE_APPROVED_ACTION,
        request_id=REQUEST_ID,
        app_id="orka_ats",
        adapter_response_id=response.adapter_response_id,
        responded_at=NOW,
        outcome="success",
        payload={
            "schema_version": "v1",
            "adapter_contract_version": "1.0.0",
            "request_id": REQUEST_ID.root,
            "app_id": "orka_ats",
            "adapter_response_id": response.adapter_response_id,
            "responded_at": NOW.isoformat(),
            "receipt": {
                "schema_version": "v1",
                "receipt_id": "receipt-001",
                "adapter_id": "apps_script_orka_ats",
                "owner_app_id": "other_app",
                "action_id": "candidate.update_start_date",
                "action_version": "1.0.0",
                "target": {
                    "schema_version": "v1",
                    "app_id": "orka_ats",
                    "entity_type": "candidate",
                    "entity_id": "CAND-1001",
                },
                "request_id": REQUEST_ID.root,
                "idempotency_key": "action-demo-key-0001",
                "adapter_transaction_reference": "transaction-001",
                "outcome": "succeeded",
                "executed_at": NOW.isoformat(),
                "received_at": NOW.isoformat(),
            },
        },
    )
    adapter = enabled_adapter(RecordingTransport())

    with pytest.raises(AdapterInternalFailureError, match="invalid response"):
        adapter._parse_response(
            HttpTransportResponse(status_code=200, body=envelope.model_dump_json().encode()),
            operation=AdapterCapability.EXECUTE_APPROVED_ACTION,
            request=request(),
            response_type=ExecuteApprovedActionResponse,
        )


def test_adapter_logs_exclude_endpoint_and_response_secrets() -> None:
    secret = "NEVER-LOG-THIS-CANDIDATE-SECRET"
    endpoint_secret = "NEVER-LOG-THIS-ENDPOINT-PATH"
    transport = RecordingTransport(
        success_transport_response(app_response(description=f"Synthetic {secret}"))
    )
    adapter = AppsScriptOrkaATSAdapter(
        transport=transport,
        config=AppsScriptAdapterConfig(
            enabled=True,
            endpoint_url=f"https://example.invalid/{endpoint_secret}",
        ),
    )
    logger = logging.getLogger("orkafin.adapters.orka_ats.apps_script")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    original_level = logger.level
    original_disabled = logger.disabled
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.disabled = False
    try:
        run_get_metadata(adapter)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(original_level)
        logger.disabled = original_disabled

    output = stream.getvalue()
    assert "apps_script_adapter_request" in output
    assert "apps_script_adapter_response" in output
    assert secret not in output
    assert endpoint_secret not in output


def test_disabled_by_default_and_incomplete_enabled_config_refuse_startup() -> None:
    transport = RecordingTransport()

    with pytest.raises(AdapterUnavailableError, match="disabled"):
        AppsScriptOrkaATSAdapter(transport=transport)
    with pytest.raises(ValidationError, match="requires endpoint_url"):
        AppsScriptAdapterConfig(enabled=True)
    with pytest.raises(ValidationError, match="absolute HTTPS URL"):
        AppsScriptAdapterConfig(enabled=True, endpoint_url="http://localhost:8000")
