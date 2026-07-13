"""Validate that the version-controlled knowledge scaffold is present.

Prompt 2 intentionally has no catalog schema or loader. Prompt 6 will replace this
structural check with catalog-aware validation while retaining the same command.
"""

from __future__ import annotations

from pathlib import Path


def main() -> int:
    repository_root = Path(__file__).resolve().parents[1]
    knowledge_root = repository_root / "knowledge" / "orka_ats"
    if not knowledge_root.is_dir():
        print(f"Missing knowledge scaffold: {knowledge_root}")
        return 1

    print(f"Knowledge scaffold is present: {knowledge_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
