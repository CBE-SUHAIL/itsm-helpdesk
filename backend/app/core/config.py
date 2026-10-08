"""Application settings, loaded from the repository-root .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> repository root
ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Values come from environment variables, falling back to the root .env."""

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "itsm"
    postgres_password: str = "itsm_local_dev_only"
    postgres_db: str = "itsm"

    frontend_origin: str = "http://localhost:5173"

    @property
    def database_url(self) -> str:
        """Built from the POSTGRES_* parts so credentials cannot drift.

        compose.yaml creates the container from the same variables, so the
        database the app connects to is always the one Compose started.
        """
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """Cached so the .env file is read once per process."""
    return Settings()
