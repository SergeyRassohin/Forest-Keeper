import os
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, SecretStr
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SecretsSettingsSource,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FK_", extra="ignore")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        if directory := os.getenv("FK_SECRETS_DIR"):
            file_secret_settings = SecretsSettingsSource(settings_cls, secrets_dir=directory)
        return init_settings, env_settings, dotenv_settings, file_secret_settings

    database_url: SecretStr
    redis_url: SecretStr
    health_timeout_seconds: float = Field(default=0.75, gt=0, le=5)
    session_minutes: int = Field(default=60, ge=5, le=1440)
    allowed_origins: list[str] = ["https://localhost:8443"]
    login_window_seconds: int = Field(default=60, ge=1)
    login_account_limit: int = Field(default=10, ge=1)
    login_ip_limit: int = Field(default=60, ge=1)
    auth_rate_prefix: str = "fk:auth:login:"
    import_storage_root: Path = Path("var/imports")
    import_max_bytes: int = Field(default=100_000_000, ge=1024, le=1_000_000_000)
    import_max_expanded_bytes: int = Field(default=512_000_000, ge=1024)
    import_job_timeout: int = Field(default=900, ge=30, le=7200)
    import_queue_name: str = "forest-keeper"
    deployment_mode: Literal["production", "development", "test"] = "production"
    similarity_provider: Literal["unavailable", "test"] = "unavailable"
    similarity_allow_test_provider: bool = False
    similarity_autoindex: bool = False
    similarity_reads_per_minute: int = Field(default=120, ge=1, le=600)
    recommendation_enabled: bool = False
    recommendation_source_map: dict[str, Any] = Field(default_factory=dict)
