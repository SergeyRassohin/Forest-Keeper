import json
from pathlib import Path

from app.auth.models import Role, User

_catalog: dict[str, list[str]] = json.loads(
    Path(__file__).with_name("permissions.json").read_text()
)["permissions"]
PERMISSIONS: dict[str, frozenset[Role]] = {
    code: frozenset(Role(role) for role in roles) for code, roles in _catalog.items()
}


def permissions_for(user: User) -> list[str]:
    roles = {Role(assignment.role_code) for assignment in user.roles}
    return sorted(code for code, allowed in PERMISSIONS.items() if roles & allowed)


def permits(user: User, permission: str) -> bool:
    return permission in permissions_for(user)
