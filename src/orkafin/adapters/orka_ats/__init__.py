"""Permission-aware mock and future HTTP OrkaATS adapter implementations."""

from orkafin.adapters.orka_ats.apps_script import (
    APPS_SCRIPT_ORKA_ATS_ADAPTER_ID,
    APPS_SCRIPT_ORKA_ATS_APP_ID,
    APPS_SCRIPT_WIRE_SCHEMA_VERSION,
    AppsScriptAdapter,
    AppsScriptAdapterConfig,
    AppsScriptFailureEnvelope,
    AppsScriptOrkaATSAdapter,
    AppsScriptRequestEnvelope,
    AppsScriptSuccessEnvelope,
    AsyncHttpTransport,
    HttpTransportError,
    HttpTransportResponse,
    HttpTransportTimeoutError,
    HttpxAsyncHttpTransport,
)
from orkafin.adapters.orka_ats.crypto import (
    SignedPayloadEnvelope,
    canonical_payload_json,
    create_signed_envelope,
)
from orkafin.adapters.orka_ats.mock import (
    MOCK_ORKA_ATS_ADAPTER_ID,
    MOCK_ORKA_ATS_APP_ID,
    MockFailureSimulation,
    MockOrkaATSAdapter,
)
from orkafin.adapters.orka_ats.state import (
    MockCandidateStateConflictError,
    MockIdempotencyConflictError,
    MockOrkaATSState,
    MockOrkaATSStateStore,
    MockStateError,
    MockStoredExecution,
    default_mock_state_path,
)

__all__ = [
    "APPS_SCRIPT_ORKA_ATS_ADAPTER_ID",
    "APPS_SCRIPT_ORKA_ATS_APP_ID",
    "APPS_SCRIPT_WIRE_SCHEMA_VERSION",
    "MOCK_ORKA_ATS_ADAPTER_ID",
    "MOCK_ORKA_ATS_APP_ID",
    "AppsScriptAdapter",
    "AppsScriptAdapterConfig",
    "AppsScriptFailureEnvelope",
    "AppsScriptOrkaATSAdapter",
    "AppsScriptRequestEnvelope",
    "AppsScriptSuccessEnvelope",
    "AsyncHttpTransport",
    "HttpTransportError",
    "HttpTransportResponse",
    "HttpTransportTimeoutError",
    "HttpxAsyncHttpTransport",
    "MockFailureSimulation",
    "MockCandidateStateConflictError",
    "MockIdempotencyConflictError",
    "MockOrkaATSAdapter",
    "MockOrkaATSState",
    "MockOrkaATSStateStore",
    "MockStateError",
    "MockStoredExecution",
    "SignedPayloadEnvelope",
    "canonical_payload_json",
    "create_signed_envelope",
    "default_mock_state_path",
]
