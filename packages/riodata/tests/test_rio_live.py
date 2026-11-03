"""Live contracttest tegen RIO LOD API v3: doet het contract wat de spec belooft?

Draait alleen op verzoek (``RIODATA_LIVE=1``), omdat elke test het netwerk raakt:

    RIODATA_LIVE=1 uv run pytest tests/test_rio_live.py -v

Toetst per lijst-resource het endpoint, elk filter uit het contract (een filter dat de API niet
kent geeft HTTP 400 "not allowed"), de sub-resources uit de spec, de resources die alleen als
sub-resource bestaan, de ID-formaten in echte records, de paginering en het ``pageSize``-maximum.
De v2-verwijdering van 19-10-2026 (HTTP 410 op alles) had deze test in één run laten zien.
"""
from __future__ import annotations

import datetime as dt
import os
import re
from functools import lru_cache

import httpx
import pytest

import riodata
from riodata import _filtercontract as fc
from riodata import client, contract, filtercontract

pytestmark = pytest.mark.skipif(not os.environ.get("RIODATA_LIVE"), reason="live RIO-test: zet RIODATA_LIVE=1")

BASE = client.BASE_URL
UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
NIET_TOEGESTAAN = "not allowed"


def _get(pad: str, **params) -> httpx.Response:
    return httpx.get(f"{BASE}/{pad}", params=params or None, timeout=60)


def _items(r: httpx.Response) -> list:
    body = r.json()
    return next(iter(body.get("_embedded", {}).values()), []) if isinstance(body, dict) else body


@lru_cache(maxsize=None)
def _eerste(resource: str) -> dict:
    """Het eerste record van een lijst-resource, als bron voor voorbeeldwaarden."""
    r = _get(resource, pageSize=1)
    r.raise_for_status()
    (item,) = _items(r)
    return item


def _voorbeeldwaarde(resource: str, f: dict) -> str:
    """Een waarde waarmee de API het filter moet accepteren (een leeg resultaat is goed)."""
    if f["enum"]:
        return f["enum"][0]
    if f["format"] == "date":
        return dt.date.today().isoformat()
    naam = f["naam"]
    vast = {
        "volledigeNaam": "Aeres Hogeschool",
        "plaatsnaam": "Ede",
        "instellingserkenningId": "30TX",
        "opleidingseenheidcode": "1001O1001",
        "erkendeopleidingscode": "34479",  # maximaal 8 tekens (GGM-003)
    }
    if naam in vast:
        return vast[naam]
    if naam == "aangebodenOpleidingId":
        return _eerste("aangeboden-opleidingen")["id"]
    if naam == "onderwijslocatieId":
        return _eerste("onderwijslocaties")["id"]
    if naam == "organisatorischeEenheidcode":
        return _eerste("organisatorische-eenheden")["id"]
    if naam == "onderwijslocatiegebruikId":
        return _eerste("onderwijslocaties")["id"]  # zelfde opbouw; alleen de acceptatie telt
    raise AssertionError(f"geen voorbeeldwaarde voor filter {naam} van {resource}")


@pytest.mark.parametrize("resource", fc.lijstresources())
def test_elke_lijstresource_antwoordt_met_een_pagina(resource):
    r = _get(resource, pageSize=1)
    assert r.status_code == 200, f"{resource}: HTTP {r.status_code} {r.text[:120]}"
    assert "_embedded" in r.json()


@pytest.mark.parametrize(
    "resource,filter_naam",
    [(res, f["naam"]) for res in fc.lijstresources() for f in filtercontract()["resources"][res]["filters"]],
)
def test_elk_filter_uit_het_contract_wordt_geaccepteerd(resource, filter_naam):
    f = fc.filters(resource)[filter_naam]
    r = _get(resource, pageSize=1, **{filter_naam: _voorbeeldwaarde(resource, f)})
    assert r.status_code == 200, f"{resource}?{filter_naam}: HTTP {r.status_code} {r.text[:160]}"
    assert NIET_TOEGESTAAN not in r.text


def test_v2_filternamen_worden_geweigerd():
    """De hernoeming is echt: de oude naam is op v3 geen filter meer."""
    assert _get("erkenningen", erkenningtype="BEVOEGD_GEZAG", pageSize=1).status_code == 400
    assert _get("opleidingen", opleidingseenheidtype="HOOPLEIDING", pageSize=1).status_code == 400


