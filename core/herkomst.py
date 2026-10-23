"""Welke browser een chatverbinding mag openen (#682).

CORS geldt niet voor een WebSocket: de browser stuurt Origin mee, maar alleen de server kan hem weigeren. Het
token in het subprotocol is het eerste slot; zonder login (lokaal, demo) is dit het enige. Een client zonder
Origin is geen browser en kan zich dus ook niet voordoen als een gebruiker die toevallig een andere site open heeft.
"""

from urllib.parse import urlsplit

# Vite (npm run dev) proxiet met changeOrigin: Host wordt de backend, Origin blijft de devserver.
_LOKALE_HOSTS = ("localhost", "127.0.0.1", "::1")


def origin_toegestaan(origin: str | None, host: str | None, toegestaan: list[str], *, lokaal: bool) -> bool:
    """De eigen origin (die van Host), een origin uit CORS_ORIGINS, of lokaal een devserver op deze machine.

    "null" (een frame met een opake origin, zoals het rapportframe) valt overal buiten.
    """
    if origin is None:
        return True
    if origin in toegestaan:
        return True
    delen = urlsplit(origin)
    if host and delen.scheme in ("http", "https") and delen.netloc == host:
        return True
    return lokaal and delen.hostname in _LOKALE_HOSTS
