"""De zoekpoort voor vo-context (#557, #877) op de vragenset: zonder vervolgvraag geen VO_CONTEXT-record (#559).

Elke mbo-, hbo- en wo-vraag zoekt met zijn `zoekinput` en met de `vraag` zelf, met zijn eigen `source`
en `geo_niveau`; een mbo-vraag ook met `source` cbs en duo. Gaat de tekst niet over het ho of over doorstroom
uit het vo (`opent_vo_context`), dan heeft geen treffer in de top 50 een ID uit `scopeprofiel.VO_CONTEXT` of
het veld `context`. Offline en zonder instellingsregister, net als de meting (harnas.py).
"""

import json

import pytest

from tests.retrieval_baseline import harnas, rapport
from tools import catalog, scopeprofiel
from tools.ho_markers import beurtvraag, opent_vo_context, vo_deel_poort

_TOP_N = 50
_VELDEN = ("zoekinput", "vraag")
_MBO_BRONNEN = ("cbs", "duo")

_VRAGEN = [v for v in harnas.laad_vragen() if v["sector"] in rapport.SECTOREN]


def _bronnen(vraag: dict) -> list[str]:
    eigen = vraag.get("source", "both")
    extra = _MBO_BRONNEN if vraag["sector"] == "mbo" else ()
    return list(dict.fromkeys((eigen, *extra)))


_ZOEKACTIES = [(v, veld, bron) for v in _VRAGEN for veld in _VELDEN for bron in _bronnen(v)]
_DICHT = [z for z in _ZOEKACTIES if not opent_vo_context(z[0][z[1]])]
_OPEN = [z for z in _ZOEKACTIES if opent_vo_context(z[0][z[1]])]


def _doorstroomvraag(vraag: dict) -> bool:
    """Een vraag met een vo-contextrecord als label: doorstroom naar vervolgonderwijs (#559, #877). Of een RIO-register
    met vo- en vavo-typen als label, bij een vraag die zijn vo-deel opent (#880)."""
    if set(vraag["geaccepteerd"]) & set(scopeprofiel.VO_CONTEXT):
        return True
    with beurtvraag(vraag["vraag"]):
        return bool(set(vraag["geaccepteerd"]) & set(scopeprofiel.SECTORFILTER_VO_CONTEXT)) and vo_deel_poort()


def _treffers(vraag: dict, veld: str, bron: str) -> list[dict]:
    with harnas.zonder_netwerk(), harnas.zonder_instellingsregister():
        resultaat = catalog.search_catalog(vraag[veld], bron, top_n=_TOP_N, geo_niveau=vraag.get("geo_niveau"))
    waar = f"{vraag['id']} ({veld}, source={bron})"
    try:
        envelop = json.loads(resultaat)
    except json.JSONDecodeError:
        pytest.fail(f"{waar}: search_catalog gaf geen JSON-envelope: {resultaat[:200]!r}")
    if not isinstance(envelop, dict) or "status" not in envelop:
        pytest.fail(f"{waar}: search_catalog gaf JSON zonder status: {resultaat[:200]!r}")
    if envelop["status"] != "candidates":  # geen treffers: no_match, needs_clarification, geo-melding
        return []
    return [t for t in envelop.get("kandidaten") or [] if isinstance(t, dict)]


def _vo_context(treffers: list[dict]) -> list[str]:
    return [
        str(scopeprofiel.dataset_id(t) or t.get("bron"))
        for t in treffers
        if scopeprofiel.is_vo_context(t) or "context" in t
    ]


@pytest.mark.parametrize(
    ("vraag", "veld", "bron"), [pytest.param(*z, id=f"{z[0]['id']}-{z[1]}-{z[2]}") for z in _DICHT]
)
def test_zonder_vervolgvraag_geen_vo_context(vraag, veld, bron):
    gevonden = _vo_context(_treffers(vraag, veld, bron))
    assert gevonden == [], f"{vraag['id']} ({veld}, source={bron}): vo-context zonder vervolgvraag in {vraag[veld]!r}"


def test_alleen_een_mbo_doorstroomvraag_opent_de_poort():
    """De lektest (#877): een mbo-vraag opent de poort alleen als ze over doorstroom uit het vo gaat. Anders zou
    een marker de toets hierboven voor die vraag stil uitzetten."""
    open_ = [
        (v["id"], v[veld])
        for v in _VRAGEN
        if v["sector"] == "mbo" and not _doorstroomvraag(v)
        for veld in _VELDEN
        if opent_vo_context(v[veld])
    ]
    assert open_ == []


def test_elke_mbo_zoekactie_zonder_doorstroom_valt_onder_de_poorttoets():
    mbo = [z for z in _ZOEKACTIES if z[0]["sector"] == "mbo" and not _doorstroomvraag(z[0])]
    assert mbo and all(z in _DICHT for z in mbo)


def test_controle_een_vervolgvraag_met_open_poort_vindt_vo_context():
    """De toets is niet leeg: bij een vervolgvraag komt een VO_CONTEXT-record wel door, met zijn etiket."""
    gevonden = [t for z in _OPEN for t in _treffers(*z) if scopeprofiel.is_vo_context(t)]
    assert gevonden, "geen enkele vervolgvraag vindt een VO_CONTEXT-record"
    assert all(t.get("context") == scopeprofiel.VO_CONTEXT_ETIKET for t in gevonden)
