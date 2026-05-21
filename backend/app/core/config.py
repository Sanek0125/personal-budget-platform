from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    app_name: str = "Personal Budget Backend"
    environment: str = "local"
    debug: bool = False

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "budget"
    postgres_password: str = "budget"
    postgres_db: str = "budget"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """Build the async SQLAlchemy PostgreSQL DSN from DB settings."""
        url = URL.create(
            drivername="postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )
        return url.render_as_string(hide_password=False)


@lru_cache
def get_settings() -> Settings:
    """Return cached process-wide settings."""
    return Settings()
