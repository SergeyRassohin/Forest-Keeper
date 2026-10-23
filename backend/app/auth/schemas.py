from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from app.auth.models import Role, User, UserStatus
from app.auth.policy import permissions_for


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    login: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(min_length=1, max_length=128)


class DomainScope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data_domains: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("data_domains")
    @classmethod
    def validate_domains(cls, values: list[str]) -> list[str]:
        if any(
            not value
            or value != value.strip()
            or len(value) > 100
            or any(ord(char) < 32 or 127 <= ord(char) < 160 for char in value)
            for value in values
        ):
            raise ValueError("Invalid domain scope")
        if "*" in values and values != ["*"]:
            raise ValueError("Wildcard must be an explicit standalone grant")
        return sorted(set(values))


class UserCreate(DomainScope):
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
    data_domains: list[str]

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
            data_domains=list(user.data_domains or []),
        )


class LoginResponse(BaseModel):
    user: UserView
