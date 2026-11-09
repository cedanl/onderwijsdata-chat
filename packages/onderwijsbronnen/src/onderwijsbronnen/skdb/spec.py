"""De openbare OpenAPI-spec van de Studiekeuzedatabase tegen wat dit pakket leest (#878).

De spec (`/openapi.json`) vraagt geen sleutel, de export wel. De bron-ping van de chat (`scripts/bronping.py`) haalt
haar daarom dagelijks op en meldt zo een wijziging van de API zonder dat de sleutel in CI hoeft (afspraak #878, 04-11:
de sleutel staat alleen als secret in de clusters). `ontbreekt` toetst dat `/export/json` nog een ZIP levert en dat de
tabellen die de zes overzichten lezen nog in de API staan: als eigen pad, of als lijst in het antwoord van een ander
pad, die de export tot een eigen tabel plat maakt.

Alleen paden en veldnamen; de spec zelf staat niet in de repo (een open vraag aan LCSK, #878 §5).
"""

from __future__ import annotations

import httpx

from .export import API, EXPORT, USER_AGENT, SkdbFout
from .schemakaart import MOGELIJKHEDEN, OVERZICHT

OPENAPI = f"{API}/openapi.json"
_EXPORT_PAD = EXPORT.removeprefix(API)
_ZIP = "application/zip"

# De tabellen zonder eigen pad: in de API een lijst in het antwoord van een ander pad (spec van 09-11-2026).
GENEST: dict[str, tuple[str, str]] = {
    "opleidingvormen": ("/opleidingen", "vormen"),
    "studievormen": ("/studies", "vormen"),
    "standaardonderwijsindelingvorm": ("/standaardonderwijsindeling", "vormen"),
    "doorstroombachelormaster": ("/studies", "doorstroomBachelorMaster"),
}


def tabellen() -> list[str]:
    """De tabellen die de zes overzichten lezen (`schemakaart.MOGELIJKHEDEN`)."""
    return sorted(t for t, m in MOGELIJKHEDEN.items() if m.soort == OVERZICHT)


def haal_spec(*, timeout: float = 30.0) -> dict:
    """De OpenAPI-spec van de API, zonder sleutel."""
    try:
        response = httpx.get(OPENAPI, headers={"User-Agent": USER_AGENT}, timeout=timeout, follow_redirects=True)
    except httpx.HTTPError as e:
        raise SkdbFout(f"De OpenAPI-spec van de Studiekeuzedatabase is niet bereikbaar ({type(e).__name__}).") from None
    if response.status_code != 200:
        raise SkdbFout(f"De Studiekeuzedatabase gaf HTTP {response.status_code} op de OpenAPI-spec.")
    try:
        spec = response.json()
    except ValueError:
        spec = None
    if not isinstance(spec, dict):
        raise SkdbFout("De OpenAPI-spec van de Studiekeuzedatabase is geen JSON-object.")
    return spec


def _volg(spec: dict, schema: dict) -> dict:
    """Een lokale `$ref` (`#/components/...`) opgezocht; anders het schema zelf."""
    ref = schema.get("$ref") if isinstance(schema, dict) else None
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return schema if isinstance(schema, dict) else {}
    doel: object = spec
    for deel in ref[2:].split("/"):
        doel = doel.get(deel, {}) if isinstance(doel, dict) else {}
    return doel if isinstance(doel, dict) else {}


def _inhoud(spec: dict, pad: str) -> dict:
    """De content-types van het 200-antwoord op GET `pad`."""
    get = (spec.get("paths") or {}).get(pad, {}).get("get") or {}
    return _volg(spec, (get.get("responses") or {}).get("200") or {}).get("content") or {}


def _velden(spec: dict, pad: str) -> set[str]:
    """De veldnamen van één item in het JSON-antwoord op GET `pad` (een lijst of één object)."""
    schema = _volg(spec, (_inhoud(spec, pad).get("application/json") or {}).get("schema") or {})
    if schema.get("type") == "array":
        schema = _volg(spec, schema.get("items") or {})
    return set(schema.get("properties") or {})


def _tabel(spec: dict, tabel: str) -> str | None:
    paden = spec.get("paths") or {}
    if tabel in GENEST:
        pad, veld = GENEST[tabel]
        if pad not in paden:
            return f"tabel {tabel}: geen pad {pad} in de spec"
        return None if veld in _velden(spec, pad) else f"tabel {tabel}: geen veld {veld} in het antwoord van {pad}"
    if any(p.rstrip("/").endswith(f"/{tabel}") and "get" in (o or {}) for p, o in paden.items()):
        return None
    return f"tabel {tabel}: geen pad dat eindigt op /{tabel}"


def _export(spec: dict) -> str | None:
    if _EXPORT_PAD not in (spec.get("paths") or {}):
        return f"geen pad {_EXPORT_PAD} in de spec"
    types = sorted(_inhoud(spec, _EXPORT_PAD))
    return None if _ZIP in types else f"{_EXPORT_PAD} levert geen {_ZIP} meer (wel: {', '.join(types) or 'niets'})"


def ontbreekt(spec: dict) -> list[str]:
    """Wat het pakket leest en de spec niet meer noemt, één melding per pad of tabel; leeg als alles er is."""
    return [m for m in (_export(spec), *(_tabel(spec, t) for t in tabellen())) if m]
