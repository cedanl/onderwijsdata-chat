"""Hoe actueel elke bron is, op één plek (#1266): de pagina /bronnen, `GET /api/bronactualiteit` en de MCP-resource.

Per bron (CBS, DUO, RIO, UWV, ROA, SKDB) en per dataset de laatste periode of editie, de laatste wijziging, de status
(voorlopig of definitief), de frequentie en een verwachte volgende editie. Alles komt uit de metadata die de app al
heeft: de catalogus van `onderwijsbronnen` (het broncontract, #911, en bij CBS de vastgelegde TableInfos). Er gaat
geen verzoek naar een bron: een trage of falende bron houdt de pagina dus nooit op. Of een bron nu antwoordt, komt uit
de bewaking die al draait (`core.bronstatus`).

Een verwachte volgende editie staat er alleen als de bron haar zelf noemt, letterlijk en met de bron erbij: bij CBS de
zin onder "Wanneer komen er nieuwe cijfers?" in de TableInfos van die tabel. Nooit een datum die uit de frequentie is
geraden; zonder bronzin is het veld "onbekend" en zegt de samenvatting alleen de frequentie en de laatste update.
Een datum staat er zoals de bron hem schrijft, niet omgerekend (tests/test_bronactualiteit_overzicht.py).

Elk veld dat ontbreekt is de tekst "onbekend", nooit null of leeg. Lukt het lezen van één bron niet, dan staat die bron
er met "onbekend" en een melding; de andere bronnen blijven staan.
"""

from __future__ import annotations

import functools
import logging
import re
from collections.abc import Iterable
from datetime import date, datetime

from core import actualiteit, bronstatus
from core.logging_util import foutkenmerk

logger = logging.getLogger(__name__)

ONBEKEND = "onbekend"
VOORLOPIG = "voorlopig"
DEFINITIEF = "definitief"
DEELS_VOORLOPIG = "deels voorlopig"
PER_DATASET = "verschilt per dataset"
BEREIKBAAR = "bereikbaar"
NIET_BEREIKBAAR = "niet bereikbaar"
# Een verwachte editie die een antwoord noemt: alleen binnen zoveel dagen (#1266).
VERWACHT_BINNEN_DAGEN = 30

# De bronnen op de pagina, in deze volgorde: (sleutel, naam, titel, link naar de bron).
BRONNEN = (
    ("cbs", "CBS", "Centraal Bureau voor de Statistiek (StatLine)", "https://opendata.cbs.nl"),
    ("duo", "DUO", "Dienst Uitvoering Onderwijs (open onderwijsdata)", "https://onderwijsdata.duo.nl"),
    ("rio", "RIO", "Register Instellingen en Opleidingen", "https://lod.onderwijsregistratie.nl"),
    ("uwv", "UWV", "UWV Open Match (vacatures)", "https://data.overheid.nl/dataset/uwv-open-match-data"),
    ("roa", "ROA", "ROA Arbeidsmarktinformatiesysteem", "https://doi.org/10.34894/DVQTOG"),
    (
        "skdb",
        "SKDB",
        "Studiekeuzedatabase (Landelijk Centrum Studiekeuze)",
        "https://lcsk.nl/over-ons/studiekeuzedata-raadplegen/",
    ),
)

# Zo schrijft de catalogus dezelfde frequentie soms anders; de rest blijft zoals de bron hem noemt.
_FREQUENTIE = {"perjaar": "Jaarlijks", "perkwartaal": "Per kwartaal", "kwartaal": "Per kwartaal"}
_CBS_STATUS = {"voorlopig": VOORLOPIG, "nadervoorlopig": VOORLOPIG, "definitief": DEFINITIEF}
_ISO_DAG = re.compile(r"^\d{4}-\d{2}-\d{2}")
_MAANDEN = (
    "januari",
    "februari",
    "maart",
    "april",
    "mei",
    "juni",
    "juli",
    "augustus",
    "september",
    "oktober",
    "november",
    "december",
)
# Een dag in een bronzin: "13 december 2026", "13-12-2026" of "2026-12-13". Een kwartaal of maand is geen dag.
_DAG_IN_TEKST = re.compile(
    rf"\b(?P<lang>(?P<d>\d{{1,2}}) (?P<m>{'|'.join(_MAANDEN)}) (?P<j>\d{{4}}))\b"
    r"|\b(?P<nl>(?P<d2>\d{1,2})-(?P<m2>\d{1,2})-(?P<j2>\d{4}))\b"
    r"|\b(?P<iso>(?P<j3>\d{4})-(?P<m3>\d{2})-(?P<d3>\d{2}))\b",
    re.IGNORECASE,
)


