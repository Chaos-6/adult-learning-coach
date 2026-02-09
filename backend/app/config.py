"""
Application configuration loaded from environment variables.

Uses Pydantic Settings to:
1. Read from .env file automatically
2. Validate all required values exist at startup
3. Provide type-safe access throughout the app

Usage:
    from app.config import settings
    print(settings.DATABASE_URL)
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All application configuration in one place."""

    model_config = SettingsConfigDict(
        env_file=".env",        # Load from .env file
        env_file_encoding="utf-8",
        case_sensitive=True,     # ENV_VAR must match exactly
    )

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
