from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # SQLite keeps local runs and tests dependency-free; production points this at Postgres.
    database_url: str = "sqlite+aiosqlite:///./wardwatch.db"
    cors_origins: str = "http://localhost:5173"
    simulate: bool = True
    tick_seconds: float = 2.0
    keep_minutes: int = 30

    @field_validator("database_url")
    @classmethod
    def use_async_driver(cls, value: str) -> str:
        # Hosting providers hand out plain postgres:// URLs; SQLAlchemy needs the async psycopg driver named.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
