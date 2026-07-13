"""Transaction-owning audit recorder for security-sensitive application services."""

from orkafin.domain.audit import AuditRecord
from orkafin.infrastructure.database.repositories import OrkaFinRepository
from orkafin.infrastructure.database.session import Database


class DatabaseAuditRecorder:
    """Persist each audit fact in its own committed append-only transaction."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def append(self, record: AuditRecord) -> None:
        """Commit an audit before sensitive data is returned or a denial is raised."""
        with self._database.session_factory.begin() as session:
            OrkaFinRepository(session).append_audit_record(record)
