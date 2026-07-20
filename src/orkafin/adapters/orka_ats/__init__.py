"""Permission-aware mock and future HTTP OrkaATS adapter implementations."""

from orkafin.adapters.orka_ats.apps_script import (
    APPS_SCRIPT_ORKA_ATS_ADAPTER_ID,
    APPS_SCRIPT_ORKA_ATS_APP_ID,
    APPS_SCRIPT_WIRE_SCHEMA_VERSION,
    AppsScriptAdapterConfig,
    AppsScriptFailureEnvelope,
    AppsScriptOrkaATSAdapter,
    AppsScriptRequestEnvelope,
    AppsScriptSuccessEnvelope,
    AsyncHttpTransport,
    HttpTransportError,
    HttpTransportResponse,
    HttpTransportTimeoutError,
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
    "AppsScriptAdapterConfig",
    "AppsScriptFailureEnvelope",
    "AppsScriptOrkaATSAdapter",
    "AppsScriptRequestEnvelope",
    "AppsScriptSuccessEnvelope",
    "AsyncHttpTransport",
    "HttpTransportError",
    "HttpTransportResponse",
    "HttpTransportTimeoutError",
    "MockFailureSimulation",
    "MockCandidateStateConflictError",
    "MockIdempotencyConflictError",
    "MockOrkaATSAdapter",
    "MockOrkaATSState",
    "MockOrkaATSStateStore",
    "MockStateError",
    "MockStoredExecution",
    "default_mock_state_path",
]
