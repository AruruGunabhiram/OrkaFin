"""CLI validation entry point for version-controlled knowledge."""

from __future__ import annotations

import argparse
from pathlib import Path

from orkafin.knowledge.loader import KnowledgeValidationError, load_knowledge


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an OrkaFin knowledge catalog.")
    parser.add_argument(
        "knowledge_root", type=Path, help="Catalog directory, such as knowledge/orka_ats"
    )
    arguments = parser.parse_args()
    try:
        index = load_knowledge(arguments.knowledge_root)
    except KnowledgeValidationError as error:
        print(f"Knowledge validation failed: {error}")
        return 1

    print(
        f"Knowledge validation passed: app={index.manifest.app_id} "
        f"version={index.manifest.provenance.content_version}"
    )
    for name, count in index.summary_counts.items():
        print(f"{name}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
