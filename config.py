"""
Application configuration and environment validation.
Ensures all required settings are available at startup.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""
    pass


class Config:
    """Application configuration from environment variables."""

    # Required settings
    MODEL: str = os.getenv("MODEL", "willma/default")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")

    # Optional database settings
    POSTGRES_URI: Optional[str] = os.getenv("POSTGRES_URI")
    DATABASE_PATH: Optional[str] = os.getenv("DATABASE_PATH")

    # Optional API keys (at least one must be set for LLM functionality)
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    AZURE_AI_API_KEY: Optional[str] = os.getenv("AZURE_AI_API_KEY")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")

    # Optional authentication
    CHAT_USERS: Optional[str] = os.getenv("CHAT_USERS")  # username:password format
    CHAT_SECRET: Optional[str] = os.getenv("CHAT_SECRET")

    # Optional OIDC/SURFconext
    OIDC_CLIENT_ID: Optional[str] = os.getenv("OIDC_CLIENT_ID")
    OIDC_CLIENT_SECRET: Optional[str] = os.getenv("OIDC_CLIENT_SECRET")
    OIDC_ISSUER_URL: Optional[str] = os.getenv("OIDC_ISSUER_URL")
    SESSION_SECRET: Optional[str] = os.getenv("SESSION_SECRET")

    @classmethod
    def validate(cls) -> None:
        """Validate required configuration at startup."""
        errors = []

        # Check model is valid format (provider/model-name)
        if not cls.MODEL or "/" not in cls.MODEL:
            errors.append(f"MODEL must be in format 'provider/model-name', got: {cls.MODEL}")

        if errors:
            for error in errors:
                logger.error(error)
            raise ConfigError("; ".join(errors))

        logger.info(f"Configuration validated. Model: {cls.MODEL}, Database: {'PostgreSQL' if cls.POSTGRES_URI else 'SQLite'}")

    @classmethod
    def get_parsed_cors_origins(cls) -> list[str]:
        """Parse CORS_ORIGINS into a list."""
        return [o.strip() for o in cls.CORS_ORIGINS.split(",")]

    @classmethod
    def is_production(cls) -> bool:
        """Check if running in production environment."""
        return bool(cls.POSTGRES_URI) and bool(cls.SESSION_SECRET)
