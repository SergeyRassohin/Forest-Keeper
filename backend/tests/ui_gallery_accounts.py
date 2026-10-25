"""Add only owned demo identities to an existing disposable E2E fixture."""

import json
import os
import secrets
import sys
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.security import hash_password
from app.common.config import Settings
from app.common.database import make_engine
from app.imports.models import SourceSystem
from app.matching.profiles import catalog


def main() -> None:
    if os.getenv("FK_TEST_INTEGRATION") != "1":
        raise SystemExit("Development UI gallery requires FK_TEST_INTEGRATION=1")
    if len(sys.argv) == 2 and sys.argv[1] == "declaration":
        profile = next(p for p in catalog().values() if p.code == "synthetic-material")
        print(
            json.dumps(
                {
                    "version": "gallery-explicit-sources-v1",
                    "approved": True,
                    "approval_reference": (
                        "Isolated gallery operator explicitly assigns these source identities."
                    ),
                    "domain": "synthetic-material",
                    "entity_type": "Material",
                    "attribute_code": "mass",
                    "matching_profile_hashes": [profile.digest()],
                    "sources": [
                        {"source_id": str(uuid4()), "source_type": source_type, "role": role}
                        for source_type, role in [
                            ("FILE", "REGISTER_EXPORT"),
                            ("ONE_C", "ACCOUNTING_EXPORT"),
                        ]
                    ],
                }
            )
        )
        return
    path = Path(__file__).resolve().parents[2] / "deploy/local/e2e.json"
    data = json.loads(path.read_text())
    if not data["prefix"].startswith("e2e_"):
        raise SystemExit("An owned E2E fixture is required")
    engine = make_engine(Settings())  # type: ignore[call-arg]
    try:
        with Session(engine) as session:
            declaration = json.loads(os.environ["FK_GALLERY_SOURCE_DECLARATION"])
            for index, source in enumerate(declaration["sources"]):
                session.add(
                    SourceSystem(
                        id=UUID(source["source_id"]),
                        code=data["prefix"] + "_recommendation_" + str(index),
                        name="Stage 8 рабочий реестр" if index == 0 else "Stage 8 учётная система",
                        source_type=source["source_type"],
                        status="ACTIVE",
                        authority_scope={},
                    )
                )
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
        data["recommendation_sources"] = declaration["sources"]
        path.write_text(json.dumps(data, ensure_ascii=False))
        path.chmod(0o600)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
