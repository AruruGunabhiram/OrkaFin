"""Read redacted Local V1 events and audits without exposing an API endpoint."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from orkafin.core.logging import redact_value

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = REPOSITORY_ROOT / "var" / "orkafin.db"
ActivityKind = Literal["events", "audits", "all"]


class ActivityInspectionError(RuntimeError):
    """Raised when the local-only read command cannot safely inspect its input."""


def _safe_database_path(value: Path) -> Path:
    path = value.resolve()
    if value.is_symlink() or not path.is_file():
        raise ActivityInspectionError("database must be an existing regular SQLite file")
    return path


def _parse_json(value: str) -> object:
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return {"stored_value": "[REDACTED]"}


def _event_rows(connection: sqlite3.Connection, limit: int) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT event_id, event_type, source, app_id, actor_user_id, workspace_id,
               entity_type, entity_id, metadata_json, occurred_at, request_id
        FROM user_events
        ORDER BY occurred_at DESC, event_id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [
        {
            "event_id": row["event_id"],
            "event_type": row["event_type"],
            "source": row["source"],
            "app_id": row["app_id"],
            "actor_user_id": row["actor_user_id"],
            "workspace_id": row["workspace_id"],
            "entity": (
                {"type": row["entity_type"], "id": row["entity_id"]}
                if row["entity_type"] is not None and row["entity_id"] is not None
                else None
            ),
            "metadata": redact_value(_parse_json(row["metadata_json"])),
            "occurred_at": row["occurred_at"],
            "request_id": row["request_id"],
        }
        for row in rows
    ]


def _audit_rows(connection: sqlite3.Connection, limit: int) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT audit_id, event_type, outcome, actor_user_id, workspace_id, app_id,
               target_entity_type, target_entity_id, action_id, details_json, occurred_at,
               request_id, correlation_id
        FROM audit_records
        ORDER BY occurred_at DESC, audit_id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [
        {
            "audit_id": row["audit_id"],
            "event_type": row["event_type"],
            "outcome": row["outcome"],
            "actor_user_id": row["actor_user_id"],
            "workspace_id": row["workspace_id"],
            "app_id": row["app_id"],
            "target": (
                {"type": row["target_entity_type"], "id": row["target_entity_id"]}
                if row["target_entity_type"] is not None and row["target_entity_id"] is not None
                else None
            ),
            "action_id": row["action_id"],
            "details": redact_value(_parse_json(row["details_json"])),
            "occurred_at": row["occurred_at"],
            "request_id": row["request_id"],
            "correlation_id": row["correlation_id"],
        }
        for row in rows
    ]


def inspect_local_activity(
    database: Path = DEFAULT_DATABASE,
    *,
    kind: ActivityKind = "all",
    limit: int = 50,
) -> dict[str, object]:
    """Return bounded, content-redacted event/audit rows through a read-only SQLite URI."""
    if not 1 <= limit <= 200:
        raise ActivityInspectionError("limit must be between 1 and 200")
    path = _safe_database_path(database)
    uri = f"file:{path.as_posix()}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only = ON")
            payload: dict[str, object] = {
                "database": str(path.relative_to(REPOSITORY_ROOT))
                if path.is_relative_to(REPOSITORY_ROOT)
                else "external_local_sqlite",
            }
            if kind in {"events", "all"}:
                payload["events"] = _event_rows(connection, limit)
            if kind in {"audits", "all"}:
                payload["audits"] = _audit_rows(connection, limit)
            return payload
        finally:
            connection.close()
    except sqlite3.Error as error:
        raise ActivityInspectionError(
            "database is not initialized with the Local V1 schema"
        ) from error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect redacted Local V1 SQLite events/audits; this never opens an HTTP route."
        )
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE,
        help="Local SQLite database path (default: var/orkafin.db).",
    )
    parser.add_argument("--kind", choices=("events", "audits", "all"), default="all")
    parser.add_argument("--limit", type=int, default=50, help="Rows per selected kind (1-200).")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        output = inspect_local_activity(
            arguments.database,
            kind=arguments.kind,
            limit=arguments.limit,
        )
    except ActivityInspectionError as error:
        print(f"Unable to inspect local activity: {error}", file=sys.stderr)
        return 2
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
