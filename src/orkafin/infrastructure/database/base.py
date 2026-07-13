"""SQLAlchemy declarative base and shared SQLite value helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    """Return an aware UTC timestamp for application-created records."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Base class for OrkaFin-owned relational records."""


class CreatedAtMixin:
    """Common immutable creation timestamp."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
