"""Reset isolated mock-OrkaATS state used by future local action exercises."""

from __future__ import annotations

import argparse
from pathlib import Path


def mock_state_path() -> Path:
    return Path(__file__).resolve().parents[4] / "var" / "mock_orka_ats_state.json"


def reset_mock_state() -> Path:
    """Create the empty adapter-owned state file without touching OrkaFin's database."""
    state_path = mock_state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text('{"version": 1, "actions": []}\n', encoding="utf-8")
    return state_path


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