def _tekst(waarde: object) -> str:
    """Een veld als tekst; None, leeg of alleen spaties is "onbekend"."""
    if waarde is None:
        return ONBEKEND
    tekst = " ".join(str(waarde).split())
    return tekst if tekst and tekst.lower() != ONBEKEND else ONBEKEND


def _dag(waarde: object) -> str:
    """De dag (jjjj-mm-dd) vooraan een ISO-moment uit de bron, letterlijk; anders "onbekend"."""
    tekst = str(waarde or "")
    return tekst[:10] if _ISO_DAG.match(tekst) else ONBEKEND


def _frequentie(waarde: object) -> str:
    """De frequentie zoals de bron haar noemt, met een hoofdletter; "Perjaar" en "Kwartaal" als "Jaarlijks" en "Per
    kwartaal", zodat dezelfde frequentie er één keer staat."""
    tekst = _tekst(waarde)
    if tekst == ONBEKEND:
        return ONBEKEND
    tekst = _FREQUENTIE.get(tekst.lower().replace(" ", ""), tekst)
    return tekst[0].upper() + tekst[1:]


def _status(voorlopig: bool | None) -> str:
    return ONBEKEND if voorlopig is None else (VOORLOPIG if voorlopig else DEFINITIEF)


def samenvatting(dataset: dict) -> str:
    """Eén zin over de actualiteit: de verwachte editie met haar bron, of anders de frequentie en de laatste update."""
    if dataset["verwachte_volgende_editie"] != ONBEKEND:
        return f"Volgende editie volgens {dataset['verwachte_volgende_editie_bron']}: {dataset['verwachte_volgende_editie']}"
    return f"frequentie: {dataset['frequentie']}, laatste update {dataset['laatste_wijziging']}"


def _dataset(
    id: object,
    titel: object,
    url: object = None,
    *,
    laatste_periode: object = None,
    laatste_wijziging: object = None,
    status: str = ONBEKEND,
    frequentie: object = None,
    verwacht: object = None,
    verwacht_bron: object = None,
    verwacht_url: object = None,
    gecontroleerd_op: object = None,
) -> dict:
    """Een dataset met elk veld als tekst. Een verwachte editie zonder bron telt niet: dan is ze "onbekend"."""
    verwacht_tekst = _tekst(verwacht)
    if _tekst(verwacht_bron) == ONBEKEND:
        verwacht_tekst = ONBEKEND
    dataset = {
        "id": _tekst(id),
        "titel": _tekst(titel),
        "url": _tekst(url),
        "laatste_periode": _tekst(laatste_periode),
        "laatste_wijziging": _dag(laatste_wijziging),
        "status": status,
        "frequentie": _frequentie(frequentie),
        "verwachte_volgende_editie": verwacht_tekst,
        "verwachte_volgende_editie_bron": _tekst(verwacht_bron) if verwacht_tekst != ONBEKEND else ONBEKEND,
        "verwachte_volgende_editie_url": _tekst(verwacht_url) if verwacht_tekst != ONBEKEND else ONBEKEND,
        "gecontroleerd_op": _dag(gecontroleerd_op),
    }
    return dataset | {"samenvatting": samenvatting(dataset)}


def _link(dataset_id: str) -> str | None:
    from tools.catalog import documentatie_url  # hier: tools laadt de hele catalogus, de module zelf niet

    return documentatie_url(dataset_id)


def _opvraagbaar(bron: str) -> set[str]:
    """De datasets van een chatbron die de chat kan opvragen, zoals /api/catalog/counts ze telt."""
    from tools.catalog import opvraagbare_ids

    return set(opvraagbare_ids(bron))


# ── per bron ─────────────────────────────────────────────────────────────────


def cbs_verwacht(record: dict) -> str | None:
    """De zin van CBS over de volgende cijfers ("Wanneer komen er nieuwe cijfers?") uit de TableInfos van de tabel."""
    publicatie = (record.get("methodiek") or {}).get("publicatie") or {}
    zin = publicatie.get("volgende_publicatie") if isinstance(publicatie, dict) else None
    return zin if isinstance(zin, str) and zin.strip() else None


