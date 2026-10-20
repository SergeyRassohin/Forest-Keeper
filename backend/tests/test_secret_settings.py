import secrets

from app.common.config import Settings


def test_file_secret_supplies_database_url_without_sensitive_environment(tmp_path, monkeypatch):
    value = "postgresql+psycopg://user:" + secrets.token_hex(24) + "@postgres/db"
    (tmp_path / "fk_database_url").write_text(value)
    monkeypatch.delenv("FK_DATABASE_URL", raising=False)
    monkeypatch.setenv("FK_SECRETS_DIR", str(tmp_path))
    monkeypatch.setenv("FK_REDIS_URL", "redis://redis:6379/0")
    settings = Settings()
    assert settings.database_url.get_secret_value() == value
    assert value not in repr(settings)


def test_existing_development_environment_precedence_is_unchanged(tmp_path, monkeypatch):
    (tmp_path / "fk_database_url").write_text("postgresql+psycopg://file/db")
    monkeypatch.setenv("FK_SECRETS_DIR", str(tmp_path))
    monkeypatch.setenv("FK_DATABASE_URL", "postgresql+psycopg://development/db")
    settings = Settings(redis_url="redis://localhost/0")
    assert settings.database_url.get_secret_value() == "postgresql+psycopg://development/db"
