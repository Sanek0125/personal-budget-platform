from app.core.config import Settings


def test_settings_builds_async_postgres_url_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("APP_NAME", "Budget API")
    monkeypatch.setenv("POSTGRES_HOST", "db")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    monkeypatch.setenv("POSTGRES_USER", "budget")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    monkeypatch.setenv("POSTGRES_DB", "budget_test")

    settings = Settings()

    assert settings.app_name == "Budget API"
    assert settings.database_url == (
        "postgresql+asyncpg://budget:secret@db:5433/budget_test"
    )


def test_settings_escapes_database_credentials(monkeypatch) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_USER", "budget@app")
    monkeypatch.setenv("POSTGRES_PASSWORD", "se:cr/et@word")
    monkeypatch.setenv("POSTGRES_DB", "budget")

    settings = Settings()

    assert settings.database_url == (
        "postgresql+asyncpg://budget%40app:se%3Acr%2Fet%40word@localhost:5432/budget"
    )
