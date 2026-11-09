"""Studiekeuzedatabase (SKDB) van het Landelijk Centrum Studiekeuze: opleidingen in het hbo en wo (#957).

De data achter Studiekeuze123: per opleiding (CROHO-code × BRIN × vestiging) de oordelen uit de Nationale Studenten
Enquête, doorstroom en rendement, numerus fixus en de vooropleidingseisen; per landelijke studie de
arbeidsmarktpositie per SOI-rubriek; de doorstroom mbo-4 → hbo en bachelor → master. Alleen hbo en wo. Wat een andere
bron leidend heeft (aantallen studenten: DUO; collegegeld; accreditatie), geven de overzichten niet (#878).

Gebruik (met `STUDIEKEUZEDATABASE_API_KEY` in de omgeving, of de sleutel als argument):
    from onderwijsbronnen import skdb

    df = skdb.load("opleidingvormen")                 # één tabel van de nieuwste export

    export = skdb.lees(*skdb.haal_op())               # alle tabellen van één export, met de herkomst
    export.herkomst.versie                            # "26.6"
    export.frame("studies")
    skdb.schema(export)                               # het schema uit de export zelf: tabellen, kolommen, korrel (#978)
    skdb.opleidingen(export, brin="25DW", croho=30020)   # kerncijfers per opleiding en vorm, met NSE landelijk

Licentie: de Algemene Leveringsvoorwaarden Data van LCSK (v25.1). Bij elke uiting `VERPLICHTE_ZIN` met een link naar
`DOCUMENTATIE` en het versienummer; geen doorlevering. Dit pakket bevat daarom geen data van LCSK: de lader haalt de
export op het moment van gebruik, met de eigen sleutel van de gebruiker.
"""

from __future__ import annotations

import json
from importlib.resources import files

from .._kern import broncontract, sleutels
from .export import (
    API,
    DOCUMENTATIE,
    EXPORT,
    LEVERANCIER,
    SLEUTEL_ENV,
    USER_AGENT,
    VEREIST,
    VERPLICHTE_ZIN,
    Export,
    GeenSleutel,
    Herkomst,
    SkdbFout,
    haal_op,
    herkomst,
    lees,
    load,
    sleutel,
)
from .overzicht import (
    ARBEIDSMARKT,
    NSE_THEMAS,
    SORTERINGEN,
    TOELATING,
    VORMEN,
    doorstroom_bachelor_master,
    doorstroom_mbo_hbo,
    instellingen,
    jaren,
    numerus_fixus,
    opleidingen,
    studie,
    toelating,
    zoek_studies,
)
from .schemakaart import MOGELIJKHEDEN, schema


def catalog() -> list[dict]:
    """De SKDB als catalogusrecord (lokale JSON): één record, de hele export, met de namen van haar tabellen.

    Alleen de namen (#978): de omschrijvingen, kolommen en types zijn het woordenboek van LCSK en komen uit een
    opgehaalde export (`schema`), niet uit de repo.
    """
    [record] = json.loads(
        files("onderwijsbronnen.skdb.data").joinpath("skdb_resources.json").read_text(encoding="utf-8")
    )
    return [sleutels.in_record({**record, "tabellen": sorted(MOGELIJKHEDEN)}, _SLEUTELS, "")]


# De sleutels in de uitkomst van de overzichten (`opleidingen`, `studie`, `doorstroom_bachelor_master`, #958): vast,
# want het schema staat niet in de repo. De ruwe tabellen (instellingCode, opleidingCode, soiId, …) dragen ze onder hun
# eigen kolomnaam; `sleutels.paren` leest die uit het schema van een opgehaalde export.
_SLEUTELS = [
    {"kolom": "brin", "sleutel": "brin"},
    {"kolom": "croho", "sleutel": "croho"},
    {"kolom": "master_croho", "sleutel": "croho"},
    {"kolom": "roa_opleidingstype", "sleutel": "roa_opleidingstype"},
]


# ── broncontract (#911) ────────────────────────────────────────────────────────

BRON = "skdb"
catalogusrecords = catalog
laad = load


def metadata(record: dict) -> dict:
    return broncontract.metadata(
        BRON,
        record["_skdb_id"],
        record.get("bron"),
        voorlopig=False,
        redenen={
            "peildatum_of_editie": (
                "de lader leest de export van vandaag; het versienummer en de exportdatum staan in de herkomst van een "
                "lading, niet in de catalogus"
            ),
            "laatste_update": "de exportdatum staat in de herkomst van een lading, niet in de catalogus",
        },
    )


__all__ = [
    "ARBEIDSMARKT", "NSE_THEMAS", "SORTERINGEN", "TOELATING", "VORMEN", "doorstroom_bachelor_master", "doorstroom_mbo_hbo",
    "instellingen", "jaren", "numerus_fixus", "opleidingen", "studie", "toelating", "zoek_studies",
    "API", "BRON", "DOCUMENTATIE", "EXPORT", "LEVERANCIER", "SLEUTEL_ENV", "USER_AGENT", "VEREIST", "VERPLICHTE_ZIN",
    "Export", "GeenSleutel", "Herkomst", "SkdbFout", "catalog", "catalogusrecords", "haal_op", "herkomst", "laad",
    "lees", "load", "metadata", "schema", "sleutel",
]
