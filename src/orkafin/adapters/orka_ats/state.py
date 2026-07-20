"""Isolated, adapter-owned mutable state for the local mock OrkaATS action."""

from __future__ import annotations

import json
from contextlib import suppress
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from threading import RLock
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from orkafin.domain.actions import AdapterExecutionReceipt
from orkafin.domain.base import Identifier
from orkafin.domain.identifiers import IdempotencyKey, Sha256Digest

_STATE_LOCK = RLock()
_IDENTIFIER_ADAPTER = TypeAdapter(Identifier)


class MockStateError(RuntimeError):
    """Base failure for invalid or unavailable adapter-owned mock state."""


class MockCandidateStateConflictError(MockStateError):
    """The candidate value changed before the mock write could commit."""


class MockIdempotencyConflictError(MockStateError):
    """An idempotency key was reused for a different bound request."""


class MockStoredExecution(BaseModel):
    """One durable mock write and its owning-adapter receipt."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    request_fingerprint: Sha256Digest
    candidate_id: Identifier
    previous_start_date: date
    new_start_date: date
    receipt: AdapterExecutionReceipt


class MockOrkaATSState(BaseModel):
    """Complete bounded state owned only by the mock adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    version: Literal[1] = 1
    candidate_start_dates: dict[str, date] = Field(default_factory=dict)
    executions: dict[str, MockStoredExecution] = Field(default_factory=dict)

    @field_validator("candidate_start_dates")
    @classmethod
    def validate_candidate_ids(cls, values: dict[str, date]) -> dict[str, date]:
        for candidate_id in values:
            _IDENTIFIER_ADAPTER.validate_python(candidate_id)
        return values

    @field_validator("executions")
    @classmethod
    def validate_execution_keys(
        cls, values: dict[str, MockStoredExecution]
    ) -> dict[str, MockStoredExecution]:
        for raw_key, execution in values.items():
            key = IdempotencyKey(root=raw_key)
            if execution.receipt.idempotency_key != key:
                raise ValueError("mock state execution key must match its receipt")
            if execution.receipt.target.entity_id != execution.candidate_id:
                raise ValueError("mock state candidate must match its receipt target")
        return values


@dataclass(frozen=True, slots=True)
class MockStateExecution:
    """Stored execution plus whether this call was an idempotent replay."""

    receipt: AdapterExecutionReceipt
    replayed: bool


def default_mock_state_path() -> Path:
    """Return the adapter-owned local state path, outside OrkaFin persistence."""
    return Path(__file__).resolve().parents[4] / "var" / "mock_orka_ats_state.json"


class MockOrkaATSStateStore:
    """Atomically read, compare, mutate, and reset isolated mock state."""

    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path) if path is not None else default_mock_state_path()

    @property
    def path(self) -> Path:
        return self._path

    def reset(self) -> Path:
        """Restore fixture-backed values and remove every execution receipt."""
        with _STATE_LOCK:
            self._write(MockOrkaATSState())
        return self._path

    def snapshot(self) -> MockOrkaATSState:
        """Return a validated immutable snapshot for tests and reconciliation."""
        with _STATE_LOCK:
            return self._read()

    def current_start_date(self, candidate_id: str, fixture_value: date) -> date:
        """Overlay the adapter-owned mutable value on the immutable fixture baseline."""
        with _STATE_LOCK:
            state = self._read()
            return state.candidate_start_dates.get(candidate_id, fixture_value)

    def set_candidate_start_date(self, candidate_id: str, value: date) -> None:
        """Apply a manual mock-only compensating/test operation without an OrkaFin write."""
        with _STATE_LOCK:
            state = self._read()
            dates = dict(state.candidate_start_dates)
            dates[candidate_id] = value
            self._write(state.model_copy(update={"candidate_start_dates": dates}))

    def execute_start_date_update(
        self,
        *,
        candidate_id: str,
        fixture_value: date,
        expected_start_date: date,
        new_start_date: date,
        idempotency_key: IdempotencyKey,
        request_fingerprint: Sha256Digest,
        receipt: AdapterExecutionReceipt,
    ) -> MockStateExecution:
        """Compare-and-set once, returning the original receipt on exact replay."""
        with _STATE_LOCK:
            state = self._read()
            stored = state.executions.get(idempotency_key.root)
            if stored is not None:
                if stored.request_fingerprint != request_fingerprint:
                    raise MockIdempotencyConflictError
                return MockStateExecution(receipt=stored.receipt, replayed=True)

            current_value = state.candidate_start_dates.get(candidate_id, fixture_value)
            if current_value != expected_start_date:
                raise MockCandidateStateConflictError
            if receipt.idempotency_key != idempotency_key:
                raise MockIdempotencyConflictError

            dates = dict(state.candidate_start_dates)
            dates[candidate_id] = new_start_date
            executions = dict(state.executions)
            executions[idempotency_key.root] = MockStoredExecution(
                request_fingerprint=request_fingerprint,
                candidate_id=candidate_id,
                previous_start_date=current_value,
                new_start_date=new_start_date,
                receipt=receipt,
            )
            self._write(
                state.model_copy(update={"candidate_start_dates": dates, "executions": executions})
            )
            return MockStateExecution(receipt=receipt, replayed=False)

    def execution_for(self, idempotency_key: IdempotencyKey) -> MockStoredExecution | None:
        """Support manual reconciliation without reissuing a write."""
        with _STATE_LOCK:
            return self._read().executions.get(idempotency_key.root)

    def _read(self) -> MockOrkaATSState:
        if not self._path.exists():
            self._write(MockOrkaATSState())
        try:
            raw = self._path.read_text(encoding="utf-8")
            decoded = json.loads(raw)
            if decoded == {"version": 1, "actions": []}:
                state = MockOrkaATSState()
                self._write(state)
                return state
            return MockOrkaATSState.model_validate_json(raw)
        except (OSError, ValueError, TypeError) as error:
            raise MockStateError("mock OrkaATS state is unavailable or invalid") from error

    def _write(self, state: MockOrkaATSState) -> None:
        temporary: Path | None = None
        try:
            validated = MockOrkaATSState.model_validate(state.model_dump(mode="python"))
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self._path.with_name(f".{self._path.name}.{uuid4().hex}.tmp")
            temporary.write_text(validated.model_dump_json(indent=2) + "\n", encoding="utf-8")
            temporary.replace(self._path)
        except OSError as error:
            raise MockStateError("mock OrkaATS state could not be written") from error
        finally:
            if temporary is not None and temporary.exists():
                with suppress(OSError):
                    temporary.unlink(missing_ok=True)
