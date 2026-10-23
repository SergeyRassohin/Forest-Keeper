"""Owned synthetic fixture expansion with all database guards enabled.

Real immutable Decision rows, copied frozen provenance, not a claim of human workload
or independent source entities. Never call against customer/default data.
"""

from copy import deepcopy
from uuid import uuid4

from sqlalchemy import bindparam, insert, update
from sqlalchemy.orm import Session

from app.auth.models import AuditEvent
from app.conflicts.models import Conflict
from app.decisions.models import Decision
from app.decisions.service import digest


def expand(session: Session, seed: Decision, count: int, transform=None):
    case = session.get(Conflict, seed.conflict_id)
    conflict_values = {c.name: getattr(case, c.name) for c in Conflict.__table__.columns}
    decision_values = {c.name: getattr(seed, c.name) for c in Decision.__table__.columns}
    cases, facts, audits, heads = [], [], [], []
    for _ in range(count):
        case_id, fact_id, audit_id = uuid4(), uuid4(), uuid4()
        snapshot = deepcopy(seed.context_snapshot)
        snapshot["conflict"]["id"] = str(case_id)
        snapshot["review"].update(status="IN_REVIEW", version=1, effective_decision_id=None)
        if transform is not None:
            transform(snapshot)
        cases.append(
            {
                **conflict_values,
                "id": case_id,
                "status": "IN_REVIEW",
                "review_version": 1,
                "current_decision_id": None,
            }
        )
        facts.append(
            {
                **decision_values,
                "id": fact_id,
                "conflict_id": case_id,
                "supersedes_decision_id": None,
                "context_snapshot": snapshot,
                "context_version": digest(snapshot["review"]),
                "evidence_hash": digest(snapshot["conflict"]),
                "audit_event_id": audit_id,
                "idempotency_key": uuid4(),
                "reason": "Synthetic capacity fixture copied from confirmed test evidence.",
            }
        )
        audits.append(
            {
                "id": audit_id,
                "event_type": "SYNTHETIC_DECISION_FIXTURE",
                "object_type": "Decision",
                "object_id": fact_id,
                "payload": {"synthetic": True},
            }
        )
        heads.append({"case_id": case_id, "head_id": fact_id})
    connection = session.connection()
    connection.execute(insert(Conflict), cases)
    connection.execute(insert(AuditEvent), audits)
    connection.execute(insert(Decision), facts)
    connection.execute(
        update(Conflict)
        .where(Conflict.id == bindparam("case_id"))
        .values(current_decision_id=bindparam("head_id"), status="RESOLVED", review_version=2),
        heads,
    )
    session.commit()
    return [r["id"] for r in facts]