@pytest.mark.parametrize(
    "resource,sub",
    [(res, sub) for res in fc.lijstresources() for sub in filtercontract()["resources"][res]["sub_resources"]],
)
def test_subresources_uit_de_spec_bestaan(resource, sub):
    """Het pad bestaat; een specifiek record kan er leeg zijn (404), maar nooit weg (410) of geweigerd (400)."""
    r = _get(f"{resource}/{_eerste(resource)['id']}/{sub}")
    if r.status_code >= 500:  # een trage sub-resource (504) zegt niets over het contract
        pytest.skip(f"{resource}/{{id}}/{sub}: RIO antwoordt HTTP {r.status_code}")
    assert r.status_code in (200, 404), f"{resource}/{{id}}/{sub}: HTTP {r.status_code} {r.text[:120]}"


@pytest.mark.parametrize("resource", sorted(set(filtercontract()["resources"]) - set(fc.lijstresources())))
def test_resources_zonder_lijstendpoint_bestaan_alleen_via_het_subpad(resource):
    assert _get(resource, pageSize=1).status_code == 404
    with pytest.raises(ValueError, match="related"):
        riodata.fetch(resource)
    (pad, *_) = filtercontract()["resources"][resource]["via"]
    ouder = pad.strip("/").split("/")[0]
    r = _get(pad.strip("/").replace("{id}", _eerste(ouder)["id"]))
    assert r.status_code in (200, 404), f"{pad}: HTTP {r.status_code}"


@pytest.mark.parametrize("resource,formaat", sorted(contract._RIO_ID_FORMATEN.items()))
def test_id_formaten_kloppen_met_echte_records(resource, formaat):
    record_id = _eerste(resource)["id"]
    patroon = UUID if formaat == "uuid" else re.compile(formaat)
    assert patroon.fullmatch(record_id), f"{resource}: id {record_id!r} past niet op {formaat}"


def test_aeres_hogeschool_met_vestigingen_via_instellingsrelaties():
    """De route van onderwijsdata-chat (naam → erkenning → relaties): v3 draagt de ID's als veld."""
    (instelling,) = [
        e for e in riodata.fetch("erkenningen", volledigeNaam="Aeres Hogeschool", type="ERKENDE_ONDERWIJSINSTELLING",
                                 datumGeldigOp=dt.date.today().isoformat())
        if e["volledigeNaam"] == "Aeres Hogeschool" and e["wet"] == "WHW"
    ]
    assert instelling["code"] == "30TX" and instelling["type"] == "ERKENDE_ONDERWIJSINSTELLING"
    assert riodata.get("erkenningen", "30TX")["volledigeNaam"] == "Aeres Hogeschool"
    relaties = riodata.related("erkenningen", "30TX", "instellingsrelaties")
    onder = {r["naarErkenningId"] for r in relaties if r["soort"] == "HIERARCHISCH" and r["vanErkenningId"] == "30TX"}
    assert {"30TX00", "30TX01", "30TX02", "30TX03", "30TX04"} <= onder
    for r in relaties:
        assert r["_links"]["van"]["href"].startswith(f"{BASE}/erkenningen/{r['vanErkenningId']}")


def test_paginering_is_1_gebaseerd_en_fetch_volgt_de_next_link():
    """v3 telt pagina's vanaf 1: ``page=0`` geeft dezelfde pagina als ``page=1`` en de next-link
    gaat dan naar 2, dus ``fetch`` (dat bij 0 begint) mist niets. De laatste pagina kan leeg zijn
    met alleen een self-link. Dubbele ID's in een reeks komen uit de data (een erkenning per
    geldigheidsperiode), niet uit de paginering: ``sort=id`` geeft dezelfde dubbelingen."""
    nul = riodata.fetch("erkenningen", type="ERKENDE_VESTIGING", page=0, pageSize=100)
    een = riodata.fetch("erkenningen", type="ERKENDE_VESTIGING", page=1, pageSize=100)
    twee = riodata.fetch("erkenningen", type="ERKENDE_VESTIGING", page=2, pageSize=100)
    assert [e["id"] for e in nul] == [e["id"] for e in een]
    assert len(twee) == 100 and {e["id"] for e in een}.isdisjoint({e["id"] for e in twee})
    assert _get("erkenningen", pageSize=101).status_code == 400

    alles = riodata.fetch("erkenningen", type="ERKENDE_SAMENWERKING")  # drie pagina's
    handmatig, url, params = [], f"{BASE}/erkenningen", {"type": "ERKENDE_SAMENWERKING", "page": 1, "pageSize": 100}
    while url:
        body = httpx.get(url, params=params, timeout=60).json()
        if "_embedded" not in body:
            break
        handmatig += [e["id"] for e in body["_embedded"]["Erkenningen"]]
        url, params = body["_links"].get("next", {}).get("href"), None
    assert len(alles) > 200 and [e["id"] for e in alles] == handmatig
    gesorteerd = riodata.fetch("erkenningen", type="ERKENDE_SAMENWERKING", sort="id")
    assert sorted(e["id"] for e in gesorteerd) == sorted(handmatig)
