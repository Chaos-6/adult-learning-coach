"""
Application configuration loaded from environment variables.

Uses Pydantic Settings to:
1. Read from .env file automatically
2. Validate all required values exist at startup
3. Provide type-safe access throughout the app

Usage:
    from app.config import settings
    print(settings.DATABASE_URL)

Note: We use a custom Settings source that prefers .env values over
empty shell environment variables. This prevents empty env vars
(like ANTHROPIC_API_KEY="" from Claude Desktop) from overriding
real values in the .env file.
"""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All application configuration in one place."""

    model_config = SettingsConfigDict(
        env_file=".env",        # Load from .env file
        env_file_encoding="utf-8",
        case_sensitive=True,     # ENV_VAR must match exactly
        extra="ignore",         # Skip unknown env vars (e.g. VIMEO_ACCESS_TOKEN)
    )

    @model_validator(mode="before")
    @classmethod
    def prefer_dotenv_over_empty_env(cls, data):
        """Always prefer .env file values over shell environment variables.

        Pydantic Settings normally prioritizes shell env vars over .env.
        This causes two problems:
        1. Claude Desktop sets ANTHROPIC_API_KEY="" (empty) in the shell
        2. After rotating keys, the shell may still have the OLD key set

        Fix: load .env values and use them for ALL keys that have a value
        in .env, overriding whatever the shell has.
        """
        from pathlib import Path

        from dotenv import dotenv_values

        # Find .env relative to this file (backend/.env), not cwd
        env_path = Path(__file__).resolve().parent.parent / ".env"
        dotenv_vals = dotenv_values(env_path)

        for key, dotenv_value in dotenv_vals.items():
            # .env always wins if it has a non-empty value
            if dotenv_value:
                data[key] = dotenv_value
        return data

    # --- Database ---
    DATABASE_URL: str
    DATABASE_URL_SYNC: str = ""  # Optional: for migrations

    # --- AI APIs ---
    ANTHROPIC_API_KEY: str = ""
    ASSEMBLYAI_API_KEY: str = ""

    # --- Task Queue ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- AWS ---
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-west-2"
    AWS_S3_BUCKET: str = "coaching-videos"

    # --- Security ---
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- Application ---
    APP_ENV: str = "development"
    DEBUG: bool = True
    CORS_ORIGINS: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


# Singleton instance — import this everywhere
settings = Settings()
