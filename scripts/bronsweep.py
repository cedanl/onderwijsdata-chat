"""Goedkope sweep over elke dataset die de chat kan opvragen, voor de bron-ping (#869).

De pings in scripts/bronping.py halen per bron één dataset op. Een verdwenen CBS-tabel, een DUO-bestand met een
hernoemde kolom of een RIO-register dat niet meer antwoordt viel daarbuiten. De sweep loopt dezelfde lijst langs als
de telling van de chat (`catalog.opvraagbare_ids`), met per dataset de goedkoopste aanroep die iets zegt:

- CBS: één `TableInfos` per tabel. Status, en `Modified` naast `_laatste_update` uit de catalogus: een latere datum
  betekent dat CBS de tabel bijwerkte na de catalogusbuild (de cijfers kunnen herzien zijn).
- DUO: per dataset de bestandenlijst van CKAN, en per CSV alleen de kopregel (`duo_laden.kolommen_uit_kop`), naast de
  schema-snapshot van riodata: een hernoemde, verdwenen of nieuwe kolom, een nieuw of verdwenen bestand (#868).
- RIO: per register één pagina van één record.

Elke aanroep loopt via `haal_op_met_retry` (#867), zoals in de chat. Een afwijking is informatie voor de beheerder,
geen fout van de code: ze staat in de joblog en het rapport, en de exitcode van de bron-ping blijft die van de pings.
De sweep loopt parallel en start na `TIJDSGRENS_S` geen nieuwe controle meer, zodat de job binnen vijf minuten blijft.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass

import httpx
from onderwijsbronnen import duo as riodata_duo
from onderwijsbronnen.cbs.client import get as cbs_get
from onderwijsbronnen.rio import fetch as rio_fetch

from tools import catalog, duo_laden
from tools.bronretry import haal_op_met_retry

BRONNEN = ("cbs", "duo", "rio")
TIJDSGRENS_S = 150.0
_WERKERS = 8
_MAX_DETAIL = 160


@dataclass(frozen=True)
class Bevinding:
    bron: str  # cbs | duo | rio
    id: str  # CBS-tabel, DUO-dataset[bestandsindex] of RIO-register
    ok: bool
    detail: str


@dataclass(frozen=True)
class Controle:
    bron: str
    id: str
    voer_uit: Callable[[], list[Bevinding]]


def _foutdetail(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        return f"HTTP {e.response.status_code}"
    tekst = " ".join(str(e).split())
    return f"{type(e).__name__}: {tekst[:_MAX_DETAIL]}" if tekst else type(e).__name__


# --- CBS -------------------------------------------------------------------------------------


def cbs_tabel(cbs_id: str) -> list[Bevinding]:
    """Eén TableInfos: antwoordt de tabel, en is `Modified` nog de datum uit de catalogus?"""
    rijen = haal_op_met_retry("CBS", lambda: cbs_get(cbs_id, "TableInfos"))
    gewijzigd = rijen[0].get("Modified") if rijen else None
    if not isinstance(gewijzigd, str):
        return [Bevinding("cbs", cbs_id, False, "TableInfos zonder Modified")]
    bron, catalogus = gewijzigd[:10], catalog.catalogus_laatste_update(cbs_id)
    if bron == catalogus:
        return [Bevinding("cbs", cbs_id, True, f"Modified {bron}, gelijk aan de catalogus")]
    return [Bevinding("cbs", cbs_id, False, f"Modified {bron}, catalogus {catalogus}: CBS werkte de tabel bij")]


# --- DUO -------------------------------------------------------------------------------------


def _duo_bestand(dataset_id: str, index: int, resource: dict, snapshot: dict[str, dict]) -> Bevinding:
    id = f"{dataset_id}[{index}]"
    if resource["id"] not in snapshot:
        return Bevinding("duo", id, False, f"nieuw bestand, niet in de schema-snapshot: {resource['naam'][:80]}")
    kolommen = haal_op_met_retry("DUO", lambda: duo_laden.kolommen_uit_kop(resource["url"], id))
    if drift := duo_laden.kolomdrift(dataset_id, resource["id"], kolommen):
        return Bevinding("duo", id, False, f"kolomdrift: {drift.verschil()}")
    return Bevinding("duo", id, True, f"{len(kolommen)} kolommen, gelijk aan de snapshot")


def duo_dataset(dataset_id: str) -> list[Bevinding]:
    """De bestandenlijst van CKAN, en per CSV de kopregel naast de snapshot; ook een verdwenen bestand telt."""
    bestanden = haal_op_met_retry("DUO", lambda: riodata_duo.resources(dataset_id))
    snapshot = {
        s["resource_id"]: s for s in riodata_duo.resource_schemas(dataset_id) if s["inspectie"]["status"] == "ok"
    }
    uit = [_duo_bestand(dataset_id, i, r, snapshot) for i, r in enumerate(bestanden) if "CSV" in r.get("format", "")]
    live = {r["id"] for r in bestanden}
    uit += [
        Bevinding(
            "duo", f"{dataset_id}[-]", False, f"bestand uit de snapshot staat niet meer bij DUO: {s['naam'][:80]}"
        )
        for id, s in snapshot.items()
        if id not in live
    ]
    return uit


# --- RIO -------------------------------------------------------------------------------------


def rio_register(resource: str) -> list[Bevinding]:
    """Eén pagina van één record: antwoordt het register, en heeft het iets?"""
    items = haal_op_met_retry("RIO", lambda: rio_fetch(resource, page=1, pageSize=1))
    if not items:
        return [Bevinding("rio", resource, False, "geen records")]
    return [Bevinding("rio", resource, True, "antwoordt")]


# --- de sweep --------------------------------------------------------------------------------

_CONTROLES: dict[str, tuple[str, Callable[[str], list[Bevinding]]]] = {
    "cbs": ("CBS", cbs_tabel),
    "duo": ("DUO", duo_dataset),
    "rio": ("RIO", rio_register),
}


def controles(bronnen: Iterable[str]) -> list[Controle]:
    """Eén controle per dataset die de chat kan opvragen, voor de gekozen bronnen."""
    uit = []
    for bron in bronnen:
        naam, controleer = _CONTROLES[bron]
        uit += [Controle(bron, id, lambda id=id, c=controleer: c(id)) for id in catalog.opvraagbare_ids(naam)]
    return uit


def voer_uit(
    lijst: list[Controle],
    tijdsgrens_s: float = TIJDSGRENS_S,
    klok: Callable[[], float] = time.monotonic,
    werkers: int = _WERKERS,
) -> list[Bevinding]:
    """Alle controles, parallel; een exception is een afwijking, en na de tijdsgrens start er geen meer."""
    start = klok()

    def een(controle: Controle) -> list[Bevinding]:
        if klok() - start > tijdsgrens_s:
            return [Bevinding(controle.bron, controle.id, False, f"niet gecontroleerd: sweep na {tijdsgrens_s:.0f} s")]
        try:
            return controle.voer_uit()
        except Exception as e:
            return [Bevinding(controle.bron, controle.id, False, _foutdetail(e))]

    with ThreadPoolExecutor(max_workers=werkers) as pool:
        return [b for bevindingen in pool.map(een, lijst) for b in bevindingen]


def regel(b: Bevinding) -> str:
    return f"  {'ok' if b.ok else '! '}  {b.bron:<4} {b.id:<46} {b.detail}"


def samenvatting(bevindingen: list[Bevinding]) -> str:
    per_bron = ", ".join(
        f"{b.upper()} {sum(1 for x in bevindingen if x.bron == b)}"
        for b in BRONNEN
        if any(x.bron == b for x in bevindingen)
    )
    afwijkingen = sum(1 for b in bevindingen if not b.ok)
    return f"Sweep: {len(bevindingen)} controles ({per_bron}); {afwijkingen} afwijking(en), als waarschuwing."


def rapport(bevindingen: list[Bevinding], duur_s: float) -> dict:
    """Het artefact van de job: elke bevinding, en de duur."""
    return {"duur_s": round(duur_s, 1), "bevindingen": [asdict(b) for b in bevindingen]}
