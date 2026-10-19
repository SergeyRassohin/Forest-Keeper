from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.models import AuditEvent
from app.imports.models import ImportBatch, ImportStatus

TRANSITIONS = {
    ImportStatus.NEW: {ImportStatus.QUEUED},
    ImportStatus.QUEUED: {ImportStatus.PROCESSING, ImportStatus.FAILED},
    ImportStatus.PROCESSING: {
        ImportStatus.COMPLETED,
        ImportStatus.COMPLETED_WITH_ERRORS,
        ImportStatus.FAILED,
    },
}


def audit_import(
    session: Session,
    event: str,
    batch: ImportBatch,
    actor: UUID | None,
    details: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditEvent(
            event_type=event,
            user_id=actor,
            object_type="ImportBatch",
            object_id=batch.id,
            payload={"source_system_id": str(batch.source_system_id), **(details or {})},
        )
    )


def transition(session: Session, batch: ImportBatch, target: ImportStatus) -> None:
    if target not in TRANSITIONS.get(ImportStatus(batch.status), set()):
        raise ValueError("Forbidden import transition")
    batch.status = target
    audit_import(session, "IMPORT_" + target, batch, None)
