"""Cooperating application writes; no distributed/config or superuser guarantee."""

import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.common.errors import ApiError


@dataclass
class Budget:
    deadline: float = field(default_factory=lambda: time.monotonic() + 1.5)
    _connections: set[int] = field(default_factory=set, init=False, repr=False)

    def remaining(self) -> int:
        value = int((self.deadline - time.monotonic()) * 1000)
        if value <= 0:
            raise ApiError(
                503, "RECOMMENDATION_TIMEOUT", "Подготовка рекомендации временно недоступна"
            )
        return value

    def arm(self, session: Session) -> None:
        self.remaining()
        connection = session.connection()
        identity = id(connection)
        if identity in self._connections:
            return
        self._connections.add(identity)

        def before_sql(
            conn: Any,
            cursor: Any,
            statement: Any,
            parameters: Any,
            context: Any,
            executemany: Any,
        ) -> None:
            value = str(self.remaining()) + "ms"
            # Raw cursor avoids recursively invoking SQLAlchemy's SQL event.
            cursor.execute(
                "SELECT set_config('statement_timeout', %s, true), "
                "set_config('lock_timeout', %s, true)",
                (value, value),
            )

        def release(owner: Session, transaction: Any) -> None:
            if transaction.parent is None and identity in self._connections:
                event.remove(connection, "before_cursor_execute", before_sql)
                self._connections.discard(identity)

        event.listen(connection, "before_cursor_execute", before_sql)
        event.listen(session, "after_transaction_end", release)

    def prepare_commit(self, session: Session) -> None:
        self.arm(session)
        # COMMIT goes through DBAPI rather than before_cursor_execute. Set the
        # latest remaining deadline immediately before its deferred constraints.
        session.execute(text("SELECT 1"))


def basis_lock(session: Session, *, exclusive: bool = False, budget: Budget | None = None) -> None:
    """Gate precedes every Conflict/state/user row lock. Ordinary writers stay parallel."""
    if budget:
        budget.arm(session)
    previous = session.scalar(text("SELECT current_setting('lock_timeout')"))
    session.execute(
        text("SELECT set_config('lock_timeout', :value, true)"),
        {"value": str(budget.remaining() if budget else 1500) + "ms"},
    )
    if budget:
        budget.arm(session)
    function = "pg_advisory_xact_lock" if exclusive else "pg_advisory_xact_lock_shared"
    # Only the fixed function name varies; schema/database names never become SQL text.
    session.execute(
        text(
            "SELECT " + function + "(hashtextextended(current_database() || ':' || "
            "current_schema() || :namespace, 0))"
        ),
        {"namespace": ":fk-recommendation-basis-v1"},
    )
    if not budget:
        session.execute(
            text("SELECT set_config('lock_timeout', :value, true)"), {"value": previous}
        )
