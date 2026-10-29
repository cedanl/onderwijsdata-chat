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

    # De providersleutels staan in core/config.py (_PROVIDER_API_KEYS); /ready leest ze daar (#675).

    # Optional OIDC/SRAM (see skill sram-oidc for the CEDA convention)
    OIDC_PROVIDER: str | None = os.getenv("OIDC_PROVIDER")
    OIDC_DISCOVERY_URL: str | None = os.getenv("OIDC_DISCOVERY_URL")
    OIDC_CLIENT_ID: str | None = os.getenv("OIDC_CLIENT_ID")
    OIDC_CLIENT_SECRET: str | None = os.getenv("OIDC_CLIENT_SECRET")
    SERVER_URL: str | None = os.getenv("SERVER_URL")
    SERVER_REDIRECT: str = os.getenv("SERVER_REDIRECT", "/api/auth/oidc/callback")

    # Waar de app draait (#676): manifests/<omgeving>/values.yaml zet de naam van de omgeving, lokaal staat hij leeg.
    # Buiten lokaal JSON-logs voor de logaggregatie van SDP; op playground en productie geen API-documentatie.
    APP_ENV: str = os.getenv("APP_ENV", "local").strip().lower()
    OMGEVINGEN = ("local", "development", "test", "playground", "production")

    # Een bewust openbare demo buiten lokaal, zonder login (#787). Zonder deze vlag start de app daar niet zonder login.
    ALLOW_ANONYMOUS: bool = os.getenv("ALLOW_ANONYMOUS", "").strip().lower() == "true"

    @classmethod
    def validate(cls) -> None:
        """Validate required configuration at startup."""
        errors = []

        # Check model is valid format (provider/model-name)
        if not cls.MODEL or "/" not in cls.MODEL:
            errors.append(f"MODEL must be in format 'provider/model-name', got: {cls.MODEL}")

        if cls.APP_ENV not in cls.OMGEVINGEN:
            # Een tikfout ("prod") zou anders stil als ontwikkelomgeving gelden, met API-documentatie.
            errors.append(f"APP_ENV moet een van {', '.join(cls.OMGEVINGEN)} zijn, kreeg: {cls.APP_ENV}")

        if fout := cls._login_ontbreekt():
            errors.append(fout)

        if ongeldig := cls._ongeldige_cors_origins():
            errors.append(
                f"CORS_ORIGINS mag geen '*' bevatten, ook niet als patroon ({', '.join(ongeldig)}); "
                "origins worden letterlijk vergeleken, noem ze expliciet"
            )

        if errors:
            for error in errors:
                logger.error(error)
            raise ConfigError("; ".join(errors))

        logger.info(
            f"Configuration validated. Model: {cls.MODEL}, Database: {'PostgreSQL' if cls.POSTGRES_URI else 'SQLite'}"
        )

    @classmethod
    def _login_ontbreekt(cls) -> str | None:
        """De foutmelding als een omgeving buiten lokaal zonder login zou starten (#787), anders None.

        Zonder CHAT_USERS en OIDC heet elke bezoeker `gast` en delen ze alle gesprekken en rapporten. Dat is lokaal
        bedoeld, maar een leeg geworden secret mag een uitgerolde omgeving er niet stil in brengen.
        """
        if cls.APP_ENV == "local":
            return None
        from core import auth  # pas hier: de import eist CHAT_SECRET zodra er een login is

        if auth.AUTH_ENABLED:
            return None
        if cls.ALLOW_ANONYMOUS:
            logger.warning(
                "ALLOW_ANONYMOUS=true: APP_ENV=%s draait zonder login; elke bezoeker is 'gast' en deelt alle "
                "gesprekken en rapporten",
                cls.APP_ENV,
            )
            return None
        return (
            f"APP_ENV={cls.APP_ENV} start niet zonder login: stel CHAT_USERS of OIDC_PROVIDER in "
            "(controleer ook of de waarde in het secret niet leeg is), of zet ALLOW_ANONYMOUS=true voor een "
            "bewust openbare demo"
        )

    @classmethod
    def get_parsed_cors_origins(cls) -> list[str]:
        """Parse CORS_ORIGINS into a list."""
        return [o.strip() for o in cls.CORS_ORIGINS.split(",") if o.strip()]

    @classmethod
    def _ongeldige_cors_origins(cls) -> list[str]:
        """Origins met een '*' (#506).

        Met allow_credentials laat "*" elke site namens een ingelogde gebruiker de API aanroepen.
        Een patroon als https://*.nl matcht nooit, want de CORSMiddleware vergelijkt letterlijk;
        zo'n instelling zou stil falen.
        """
        return [o for o in cls.get_parsed_cors_origins() if "*" in o]

    @classmethod
    def json_logs(cls) -> bool:
        """JSON-logs op elke SDP-omgeving, tekst alleen lokaal (#676)."""
        return cls.APP_ENV != "local"

    @classmethod
    def api_docs(cls) -> bool:
        """Swagger UI, ReDoc en het OpenAPI-schema alleen waar ontwikkeld wordt (#636, #676)."""
        return cls.APP_ENV in ("local", "development", "test")
