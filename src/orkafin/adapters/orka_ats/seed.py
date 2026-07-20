"""Reset isolated mock-OrkaATS state used by future local action exercises."""

from __future__ import annotations

import argparse
from pathlib import Path

from orkafin.adapters.orka_ats.state import (
    MockOrkaATSStateStore,
    default_mock_state_path,
)


def mock_state_path() -> Path:
    return default_mock_state_path()


def reset_mock_state() -> Path:
    """Reset adapter-owned values and receipts without touching OrkaFin's database."""
    return MockOrkaATSStateStore(mock_state_path()).reset()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed or reset mock OrkaATS state.")
    parser.add_argument("--reset", action="store_true", help="Reset isolated mock state.")
    args = parser.parse_args()
    if args.reset:
        print(reset_mock_state())
        return
    parser.error("--reset is required; fixture source data is version-controlled")


if __name__ == "__main__":
    main()
