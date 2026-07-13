"""Reusable baseline contract suite for application adapter implementations."""

from __future__ import annotations

import inspect
from dataclasses import dataclass

from orkafin.adapters import (
    ADAPTER_CONTRACT_VERSION,
    REQUIRED_ADAPTER_CAPABILITIES,
    AdapterCapability,
    AdapterFactory,
    AdapterResponse,
    GetAppMetadataRequest,
    GetPageMetadataRequest,
    GetUserPermissionsRequest,
    OrkaApplicationAdapter,
    ResolveContextRequest,
    ResolveCurrentUserRequest,
)
from orkafin.domain.context import ClientContextHint, IdentityVerificationStatus
from orkafin.domain.identifiers import RequestId


@dataclass(frozen=True, slots=True)
class AdapterContractScenario:
    """Minimal trusted inputs an implementation supplies to run the baseline suite."""

    app_id: str
    request_id: RequestId
    trusted_subject_reference: str
    client_hint: ClientContextHint


def _assert_response_envelope(
    response: AdapterResponse, *, scenario: AdapterContractScenario
) -> None:
    assert response.adapter_contract_version == ADAPTER_CONTRACT_VERSION
    assert response.app_id == scenario.app_id
    assert response.request_id == scenario.request_id


async def assert_adapter_contract(
    factory: AdapterFactory,
    scenario: AdapterContractScenario,
) -> None:
    """Exercise mandatory operations and structural async conformance."""
    adapter = factory()
    assert isinstance(adapter, OrkaApplicationAdapter)
    assert adapter.metadata.owning_app_id == scenario.app_id
    assert adapter.metadata.adapter_contract_version == ADAPTER_CONTRACT_VERSION
    advertised = {item.capability for item in adapter.metadata.capabilities}
    assert REQUIRED_ADAPTER_CAPABILITIES.issubset(advertised)

    for capability in AdapterCapability:
        method = getattr(adapter, capability.value)
        assert inspect.iscoroutinefunction(method), f"{capability.value} must be async"

    metadata_response = await adapter.get_app_metadata(
        GetAppMetadataRequest(request_id=scenario.request_id, app_id=scenario.app_id)
    )
    _assert_response_envelope(metadata_response, scenario=scenario)
    assert metadata_response.app_metadata.app_id == scenario.app_id

    identity_response = await adapter.resolve_current_user(
        ResolveCurrentUserRequest(
            request_id=scenario.request_id,
            app_id=scenario.app_id,
            trusted_subject_reference=scenario.trusted_subject_reference,
            client_hint=scenario.client_hint,
        )
    )
    _assert_response_envelope(identity_response, scenario=scenario)
    assert (
        identity_response.identity.verification_status is not IdentityVerificationStatus.UNVERIFIED
    )

    context_response = await adapter.resolve_context(
        ResolveContextRequest(
            request_id=scenario.request_id,
            app_id=scenario.app_id,
            trusted_identity=identity_response.identity,
            client_hint=scenario.client_hint,
        )
    )
    _assert_response_envelope(context_response, scenario=scenario)
    assert context_response.context.identity == identity_response.identity

    permissions_response = await adapter.get_user_permissions(
        GetUserPermissionsRequest(
            request_id=scenario.request_id,
            app_id=scenario.app_id,
            trusted_identity=identity_response.identity,
            context=context_response.context,
        )
    )
    _assert_response_envelope(permissions_response, scenario=scenario)
    assert permissions_response.authorization_facts.app_id == scenario.app_id

    page_response = await adapter.get_page_metadata(
        GetPageMetadataRequest(
            request_id=scenario.request_id,
            app_id=scenario.app_id,
            trusted_identity=identity_response.identity,
            context=context_response.context,
        )
    )
    _assert_response_envelope(page_response, scenario=scenario)
    assert page_response.page_metadata.page_id == context_response.context.page_id