def cbs_bron(cbs_id: str) -> str:
    return f"CBS, tabelinformatie {cbs_id} (Wanneer komen er nieuwe cijfers?)"


def _cbs_dataset(record: dict) -> dict:
    cbs_id = record["dataset_id"].split(":", 1)[-1]
    perioden = record.get("perioden") or {}
    codes = (perioden.get("codes") or {}).get("codes") or []
    laatste = codes[-1] if codes else {}
    status = _CBS_STATUS.get(str(laatste.get("status") or "").lower().replace(" ", ""), ONBEKEND)
    herkomst = record.get("herkomst") or {}
    link = _link(cbs_id)
    return _dataset(
        cbs_id,
        record.get("titel"),
        link,
        laatste_periode=laatste.get("titel") or perioden.get("laatste") or perioden.get("tekst"),
        laatste_wijziging=herkomst.get("laatste_update"),
        status=status,
        frequentie=perioden.get("frequentie"),
        verwacht=cbs_verwacht(record),
        verwacht_bron=cbs_bron(cbs_id),
        verwacht_url=link,
        gecontroleerd_op=herkomst.get("gecontroleerd_op"),
    )


def _cbs() -> list[dict]:
    """De CBS-tabellen die de chat kan laden, zonder de gearchiveerde: die krijgen geen nieuwe cijfers meer."""
    from onderwijsbronnen.cbs import catalog_records

    opvraagbaar = _opvraagbaar("CBS")
    return [
        _cbs_dataset(r)
        for r in catalog_records()
        if r["dataset_id"].split(":", 1)[-1] in opvraagbaar and not (r.get("archief") or {}).get("gearchiveerd")
    ]


def _duo() -> list[dict]:
    from onderwijsbronnen import duo

    opvraagbaar = _opvraagbaar("DUO")
    datasets = []
    for record in duo.catalogusrecords():
        meta = duo.metadata(record) if record.get("_ckan_id") else None
        if meta is None or meta["id"] not in opvraagbaar:
            continue
        tijd = record.get("_tijd") or {}
        datasets.append(
            _dataset(
                meta["id"],
                meta["titel"],
                _link(meta["id"]),
                laatste_periode=meta["peildatum_of_editie"] or record.get("periode"),
                laatste_wijziging=meta["laatste_update"] or (tijd.get("bron") or {}).get("metadata_modified"),
                status=_status(meta["voorlopig"]),
                frequentie=(tijd.get("verversing") or {}).get("waarde") or record.get("frequentie"),
                gecontroleerd_op=(tijd.get("bron") or {}).get("opgehaald_op"),
            )
        )
    return datasets


def _rio() -> list[dict]:
    from onderwijsbronnen import rio

    opvraagbaar = _opvraagbaar("RIO")
    datasets = []
    for record in rio.catalogusrecords():
        meta = rio.metadata(record)
        if meta["id"] not in opvraagbaar:
            continue
        datasets.append(
            _dataset(
                meta["id"],
                meta["titel"],
                (record.get("documentatie") or {}).get("url"),
                laatste_periode=meta["peildatum_of_editie"] or record.get("periode"),
                laatste_wijziging=meta["laatste_update"],
                status=_status(meta["voorlopig"]),
                frequentie=record.get("frequentie"),
            )
        )
    return datasets


def _uwv() -> list[dict]:
    from onderwijsbronnen import uwv

    datasets = []
    for record in uwv.catalogusrecords():
        meta = uwv.metadata(record)
        datasets.append(
            _dataset(
                meta["id"],
                meta["titel"],
                (record.get("documentatie") or {}).get("url"),
                laatste_periode=meta["peildatum_of_editie"],
                laatste_wijziging=meta["laatste_update"],
                status=_status(meta["voorlopig"]),
                frequentie=record.get("frequentie"),
            )
        )
    return datasets


