import argparse
import getpass
import sys

from pydantic import SecretStr
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth.models import AuditEvent, Role, User, UserRole
from app.auth.schemas import UserCreate
from app.auth.security import hash_password
from app.common.config import Settings
from app.common.database import make_engine


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the first ADMIN offline, once.")
    parser.add_argument("--login", required=True)
    parser.add_argument("--full-name", required=True)
    parser.add_argument("--password-stdin", action="store_true")
    args = parser.parse_args()
    password = sys.stdin.readline().rstrip("\n") if args.password_stdin else getpass.getpass()
    try:
        body = UserCreate(
            login=args.login,
            full_name=args.full_name,
            password=SecretStr(password),
            roles=[Role.ADMIN],
        )
    except ValueError:
        parser.exit(1, "Invalid login or password: password must contain 12–128 characters.\n")
    engine = make_engine(Settings())  # type: ignore[call-arg]
    try:
        with Session(engine) as session:
            # Serialize bootstrap with user creation; never elevate an existing account.
            session.execute(text("LOCK TABLE users IN EXCLUSIVE MODE"))
            if session.scalar(select(func.count()).select_from(User)):
                parser.exit(1, "Bootstrap refused: users already exist.\n")
            user = User(
                login=body.login,
                full_name=body.full_name,
                job_title="",
                password_hash=hash_password(password),
                roles=[UserRole(role_code="ADMIN")],
            )
            session.add(user)
            session.flush()
            session.add(
                AuditEvent(
                    event_type="ADMIN_BOOTSTRAPPED",
                    user_id=None,
                    object_type="User",
                    object_id=user.id,
                    payload={},
                )
            )
            session.commit()
        print("Initial ADMIN created. No business role was assigned.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
