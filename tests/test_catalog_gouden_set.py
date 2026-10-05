"""Gouden set voor search_catalog: rangen zonder LLM, als meetlat vóór elke wijziging aan _score (#14, #33).

De catalogus komt uit riodata, vastgepind in uv.lock: een bevroren stand, dus een
nieuwe publicatie van DUO of CBS breekt deze test niet zolang de pin niet wijzigt.

Bekende missers staan als strict xfail: verbetert de score ze, dan faalt de test
en hoort de vraag naar GOED te verhuizen. Een regressie op GOED faalt met de rang erbij.
Baseline gemeten op 2 oktober 2026.
"""

import json
import logging

import pytest

from tools.catalog import search_catalog

# (query, doel-ID, maximale rang)
GOED = [
    ("ingeschrevenen wo", "p01hoinges", 3),
    ("Hoeveel eerstejaars heeft de Universiteit Utrecht?", "p02ho1ejrs", 3),
    ("eerstejaars hoger onderwijs", "p02ho1ejrs", 1),
    ("ingeschrevenen hoger onderwijs opleidingsvorm", "85423NED", 1),
    ("voortijdig schoolverlaters mbo", "85368NED", 1),
    ("gediplomeerden hoger onderwijs", "p04hogdipl", 1),
    ("gediplomeerde mbo-studenten", "gediplomeerde-mbo-studenten", 5),
    ("studentprognoses mbo per instelling", "studentprognoses-mbo-per-instelling", 1),
    ("prognoses vo per instelling", "voprognoses", 1),
    ("onderwijslocaties van een instelling", "onderwijslocaties", 1),
    ("opleidingserkenningen", "opleidingserkenningen", 1),
    # Gelijke score met p02ho1ejrs op rang 3/4; sinds de ID-tie-break (#344) staat p01hoinges voor.
    # Geen betere score: verschuift de score, dan kan deze vraag terug naar de missers.
    ("ingeschrevenen wo opleidingsvorm", "p01hoinges", 3),
    ("ingeschrevenen hbo voltijd deeltijd", "p01hoinges", 3),
]

# (query, doel-ID, maximale rang, gemeten rang bij de baseline)
BEKENDE_MISSERS = [
    ("Hoeveel voltijd studenten heeft de VU Amsterdam?", "p01hoinges", 3, 12),
    ("Hoeveel deeltijdstudenten zijn er landelijk in het hoger onderwijs?", "85423NED", 5, 12),
    ("Hoeveel vsv'ers zijn er in het mbo?", "85368NED", 5, None),
    # Audit 11: het model koos 01voins-v1 (alleen 2014-2018) voor een vo-prognose.
    ("leerlingenprognose voortgezet onderwijs", "voprognoses", 5, None),
]

_TOP_N = 15


def _ids(query: str) -> list[str]:
    logging.disable(logging.CRITICAL)
    try:
        hits = json.loads(search_catalog(query, top_n=_TOP_N))
    finally:
        logging.disable(logging.NOTSET)
    return [h.get("_cbs_id") or h.get("_ckan_id") or h.get("_rio_resource") for h in hits]


def _rang(query: str, doel: str) -> int | None:
    ids = _ids(query)
    return ids.index(doel) + 1 if doel in ids else None


@pytest.mark.parametrize(("query", "doel", "max_rang"), GOED)
def test_doel_staat_binnen_zijn_rang(query, doel, max_rang):
    rang = _rang(query, doel)
    assert rang is not None and rang <= max_rang, f"{doel} op rang {rang} (max {max_rang}) voor {query!r}"


@pytest.mark.parametrize(
    ("query", "doel", "max_rang"),
    [
        pytest.param(q, d, m, marks=pytest.mark.xfail(strict=True, reason=f"baseline: rang {r}"))
        for q, d, m, r in BEKENDE_MISSERS
    ],
)
def test_bekende_misser(query, doel, max_rang):
    rang = _rang(query, doel)
    assert rang is not None and rang <= max_rang, f"{doel} op rang {rang} (max {max_rang}) voor {query!r}"


def test_zelfde_vraag_geeft_dezelfde_volgorde():
    """Determinisme: bij bijna gelijke scores mag de volgorde niet per aanroep wisselen (#33)."""
    for query, _, _ in GOED:
        assert _ids(query) == _ids(query)
