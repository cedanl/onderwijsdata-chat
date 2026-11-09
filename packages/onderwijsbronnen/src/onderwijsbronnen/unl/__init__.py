"""Universiteiten van Nederland (UNL): het WOPI-personeelsbestand van de 14 universiteiten (#936).

Personeel in dienst op 31 december, per universiteit (BRIN) en landelijk: fte per functiecategorie met vast of
tijdelijk (tabel `functie`), en personen per leeftijdsklasse (tabel `personen`). Elke tabel zonder of met het
HOOP-gebied Gezondheid (`gezo="excl"` of `"incl"`), totaal of alleen vrouwen. Alleen wo; voor hbo en mbo bestaat geen
open personeelsbestand per instelling.

Gebruik:
    from onderwijsbronnen import unl

    df = unl.load("functie")                         # fte, zonder GEZO, totaal (nieuwste editie)
    df = unl.load("personen", gezo="incl")           # personen per leeftijdsklasse, met GEZO

    wopi = unl.lees(*unl.haal_op())                  # alle tabellen van één download, met de herkomst
    wopi.herkomst.peildatum                          # "31-12-2025"

Licentie: UNL zegt niets over hergebruik ("De universiteiten zijn eigenaar van deze gegevens"). Dit pakket bevat
daarom geen data van UNL; de lader haalt de nieuwste editie van de pagina op het moment van gebruik.
"""

from __future__ import annotations

import json
from importlib.resources import files

from .._kern import broncontract, sleutels
from .wopi import (
    AANTAL_UNIVERSITEITEN,
    GESLACHT,
    GEZO,
    PAGINA,
    TABELLEN,
    USER_AGENT,
    Herkomst,
    Tabel,
    Wopi,
    WopiFout,
    bestandslink,
    haal_op,
    lees,
    load,
)


def catalog() -> list[dict]:
    """De UNL-bron als catalogusrecord (lokale JSON): één record, het WOPI-bestand, met de BRIN-code van elke rij als
    sleutel (`brin` in `load`, #958)."""
    records = json.loads(files("onderwijsbronnen.unl.data").joinpath("unl_resources.json").read_text(encoding="utf-8"))
    return [sleutels.in_record(r, [{"kolom": "brin", "sleutel": "brin"}], "") for r in records]


# ── broncontract (#911) ────────────────────────────────────────────────────────

BRON = "unl"
catalogusrecords = catalog
laad = load


def metadata(record: dict) -> dict:
    return broncontract.metadata(
        BRON,
        record["_unl_id"],
        record.get("bron"),
        voorlopig=False,
        redenen={
            "peildatum_of_editie": (
                "de lader leest de nieuwste editie van de pagina; de peildatum (31-12 van het editiejaar) staat in de "
                "herkomst van een lading, niet in de catalogus"
            ),
            "laatste_update": "de Last-Modified van het bestand staat in de herkomst van een lading, niet in de catalogus",
        },
    )


__all__ = [
    "AANTAL_UNIVERSITEITEN", "BRON", "GESLACHT", "GEZO", "PAGINA", "TABELLEN", "USER_AGENT", "Herkomst", "Tabel",
    "Wopi", "WopiFout", "bestandslink", "catalog", "catalogusrecords", "haal_op", "laad", "lees", "load", "metadata",
]
