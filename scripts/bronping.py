#!/usr/bin/env python
"""
Bron-ping: één aanroep per bron door de toollaag van de chat, zonder LLM (#627).

Gebruik:
    uv run python scripts/bronping.py                # elke bron één keer; exitcode 1 zodra één bron niet antwoordt
    uv run python scripts/bronping.py --alleen rio   # komma-gescheiden: cbs, duo, rio, kaart

De CI-job `bron:ping` draait dit gepland op main (.gitlab-ci.yml). Een verwijderde API (RIO v2 gaf op
19-10-2026 HTTP 410 op elke aanroep), een gewijzigd filtercontract (HTTP 400) of een onbereikbare bron
komt zo bij de beheerder binnen in plaats van via een gebruiker: pytest mockt de bronnen en /health
toetst er geen. Dezelfde code als de chat (tools.cbs, tools.duo, tools.rio_instelling en de GeoJSON van
de kaart), met de selecties van de ijkwaarden (tests/ijkwaarden/harnas.py). Waarden vergelijkt dit niet:
dat doet scripts/ijkwaarden.py.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.ijkwaarden import harnas
from tools import cbs, duo, fouten, plot, rio_instelling

_MAX_DETAIL = 200
_PROVINCIES = 12
_AERES = "30TX"  # de instellingscode achter de RIO-ijkwaarde rio-aeres-hogeschool


@dataclass(frozen=True)
class Ping:
    id: str
    bron: str  # cbs | duo | rio | kaart
    omschrijving: str
    haal: Callable[[], str | dict]  # de aanroep, zoals de chat hem doet
    bewijs: Callable[[dict], str | None]  # waarom de uitkomst geen echt antwoord is; None als ze dat wel is


@dataclass(frozen=True)
class Uitslag:
    ping: Ping
    ok: bool
    detail: str = ""
    duur: float = 0.0


def _ijkpunt(id: str) -> harnas.Ijkpunt:
    return next(p for p in harnas.IJKPUNTEN if p.id == id)


def _rijen(uitkomst: dict) -> str | None:
    return None if uitkomst.get("totaal_rijen") or uitkomst.get("opgehaalde_rijen") else "geen rijen in het antwoord"


def _cbs() -> str:
    s = _ijkpunt("cbs-hbo-voltijd-2024").selectie
    return cbs.get_cbs_data(s["dataset"], filters={**s["dimensies"], "Perioden": s["periode"]})


def _duo() -> str:
    s = _ijkpunt("duo-hu-voltijd-2024").selectie
    return duo.get_duo_data(s["dataset"], s["resource"])


def _rio() -> str:
    return rio_instelling.get_rio_instelling(_ijkpunt("rio-aeres-hogeschool").selectie["volledigeNaam"])


def _rio_bewijs(uitkomst: dict) -> str | None:
    codes = [i.get("code") for i in uitkomst.get("instellingen") or []]
    return None if _AERES in codes else f"instelling {_AERES} ontbreekt (gevonden: {codes})"


def _kaart() -> dict:
    # Dezelfde lader als create_choropleth_map; privé omdat niets anders in de app hem nodig heeft.
    return plot._load_geojson("provincie")


def _kaart_bewijs(uitkomst: dict) -> str | None:
    n = len(uitkomst.get("features") or [])
    return None if n >= _PROVINCIES else f"{n} vormen in de provincie-GeoJSON, minstens {_PROVINCIES} verwacht"


PINGS: tuple[Ping, ...] = (
    Ping("cbs-85423NED", "cbs", "hbo voltijd 2024/25 uit 85423NED (get_cbs_data)", _cbs, _rijen),
    Ping("duo-p01hoinges", "duo", "ingeschrevenen ho, bestand 3 (get_duo_data)", _duo, _rijen),
    Ping(
        "rio-aeres-hogeschool",
        "rio",
        "Aeres Hogeschool, bestuur en vestigingen (get_rio_instelling)",
        _rio,
        _rio_bewijs,
    ),
    Ping(
        "kaart-provincies",
        "kaart",
        "GeoJSON van de provincies, cartomap (create_choropleth_map)",
        _kaart,
        _kaart_bewijs,
    ),
)


def _kort(tekst: str) -> str:
    tekst = " ".join(tekst.split())
    return tekst if len(tekst) <= _MAX_DETAIL else tekst[: _MAX_DETAIL - 1] + "…"


def beoordeel(ping: Ping, uitkomst: str | dict) -> Uitslag:
    """Een echt antwoord of niet: de gecodeerde fout van de tool, platte tekst, of JSON zonder het bewijs."""
    if isinstance(uitkomst, str):
        if fouten.code(uitkomst) is not None:
            return Uitslag(ping, False, _kort(uitkomst))
        try:
            uitkomst = json.loads(uitkomst)
        except ValueError:
            return Uitslag(ping, False, _kort(uitkomst))
    if not isinstance(uitkomst, dict):
        return Uitslag(ping, False, f"onverwachte uitkomst ({type(uitkomst).__name__})")
    reden = ping.bewijs(uitkomst)
    return Uitslag(ping, reden is None, reden or "")


def ping(p: Ping) -> Uitslag:
    """Eén aanroep, met de tijd; elke exception uit de bron of het package is een rode ping."""
    start = time.monotonic()
    try:
        uitkomst = p.haal()
    except Exception as e:
        return Uitslag(p, False, f"{type(e).__name__}: {_kort(str(e))}", time.monotonic() - start)
    uitslag = beoordeel(p, uitkomst)
    return Uitslag(p, uitslag.ok, uitslag.detail, time.monotonic() - start)


def _regel(u: Uitslag) -> str:
    detail = f" — {u.detail}" if u.detail else ""
    return f"  {'ok' if u.ok else '! '}  {u.ping.bron:<5} {u.ping.id:<22} {u.duur:5.1f}s  {u.ping.omschrijving}{detail}"


def _argumenten(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Eén aanroep per bron door de toollaag van de chat (#627).")
    parser.add_argument("--alleen", default="", help="komma-gescheiden bronnen: cbs, duo, rio, kaart (standaard alle)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _argumenten(argv)
    gekozen = {b.strip() for b in args.alleen.split(",") if b.strip()}
    if onbekend := gekozen - {p.bron for p in PINGS}:
        print(f"Onbekende bron(nen): {', '.join(sorted(onbekend))}", file=sys.stderr)
        return 2
    uitslagen = [ping(p) for p in PINGS if not gekozen or p.bron in gekozen]
    print("Bron-ping, één aanroep per bron door de toollaag van de chat:")
    for u in uitslagen:
        print(_regel(u))
    fout = [u for u in uitslagen if not u.ok]
    if fout:
        print(f"\n{len(fout)} van {len(uitslagen)} bronnen antwoordt niet: {', '.join(u.ping.bron for u in fout)}.")
        return 1
    print(f"\nBron-ping: alle {len(uitslagen)} bronnen antwoorden.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
