"""GET /metrics: de Prometheus-metrics van deze pod (#678, core/metrics.py).

Niet openbaar. Zonder `METRICS_TOKEN` bestaat het eindpunt niet: 404 met dezelfde tekst als een onbekende route. Met
token vraagt het `Authorization: Bearer <token>`, anders 401. De vergelijking is constant-time, op een SHA-256 van gelijke
lengte, zoals de sleutels van /mcp: de duur verraadt niet hoeveel tekens klopten, noch hoe lang het token is.

Niet in het OpenAPI-schema: het is een eindpunt voor de monitoring, geen API van de app.
"""

import hashlib
import hmac
import os
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Response
from prometheus_client import REGISTRY, generate_latest
from prometheus_client.exposition import CONTENT_TYPE_PLAIN_0_0_4

from core import config
from core.auth import bearer_token
from core.foutmeldingen import NIET_GEVONDEN

router = APIRouter()

PAD = "/metrics"
GEEN_TOKEN = "Token ontbreekt of klopt niet"


def _token() -> str | None:
    """Het token uit de omgeving, per verzoek gelezen, met core.config als terugval: zo ziet een test die de omgeving
    zet het eindpunt zonder modules te herladen. Leeg telt als niet gezet."""
    return os.environ.get("METRICS_TOKEN", config.METRICS_TOKEN or "") or None


def _klopt(aangeboden: str, token: str) -> bool:
    return hmac.compare_digest(hashlib.sha256(aangeboden.encode()).digest(), hashlib.sha256(token.encode()).digest())


@router.get(PAD, include_in_schema=False)
async def metrics(authorization: Annotated[str | None, Header()] = None) -> Response:
    token = _token()
    if token is None:
        raise HTTPException(status_code=404, detail=NIET_GEVONDEN)
    aangeboden = bearer_token(authorization)
    if not aangeboden or not _klopt(aangeboden, token):
        raise HTTPException(status_code=401, detail=GEEN_TOKEN, headers={"WWW-Authenticate": "Bearer"})
    return Response(
        generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_PLAIN_0_0_4,
        headers={"Cache-Control": "no-store"},
    )
