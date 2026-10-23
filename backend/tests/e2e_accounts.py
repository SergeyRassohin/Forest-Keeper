"""Owned temporary development accounts for the real HTTPS browser checks."""

import json
import os
import re
import secrets
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.auth.models import Role, User, UserRole
from app.auth.security import hash_password
from app.common.config import Settings
from app.common.database import make_engine


def main() -> None:
    if os.getenv("FK_TEST_INTEGRATION") != "1":
        raise SystemExit("Development test account creation requires FK_TEST_INTEGRATION=1.")
    path = Path(__file__).resolve().parents[2] / "deploy/local/e2e.json"
    engine = make_engine(Settings())  # type: ignore[call-arg]
    try:
        if sys.argv[1] == "cleanup":
            data = json.loads(path.read_text())
            prefix = data["prefix"]
            if not re.fullmatch(r"e2e_[a-f0-9]{32}", prefix):
                raise SystemExit("Refusing to clean unknown account prefix.")
            with Session(engine) as session:
                session.execute(
                    delete(User).where(User.login.startswith(prefix + "_", autoescape=True))
                )
                session.commit()
            path.unlink()
            return
        if path.exists():
            raise SystemExit("Existing E2E fixture: run cleanup before preparing another run.")
        prefix = "e2e_" + uuid4().hex
        data = {"prefix": prefix}
        with path.open("x") as output:
            os.chmod(path, 0o600)
            with Session(engine) as session:
                for role in (Role.ADMIN, Role.VIEWER, Role.REVIEWER, Role.DATA_OWNER):
                    login = prefix + "_" + role.lower()
                    password = secrets.token_urlsafe(24)
                    session.add(
                        User(
                            login=login,
                            data_domains=["*"],
                            full_name="E2E " + role,
                            password_hash=hash_password(password),
                            roles=[UserRole(role_code=role)],
                        )
                    )
                    data[role] = {"login": login, "password": password}
                json.dump(data, output)
                session.commit()
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
