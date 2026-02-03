"""Backend configuration."""
import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings."""

    # API
    api_title: str = "Robin API"
    api_version: str = "1.0.0"
    api_prefix: str = "/api/v1"
    debug: bool = False

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Database
    database_url: str = "postgresql+asyncpg://robin:robin@localhost:5432/robin"

    # Agent
    default_model: str = "claude-sonnet-4-5-20250514"
    max_agent_turns: int = 20

    # Tor
    tor_socks_proxy: str = "socks5h://127.0.0.1:9050"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
