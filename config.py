"""
Serverconfiguratie en validatie bij het opstarten: logging, CORS, database, OIDC.
Runtime-instellingen (model, limieten, vlaggen) staan in core/config.py (#234).
"""

import logging
import os

from core.config import MODEL

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""

    pass


class Config:
    """Application configuration from environment variables."""

    # Required settings
    MODEL: str = MODEL  # één default, in core/config.py (#234)
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    # Leeg = geen cross-origin toegang: de frontend praat via dezelfde origin (#421).
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "")

    # Commit van het image, meegegeven als build-arg in CI (#231)
    GIT_COMMIT: str | None = os.getenv("GIT_COMMIT")

    # Release waarop de omgeving draait: het chart zet hem uit de chartversie (de release-tag).
    # Het image wordt op main gebouwd en bij een tag alleen gepromoveerd, dus de tag is er pas bij deploy.
    APP_VERSION: str | None = os.getenv("APP_VERSION")

    # Optional database settings
    POSTGRES_URI: str | None = os.getenv("POSTGRES_URI")

    # Optional API keys (at least one must be set for LLM functionality)
    ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")
    AZURE_AI_API_KEY: str | None = os.getenv("AZURE_AI_API_KEY")
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    GOOGLE_API_KEY: str | None = os.getenv("GOOGLE_API_KEY")

    # Optional OIDC/SRAM (see skill sram-oidc for the CEDA convention)
    OIDC_PROVIDER: str | None = os.getenv("OIDC_PROVIDER")
    OIDC_DISCOVERY_URL: str | None = os.getenv("OIDC_DISCOVERY_URL")
    OIDC_CLIENT_ID: str | None = os.getenv("OIDC_CLIENT_ID")
    OIDC_CLIENT_SECRET: str | None = os.getenv("OIDC_CLIENT_SECRET")
    SERVER_URL: str | None = os.getenv("SERVER_URL")
    SERVER_REDIRECT: str = os.getenv("SERVER_REDIRECT", "/api/auth/oidc/callback")
    SESSION_SECRET: str | None = os.getenv("SESSION_SECRET")

    @classmethod
    def validate(cls) -> None:
        """Validate required configuration at startup."""
        errors = []

        # Check model is valid format (provider/model-name)
        if not cls.MODEL or "/" not in cls.MODEL:
            errors.append(f"MODEL must be in format 'provider/model-name', got: {cls.MODEL}")

        # Met allow_credentials laat "*" elke site namens een ingelogde gebruiker de API aanroepen.
        if "*" in cls.get_parsed_cors_origins():
            errors.append("CORS_ORIGINS mag geen '*' bevatten; noem de origins expliciet")

        if errors:
            for error in errors:
                logger.error(error)
            raise ConfigError("; ".join(errors))

        logger.info(
            f"Configuration validated. Model: {cls.MODEL}, Database: {'PostgreSQL' if cls.POSTGRES_URI else 'SQLite'}"
        )

    @classmethod
    def get_parsed_cors_origins(cls) -> list[str]:
        """Parse CORS_ORIGINS into a list."""
        return [o.strip() for o in cls.CORS_ORIGINS.split(",") if o.strip()]

    @classmethod
    def is_production(cls) -> bool:
        """Check if running in production environment."""
        return bool(cls.POSTGRES_URI) and bool(cls.SESSION_SECRET)
