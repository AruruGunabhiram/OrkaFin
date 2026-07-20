"""Regression coverage for the checked demo and local-only activity inspector scripts."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path
from types import ModuleType

import pytest

from orkafin.core.config import Settings

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _script_module(filename: str) -> ModuleType:
    path = REPOSITORY_ROOT / "scripts" / filename
    module_name = f"test_script_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_local_demo_plan_requires_only_the_documented_loopback_fixture_boundary() -> None:
    demo = _script_module("run_local_demo.py")

    plan = demo.build_local_demo_plan(
        settings=Settings(), subject="admin", host="127.0.0.1", port=8000, reload=False
    )

    assert plan.subject == "admin"
    with pytest.raises(demo.DemoConfigurationError, match="loopback"):
        demo.build_local_demo_plan(
            settings=Settings(), subject="admin", host="0.0.0.0", port=8000, reload=False
        )
    with pytest.raises(demo.DemoConfigurationError, match="verified synthetic fixture"):
        demo.build_local_demo_plan(
            settings=Settings(), subject="unverified", host="127.0.0.1", port=8000, reload=False
        )
    with pytest.raises(demo.DemoConfigurationError, match="deterministic"):
        demo.build_local_demo_plan(
            settings=Settings(
                ai_provider="external", ai_provider_api_key="test-key", ai_provider_model="x"
            ),
            subject="admin",
            host="127.0.0.1",
            port=8000,
            reload=False,
        )


def test_activity_inspector_reads_only_and_redacts_metadata_and_audit_details(
    tmp_path: Path,
) -> None:
    inspector = _script_module("inspect_local_activity.py")
    database = tmp_path / "activity.db"
    token = "sk-" + "Z" * 24
    email = "demo.marker@example.invalid"
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            """
            CREATE TABLE user_events (
                event_id TEXT, event_type TEXT, source TEXT, app_id TEXT, actor_user_id TEXT,
                workspace_id TEXT, entity_type TEXT, entity_id TEXT, metadata_json TEXT,
                occurred_at TEXT, request_id TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE audit_records (
                audit_id TEXT, event_type TEXT, outcome TEXT, actor_user_id TEXT,
                workspace_id TEXT, app_id TEXT, target_entity_type TEXT, target_entity_id TEXT,
                action_id TEXT, details_json TEXT, occurred_at TEXT, request_id TEXT,
                correlation_id TEXT
            )
            """
        )
        connection.execute(
            "INSERT INTO user_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "event:1",
                "page_viewed",
                "orkafin",
                "orka_ats",
                "mock-user-admin",
                "workspace_recruiting_alpha",
                None,
                None,
                json.dumps({"note": f"email={email}; token={token}"}),
                "2026-07-19T20:00:00Z",
                "00000000-0000-4000-8000-000000000021",
            ),
        )
        connection.execute(
            "INSERT INTO audit_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "audit:1",
                "candidate_read",
                "allowed",
                "mock-user-admin",
                "workspace_recruiting_alpha",
                "orka_ats",
                "candidate",
                "CAND-1042",
                None,
                json.dumps({"details": f"bearer {token}; {email}"}),
                "2026-07-19T20:00:00Z",
                "00000000-0000-4000-8000-000000000021",
                "00000000-0000-4000-8000-000000000021",
            ),
        )
        connection.commit()
    finally:
        connection.close()

    output = inspector.inspect_local_activity(database, limit=1)
    serialized = json.dumps(output)

    assert token not in serialized
    assert email not in serialized
    assert "[REDACTED]" in serialized
    assert output["events"]
    assert output["audits"]
    with pytest.raises(inspector.ActivityInspectionError, match="limit"):
        inspector.inspect_local_activity(database, limit=0)