def _roa() -> list[dict]:
    from onderwijsbronnen import roa

    datasets = []
    for record in roa.catalogusrecords():
        meta = roa.metadata(record)
        editie = meta["peildatum_of_editie"]
        schemas = [r.get("schema") or {} for r in record.get("_resources") or []]
        # De DataverseNL-release van de bestanden van die editie: de dag waarop ROA ze publiceerde.
        releases = sorted(
            s["dataverse_release"] for s in schemas if s.get("editie") == editie and s.get("dataverse_release")
        )
        controles = sorted(
            s["gecontroleerd_op"] for s in schemas if s.get("editie") == editie and s.get("gecontroleerd_op")
        )
        datasets.append(
            _dataset(
                meta["id"],
                meta["titel"],
                (record.get("documentatie") or {}).get("url"),
                laatste_periode=f"editie {editie}" if editie else None,
                laatste_wijziging=meta["laatste_update"] or (releases[-1] if releases else None),
                status=_status(meta["voorlopig"]),
                frequentie=record.get("frequentie"),
                gecontroleerd_op=controles[-1] if controles else None,
            )
        )
    return datasets


def _skdb() -> list[dict]:
    from onderwijsbronnen import skdb

    datasets = []
    for record in skdb.catalogusrecords():
        meta = skdb.metadata(record)
        datasets.append(
            _dataset(
                meta["id"],
                meta["titel"],
                (record.get("documentatie") or {}).get("url"),
                laatste_periode=meta["peildatum_of_editie"],
                laatste_wijziging=meta["laatste_update"],
                status=_status(meta["voorlopig"]),
                frequentie=record.get("frequentie"),
            )
        )
    return datasets


# Per bron de datasets uit de catalogus. Pakketdata, dus één keer gelezen per proces; een fout wordt niet bewaard.
LEZERS = {
    "cbs": functools.cache(_cbs),
    "duo": functools.cache(_duo),
    "rio": functools.cache(_rio),
    "uwv": functools.cache(_uwv),
    "roa": functools.cache(_roa),
    "skdb": functools.cache(_skdb),
}


def vergeet() -> None:
    """Leeg de bewaarde datasets, voor een test die de catalogus vervangt."""
    for lezer in LEZERS.values():
        lezer.cache_clear()


# ── per bron samengevat ──────────────────────────────────────────────────────


def _samen(waarden: Iterable[str]) -> str:
    """Eén waarde voor de bron: dezelfde bij elke dataset, anders "verschilt per dataset"; "onbekend" zonder waarden."""
    bekend = list(dict.fromkeys(w for w in waarden if w != ONBEKEND))
    if not bekend:
        return ONBEKEND
    return bekend[0] if len(bekend) == 1 else PER_DATASET


def _bronstatus(statussen: list[str]) -> str:
    if not statussen or (ONBEKEND in statussen and VOORLOPIG not in statussen):
        return ONBEKEND
    if VOORLOPIG in statussen:
        return VOORLOPIG if all(s == VOORLOPIG for s in statussen) else DEELS_VOORLOPIG
    return DEFINITIEF


def _bereikbaarheid(sleutel: str, niet_live: set[str]) -> str:
    """Wat de bewaking (`core.bronstatus`) over de bron weet: niet bereikbaar, bereikbaar, of onbekend als ze de bron
    niet bewaakt of nog geen ronde deed."""
    if sleutel in niet_live:
        return NIET_BEREIKBAAR
    return BEREIKBAAR if bronstatus.live(sleutel) else ONBEKEND


def _ouderdom(peildatum: str) -> dict:
    """De leeftijd van de UWV-stand, met dezelfde regel en tekst als de dashboards en de chat (#1219)."""
    from data.arbeidsmarkt import ouderdom, ouderdom_tekst

    stand = ouderdom(None if peildatum == ONBEKEND else peildatum)
    maanden = stand["peildatum_ouderdom_maanden"]
    if maanden is None:
        return {"tekst": ONBEKEND, "verouderd": False}
    return {"tekst": ouderdom_tekst(maanden), "maanden": maanden, "verouderd": stand["verouderd"]}


