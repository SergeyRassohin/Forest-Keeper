from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FK_", extra="ignore")

    database_url: SecretStr
    redis_url: SecretStr
    health_timeout_seconds: float = Field(default=0.75, gt=0, le=5)
    session_minutes: int = Field(default=60, ge=5, le=1440)
    allowed_origins: list[str] = ["https://localhost:8443"]
    login_window_seconds: int = Field(default=60, ge=1)
    login_account_limit: int = Field(default=10, ge=1)
    login_ip_limit: int = Field(default=60, ge=1)
    auth_rate_prefix: str = "fk:auth:login:"
