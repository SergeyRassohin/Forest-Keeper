from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from app.auth.models import Role, User, UserStatus
from app.auth.policy import permissions_for


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    login: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(min_length=1, max_length=128)


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    login: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.@-]+$")
    full_name: str = Field(min_length=1, max_length=200)
    job_title: str = Field(default="", max_length=200)
    password: SecretStr = Field(min_length=12, max_length=128)
    roles: list[Role] = Field(default_factory=list, max_length=4)

    @field_validator("login")
    @classmethod
    def normalize_login(cls, value: str) -> str:
        return value.casefold()


class UserView(BaseModel):
    id: UUID
    login: str
    full_name: str
    display_name: str
    job_title: str
    status: UserStatus
    roles: list[Role]
    permissions: list[str]

    @classmethod
    def of(cls, user: User) -> "UserView":
        return cls(
            id=user.id,
            login=user.login,
            full_name=user.full_name,
            display_name=user.full_name,
            job_title=user.job_title,
            status=UserStatus(user.status),
            roles=sorted(Role(role.role_code) for role in user.roles),
            permissions=permissions_for(user),
        )


class LoginResponse(BaseModel):
    user: UserView
