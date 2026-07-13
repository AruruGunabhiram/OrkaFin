"""Security assertions for the mock adapter's candidate ownership boundary."""

from __future__ import annotations

import inspect

from orkafin.adapters.orka_ats.mock import MockOrkaATSAdapter


def test_mock_adapter_public_api_contains_no_raw_candidate_retrieval_method() -> None:
    public_methods = {
        name
        for name, member in inspect.getmembers(MockOrkaATSAdapter, predicate=inspect.isfunction)
        if not name.startswith("_")
    }
    assert "get_candidate" not in public_methods
    assert "get_full_candidate" not in public_methods
    assert public_methods == {
        "execute_approved_action",
        "get_app_metadata",
        "get_available_actions",
        "get_available_features",
        "get_page_metadata",
        "get_recent_user_events",
        "get_selected_entity_summary",
        "get_user_permissions",
        "log_feedback",
        "resolve_context",
        "resolve_current_user",
        "search_allowed_records",
    }
