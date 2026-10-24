"""Add only owned demo identities to an existing disposable E2E fixture."""

import json
import os
import secrets
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.security import hash_password
from app.common.config import Settings
from app.common.database import make_engine


def main() -> None:
    if os.getenv("FK_TEST_INTEGRATION") != "1":
        raise SystemExit("Development UI gallery requires FK_TEST_INTEGRATION=1")
    path = Path(__file__).resolve().parents[2] / "deploy/local/e2e.json"
    data = json.loads(path.read_text())
    if not data["prefix"].startswith("e2e_"):
        raise SystemExit("An owned E2E fixture is required")
    engine = make_engine(Settings())  # type: ignore[call-arg]
    try:
        with Session(engine) as session:
            for role, name in [
                ("ADMIN", "Администратор демонстрации"),
                ("REVIEWER", "Эксперт каталога"),
                ("VIEWER", "Наблюдатель"),
                ("DATA_OWNER", "Владелец демонстрационных данных"),
            ]:
                user = session.scalar(select(User).where(User.login == data[role]["login"]))
                if user is None:
                    raise SystemExit("Owned identity is missing")
                user.full_name = name
            login = data["prefix"] + "_guest"
            password = secrets.token_urlsafe(24)
            session.add(
                User(
                    login=login,
                    full_name="Без назначенной роли",
                    password_hash=hash_password(password),
                    roles=[],
                )
            )
            session.commit()
        data["NO_ROLES"] = {"login": login, "password": password}
        path.write_text(json.dumps(data, ensure_ascii=False))
        path.chmod(0o600)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
