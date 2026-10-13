from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FK_", extra="ignore")

    database_url: SecretStr
    redis_url: SecretStr
    health_timeout_seconds: float = Field(default=0.75, gt=0, le=5)
