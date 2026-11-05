#!/usr/bin/env python
"""
Bron-ping: één aanroep per bron door de toollaag van de chat, zonder LLM (#627).

Gebruik:
    uv run python scripts/bronping.py                # elke bron één keer; exitcode 1 zodra één bron niet antwoordt
    uv run python scripts/bronping.py --alleen rio   # komma-gescheiden: cbs, duo, rio, inspectie, kaart, collegegeld
    uv run python scripts/bronping.py --sweep --rapport bronping-sweep.json
                                                     # plus de sweep over elke CBS-, DUO- en RIO-dataset (#869)

De CI-job `bron:ping` draait dit gepland op main (.gitlab-ci.yml). Een verwijderde API (RIO v2 gaf op
19-10-2026 HTTP 410 op elke aanroep), een gewijzigd filtercontract (HTTP 400) of een onbereikbare bron
komt zo bij de beheerder binnen in plaats van via een gebruiker: pytest mockt de bronnen en /health
toetst er geen. Dezelfde code als de chat (tools.cbs, tools.duo, tools.rio_instelling en de GeoJSON van
de kaart), met de selecties van de ijkwaarden (tests/ijkwaarden/harnas.py). Waarden vergelijkt dit niet:
dat doet scripts/ijkwaarden.py.

De tabel met het wettelijk collegegeld (tools/collegegeld.py, #729) haalt de chat niet bij een bron op: haar ping
vraagt het lopende studiejaar door de tool en wordt rood zodra dat er niet in staat. Zo komt rond 1 september de
jaarlijkse controle tegen de wettekst (docs/promoten.md, "Jaarlijks") vanzelf binnen.

Zo ook de vaste DUO-bestanden achter de mbo-eerstejaars (#924) en de ingeschrevenen per hoofdgroep (#934) van de
dashboards (data/dashboard.py): de ping duo-instroom-mbo wordt rood zodra DUO een jaar publiceert dat er niet in staat,
of de volgorde verschuift. Een vaste lijst houdt de pytest-job zonder netwerk; deze ping is de live controle erop.

Met --sweep volgt een goedkope controle van elke dataset die de chat kan opvragen (scripts/bronsweep.py, #869): een
afwijking daar is een waarschuwing in de log en het rapport, de exitcode blijft die van de pings.
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

from data import dashboard
from scripts import bronsweep
from tests.ijkwaarden import harnas
from tools import (
    cbs,
    collegegeld,
    duo,
    fouten,
    fusies,
    inspectie,
    inspectie_vo,
    mbo_indicatoren,
    plot,
    rio_instelling,
)

_MAX_DETAIL = 200
_PROVINCIES = 12
# Op 1 oktober 2026 noemden 164 besturen mbo; minder dan dit is een kapot of half bestand (#749).
_MIN_MBO_BESTUREN = 100
# Vo-afdelingen in het po-so-vo-bestand: op 01-11-2026 3634 (#881).
_MIN_VO_AFDELINGEN = 3000
# De editie 2026 heeft 54 mbo-instellingen; minder dan dit is een kapot of half bestand (#727).
_MIN_MBO_INSTELLINGEN = 40
_AERES = "30TX"  # de instellingscode achter de RIO-ijkwaarde rio-aeres-hogeschool
# Vonk, KW1C, Firda, Drenthe College Terra en Talland: vijf van de zes instellingen met een fusie binnen de
# DUO-reeksen 2021-2025 (onderzoek #728, 04-11-2026). Elk hoort de vaste fusieregel te krijgen.
FUSIES_IN_REEKS = ("25EF", "04FO", "08PG", "25PW", "25PT")
# De zesde, Landstede, nam een vmbo-school op (Morgen College, WVO); die hoort niet in de regel bij een mbo-reeks
# (#937). Noemt de regel haar toch, dan geeft RIO de wet niet meer zoals de chat hem leest.
VO_VOORGANGERS = {"01AA": "02EX"}
_DUO_REEKS = (2021, 2025)


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


def _fusies() -> dict:
    # Dezelfde weg als een DUO-reeks per instelling (dekking.van): RIO-voorgangers, dagcache, vaste regel (#728).
    return {code: list(fusies.in_reeks({code: code}, _DUO_REEKS)) for code in (*FUSIES_IN_REEKS, *VO_VOORGANGERS)}


def _fusies_bewijs(uitkomst: dict) -> str | None:
    zonder = [code for code in FUSIES_IN_REEKS if not uitkomst.get(code)]
    vo = [
        f"{code} noemt {vo}"
        for code, vo in VO_VOORGANGERS.items()
        if any(f"({vo})" in r for r in uitkomst.get(code) or [])
    ]
    fouten = ([f"geen fusieregel voor {', '.join(zonder)}"] if zonder else []) + (
        [f"vo-voorganger in de regel: {', '.join(vo)}"] if vo else []
    )
    return "; ".join(fouten) or None


def _kaart() -> dict:
    # Dezelfde lader als create_choropleth_map; privé omdat niets anders in de app hem nodig heeft.
    return plot._load_geojson("provincie")


def _inspectie() -> dict:
    # Dezelfde weg als de chat: overzicht, schooljaarpagina, document, bg-bestand (#749).
    bestand = inspectie.haal_peilbestand()
    return {"peildatum": bestand.peildatum, "mbo_besturen": len(inspectie.oordelen_mbo(bestand))}


def _inspectie_bewijs(uitkomst: dict) -> str | None:
    n = uitkomst.get("mbo_besturen", 0)
    return (
        None if n >= _MIN_MBO_BESTUREN else f"{n} mbo-besturen in het bg-bestand, minstens {_MIN_MBO_BESTUREN} verwacht"
    )


def _inspectie_vo() -> dict:
    # Dezelfde weg als get_inspectieoordeel_vo: het po-so-vo-bestand uit hetzelfde document, gefilterd op vo (#881).
    bestand = inspectie_vo.haal_peilbestand_vo()
    return {"peildatum": bestand.peildatum, "vo_afdelingen": len(inspectie_vo.afdelingen_vo(bestand.rijen))}


def _inspectie_vo_bewijs(uitkomst: dict) -> str | None:
    n = uitkomst.get("vo_afdelingen", 0)
    return (
        None
        if n >= _MIN_VO_AFDELINGEN
        else f"{n} vo-afdelingen in het po-so-vo-bestand, minstens {_MIN_VO_AFDELINGEN} verwacht"
    )


def _mbo_indicatoren() -> dict:
    # Dezelfde weg als de chat: indicatorenpagina, nieuwste xlsx-editie, de koppen en regels van de tool (#727).
    gelezen = mbo_indicatoren.haal_editie()
    return {"editie": gelezen.jaar, "instellingen": len(gelezen.instellingen)}


def _mbo_indicatoren_bewijs(uitkomst: dict) -> str | None:
    n = uitkomst.get("instellingen", 0)
    return None if n >= _MIN_MBO_INSTELLINGEN else f"{n} instellingen, minstens {_MIN_MBO_INSTELLINGEN} verwacht"


def _instroom_mbo() -> dict:
    # De vaste bestanden van de mbo-eerstejaars en -hoofdgroepen in de dashboards tegen wat DUO nu publiceert (#924, #934).
    return {"afwijkingen": dashboard.instromende_mbo_afwijkingen()}


def _instroom_mbo_bewijs(uitkomst: dict) -> str | None:
    return "; ".join(uitkomst["afwijkingen"]) or None


def _collegegeld_bewijs(uitkomst: dict) -> str | None:
    return None if "voltijd" in uitkomst else "geen bedrag voor het lopende studiejaar"


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
        "rio-fusies",
        "rio",
        "fusies binnen de DUO-reeks van vijf mbo-instellingen, zonder vo-voorganger bij Landstede (RIO-overgangen)",
        _fusies,
        _fusies_bewijs,
    ),
    Ping(
        "inspectie-bg",
        "inspectie",
        "nieuwste Inspectie-peilbestand per bestuur, mbo (bg.ods)",
        _inspectie,
        _inspectie_bewijs,
    ),
    Ping(
        "inspectie-po-so-vo",
        "inspectie",
        "nieuwste Inspectie-peilbestand per school, vo-afdelingen (po-so-vo.ods)",
        _inspectie_vo,
        _inspectie_vo_bewijs,
    ),
    Ping(
        "duo-indicatoren",
        "duo",
        "nieuwste editie indicatoren per mbo-instelling (xlsx)",
        _mbo_indicatoren,
        _mbo_indicatoren_bewijs,
    ),
    Ping(
        "duo-instroom-mbo",
        "duo",
        "de jaren van instromende-mbo-studenten in de dashboards tegen de bestanden bij DUO",
        _instroom_mbo,
        _instroom_mbo_bewijs,
    ),
    Ping(
        "collegegeld-tabel",
        "collegegeld",
        "wettelijk collegegeld van het lopende studiejaar in de tabel (get_collegegeld)",
        collegegeld.get_collegegeld,
        _collegegeld_bewijs,
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
    parser.add_argument(
        "--alleen",
        default="",
        help="komma-gescheiden bronnen: cbs, duo, rio, inspectie, kaart, collegegeld (standaard alle)",
    )
    parser.add_argument("--sweep", action="store_true", help="controleer ook elke CBS-, DUO- en RIO-dataset (#869)")
    parser.add_argument("--rapport", type=Path, help="schrijf de bevindingen van de sweep als JSON naar dit pad")
    return parser.parse_args(argv)


def _sweep(gekozen: set[str], rapport: Path | None) -> None:
    """De sweep over de gekozen bronnen, als tabel in de log en desgewenst als JSON; raakt de exitcode niet."""
    bronnen = [b for b in bronsweep.BRONNEN if not gekozen or b in gekozen]
    start = time.monotonic()
    bevindingen = bronsweep.voer_uit(bronsweep.controles(bronnen))
    duur = time.monotonic() - start
    print(f"\nSweep over elke dataset die de chat kan opvragen ({duur:.0f} s; een afwijking is een waarschuwing):")
    for b in bevindingen:
        print(bronsweep.regel(b))
    print(bronsweep.samenvatting(bevindingen))
    if rapport:
        rapport.write_text(json.dumps(bronsweep.rapport(bevindingen, duur), ensure_ascii=False, indent=2) + "\n")


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
    if args.sweep:
        _sweep(gekozen, args.rapport)
    fout = [u for u in uitslagen if not u.ok]
    if fout:
        print(f"\n{len(fout)} van {len(uitslagen)} bronnen antwoordt niet: {', '.join(u.ping.bron for u in fout)}.")
        return 1
    print(f"\nBron-ping: alle {len(uitslagen)} bronnen antwoorden.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
