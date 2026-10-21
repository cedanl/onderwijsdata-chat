"""De zoekpoort voor vo-context (#557) op de vragenset: zonder ho-marker geen HO_CONTEXT-record (#559).

Elke mbo-, hbo- en wo-vraag zoekt met zijn `zoekinput` en met de `vraag` zelf, met zijn eigen `source`
en `geo_niveau`; een mbo-vraag ook met `source` cbs en duo. Noemt de tekst geen ho (`noemt_ho`), dan
heeft geen treffer in de top 50 een ID uit `scopeprofiel.HO_CONTEXT` of het veld `context`. Offline en
zonder instellingsregister, net als de meting (harnas.py).
"""

import json

import pytest

from tests.retrieval_baseline import harnas, rapport
from tools import catalog, scopeprofiel
from tools.ho_markers import noemt_ho

_TOP_N = 50
_VELDEN = ("zoekinput", "vraag")
_MBO_BRONNEN = ("cbs", "duo")

_VRAGEN = [v for v in harnas.laad_vragen() if v["sector"] in rapport.SECTOREN]


def _bronnen(vraag: dict) -> list[str]:
    eigen = vraag.get("source", "both")
    extra = _MBO_BRONNEN if vraag["sector"] == "mbo" else ()
    return list(dict.fromkeys((eigen, *extra)))


_ZOEKACTIES = [(v, veld, bron) for v in _VRAGEN for veld in _VELDEN for bron in _bronnen(v)]
_DICHT = [z for z in _ZOEKACTIES if not noemt_ho(z[0][z[1]])]
_OPEN = [z for z in _ZOEKACTIES if noemt_ho(z[0][z[1]])]


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
        if scopeprofiel.is_ho_context(t) or "context" in t
    ]


@pytest.mark.parametrize(
    ("vraag", "veld", "bron"), [pytest.param(*z, id=f"{z[0]['id']}-{z[1]}-{z[2]}") for z in _DICHT]
)
def test_zonder_ho_marker_geen_vo_context(vraag, veld, bron):
    gevonden = _vo_context(_treffers(vraag, veld, bron))
    assert gevonden == [], f"{vraag['id']} ({veld}, source={bron}): vo-context zonder ho-marker in {vraag[veld]!r}"


def test_mbo_vragen_noemen_geen_ho():
    """Anders zou een marker de toets hierboven voor die vraag stil uitzetten."""
    met_marker = [(v["id"], v[veld]) for v in _VRAGEN if v["sector"] == "mbo" for veld in _VELDEN if noemt_ho(v[veld])]
    assert met_marker == []


def test_elke_mbo_zoekactie_valt_onder_de_poorttoets():
    mbo = [z for z in _ZOEKACTIES if z[0]["sector"] == "mbo"]
    assert mbo and all(z in _DICHT for z in mbo)


def test_controle_een_ho_vraag_met_open_poort_vindt_vo_context():
    """De toets is niet leeg: met een ho-marker komt een HO_CONTEXT-record wel door, met zijn etiket."""
    gevonden = [t for z in _OPEN for t in _treffers(*z) if scopeprofiel.is_ho_context(t)]
    assert gevonden, "geen enkele hbo/wo-vraag met ho-marker vindt een HO_CONTEXT-record"
    assert all(t.get("context") == scopeprofiel.HO_CONTEXT_ETIKET for t in gevonden)
