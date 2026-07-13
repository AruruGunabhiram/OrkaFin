"""Initialize the local OrkaFin SQLite schema through Alembic."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config


def main() -> None:
    """Upgrade the configured local database to the current migration head."""
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    command.upgrade(config, "head")


if __name__ == "__main__":
    main()