def _bron(sleutel: str, naam: str, titel: str, url: str, niet_live: set[str]) -> dict:
    bron: dict = {
        "bron": sleutel,
        "naam": naam,
        "titel": titel,
        "url": url,
        "bereikbaar": _bereikbaarheid(sleutel, niet_live),
    }
    try:
        datasets = [dict(d) for d in LEZERS[sleutel]()]  # een kopie: de UWV-ouderdom hangt aan de klok
    except Exception as e:  # één bron die niet leest, mag de pagina niet ophouden
        logger.warning("BRONACTUALITEIT %s niet gelezen: %s", sleutel, foutkenmerk(e))
        logger.debug("BRONACTUALITEIT %s niet gelezen", sleutel, exc_info=True)
        datasets = []
        bron["melding"] = f"De actualiteit van {naam} kon niet worden gelezen."
    verwacht = [d for d in datasets if d["verwachte_volgende_editie"] != ONBEKEND]
    eentje = datasets[0] if len(datasets) == 1 else None
    bron |= {
        "laatste_periode": eentje["laatste_periode"] if eentje else _samen(d["laatste_periode"] for d in datasets),
        "laatste_wijziging": max(
            (d["laatste_wijziging"] for d in datasets if d["laatste_wijziging"] != ONBEKEND), default=ONBEKEND
        ),
        "status": _bronstatus([d["status"] for d in datasets]),
        "frequentie": _samen(d["frequentie"] for d in datasets),
        "verwachte_volgende_editie": eentje["verwachte_volgende_editie"]
        if eentje
        else (PER_DATASET if verwacht else ONBEKEND),
        "verwachte_volgende_editie_bron": (
            eentje["verwachte_volgende_editie_bron"] if eentje else (PER_DATASET if verwacht else ONBEKEND)
        ),
        "datasets": datasets,
    }
    if bron["bereikbaar"] == NIET_BEREIKBAAR:
        bron["melding"] = (
            f"{naam} is op dit moment niet bereikbaar. Wat hier staat is de laatst bekende stand uit de catalogus."
        )
    if sleutel == "uwv":
        for dataset in datasets:
            dataset["ouderdom"] = _ouderdom(dataset["laatste_periode"])
        bron["ouderdom"] = _ouderdom(bron["laatste_periode"])
    return bron


def overzicht() -> dict:
    """Per bron de actualiteit en haar datasets, voor /api/bronactualiteit en de MCP-resource."""
    niet_live = {b["bron"] for b in bronstatus.niet_live()}
    return {
        "bronnen": [_bron(sleutel, naam, titel, url, niet_live) for sleutel, naam, titel, url in BRONNEN],
        "uitleg": (
            "Uit de catalogus van de app, niet live opgevraagd. Een verwachte editie staat er alleen als de bron haar "
            "zelf noemt; anders 'onbekend'. Elke datum staat er zoals de bron hem geeft."
        ),
    }


# ── voor de regel onder een antwoord ─────────────────────────────────────────


def _dag_uit_match(m: re.Match[str]) -> date | None:
    try:
        if m["lang"]:
            return date(int(m["j"]), _MAANDEN.index(m["m"].lower()) + 1, int(m["d"]))
        if m["nl"]:
            return date(int(m["j2"]), int(m["m2"]), int(m["d2"]))
        return date(int(m["j3"]), int(m["m3"]), int(m["d3"]))
    except ValueError:
        return None


def dag_in_bronzin(zin: str) -> tuple[str, date] | None:
    """De eerste dag in een bronzin, zoals de bron hem schrijft en als datum; None zonder dag ("eerste kwartaal")."""
    for m in _DAG_IN_TEKST.finditer(zin):
        if (dag := _dag_uit_match(m)) is not None:
            return m[0], dag
    return None


def verwacht_binnenkort(cbs_id: str, nu: datetime | None = None) -> str | None:
    """ "Nieuwe editie verwacht op <dag> (bron: …)" voor een CBS-tabel waarvan CBS zelf een dag noemt binnen
    `VERWACHT_BINNEN_DAGEN`; None zonder bronzin, zonder dag erin, of met een dag die voorbij of verder weg is."""
    from onderwijsbronnen.cbs import contract

    try:
        record = contract.get_dataset(cbs_id)
    except contract.DatasetNietGevonden:
        return None
    if (zin := cbs_verwacht(record)) is None or (gevonden := dag_in_bronzin(zin)) is None:
        return None
    tekst, dag = gevonden
    vandaag = (nu or actualiteit.nu()).date()
    if not 0 <= (dag - vandaag).days <= VERWACHT_BINNEN_DAGEN:
        return None
    return f"Nieuwe editie verwacht op {tekst} (bron: {cbs_bron(cbs_id)})"
