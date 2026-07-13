"""Compatibility wrapper for the Prompt 6 catalog-aware validation command."""

from __future__ import annotations

import sys

from orkafin.knowledge.validate import main as validate_main


def main() -> int:
    if len(sys.argv) == 1:
        sys.argv.append("knowledge/orka_ats")
    return validate_main()


if __name__ == "__main__":
    raise SystemExit(main())
