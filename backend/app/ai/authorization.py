"""Fresh existing session, XLSX permission and scope checks for deferred AI input."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.contracts import AIError
from app.auth.models import AuthSession, User, UserStatus
from app.auth.policy import permits
from app.conflicts.models import Conflict
from app.decisions.service import case_for


def actor_case(
    session: Session, actor_id: str | None, token_hash: str | None, case_id: UUID
) -> tuple[User, Conflict]:
    if actor_id is None or token_hash is None:
        raise AIError("AI_AUTHORIZATION_REQUIRED")
    record = session.get(AuthSession, token_hash)
    actor = session.get(User, UUID(actor_id))
    if (
        record is None
        or actor is None
        or record.user_id != actor.id
        or record.revoked_at is not None
        or record.expires_at <= datetime.now(UTC)
        or actor.status != UserStatus.ACTIVE
        or not all(
            permits(actor, permission)
            for permission in ("conflict.view", "decision.view", "recommendation.view")
        )
    ):
        raise AIError("AI_ACCESS_REVOKED")
    return actor, case_for(session, case_id, actor)
