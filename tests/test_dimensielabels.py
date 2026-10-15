"""Het label bij een CBS-getal klopt met de gekozen selectie (#401, audit 14 §3.2).

'Hoeveel studenten heeft Utrecht?' gaf 118.160 als 'ingeschreven personen (leerlingen +
studenten, alle onderwijssoorten)'. In de bron is dat A025279, 'Totaal (speciaal)
basisonderwijs'. Het getal stond in de tooluitvoer; alleen het label was fout.
"""

import json

import pandas as pd
import pytest

from agent.dimensielabels import selectie_regels, verkeerde_dimensielabels
from agent.telling import telling_blok
from tools import cbs, store
from tools.store import KeyMeta

_TABEL = pd.DataFrame(
    {
        "Onderwijssoort": ["T001038", "A025279", "A025280"],
        "Onderwijssoort_label": ["Totaal onderwijssoorten", "Totaal (speciaal) basisonderwijs", "Basisonderwijs"],
        "RegioS": ["PV26", "PV26", "PV26"],
        "RegioS_label": ["Utrecht (PV)", "Utrecht (PV)", "Utrecht (PV)"],
        "Perioden": ["2024JJ00"] * 3,
        "Leerlingen_1": [400000, 118160, 110000],
    }
)


def _beurt(*keys: str) -> list[str]:
    return [json.dumps({"data_key": k}) for k in keys]


@pytest.fixture(autouse=True)
def _cbs():
    store.clear()
    cbs.register_dimensions("85701NED", ["Onderwijssoort", "RegioS", "Perioden"])
    store.put("cbs:85701NED", _TABEL, KeyMeta(bron="cbs", dataset="85701NED", periodekolom="Perioden"))
    yield
    store.clear()
    cbs.clear_dimensions()


def _selectie(*codes: str) -> str:
    key = f"cbs:85701NED:{'-'.join(codes)}"
    store.derive("cbs:85701NED", key, _TABEL[_TABEL["Onderwijssoort"].isin(codes)])
    return key


def test_alle_onderwijssoorten_bij_alleen_basisonderwijs_is_een_probleem():
    tekst = "Utrecht telt 118.160 ingeschreven personen (leerlingen + studenten, alle onderwijssoorten)."
    problemen = verkeerde_dimensielabels(tekst, _beurt("cbs:85701NED", _selectie("A025279")))

    assert any("alle onderwijssoorten" in p and "Totaal (speciaal) basisonderwijs" in p for p in problemen)


def test_studenten_bij_een_selectie_van_basisonderwijs_is_een_probleem():
    problemen = verkeerde_dimensielabels("Utrecht heeft 118.160 studenten.", _beurt(_selectie("A025279")))

    assert any("studenten" in p and "leerlingen" in p for p in problemen)


def test_leerlingen_bij_basisonderwijs_is_in_orde():
    assert verkeerde_dimensielabels("Utrecht heeft 118.160 leerlingen.", _beurt(_selectie("A025279"))) == []


def test_alle_onderwijssoorten_bij_het_totaal_is_in_orde():
    tekst = "Utrecht telt 400.000 leerlingen en studenten in alle onderwijssoorten."
    assert verkeerde_dimensielabels(tekst, _beurt(_selectie("T001038"))) == []


def test_een_selectie_met_meerdere_onderwijssoorten_zwijgt():
    tekst = "Alle onderwijssoorten samen, uitgesplitst."
    assert verkeerde_dimensielabels(tekst, _beurt(_selectie("T001038", "A025279"))) == []


def test_zonder_cbs_data_zwijgt_de_controle():
    store.put("duo:p01hoinges:0", pd.DataFrame({"AANTAL": [1]}), KeyMeta(bron="duo", dataset="p01hoinges"))
    assert verkeerde_dimensielabels("Alle onderwijssoorten, 1 student.", _beurt("duo:p01hoinges:0")) == []


def test_selectieregel_noemt_de_gekozen_labels_en_niet_de_periode():
    [regel] = selectie_regels(_beurt("cbs:85701NED", _selectie("A025279")))

    assert "85701NED" in regel
    assert "Onderwijssoort: Totaal (speciaal) basisonderwijs" in regel
    assert "RegioS: Utrecht (PV)" in regel
    assert "Perioden" not in regel


def test_de_gekozen_labels_staan_in_het_telling_blok():
    assert "Totaal (speciaal) basisonderwijs" in telling_blok(_beurt(_selectie("A025279")))


def test_een_dimensie_met_veel_waarden_is_geen_selectie():
    [regel] = selectie_regels(_beurt("cbs:85701NED"))

    assert "Onderwijssoort" not in regel and "RegioS: Utrecht (PV)" in regel


# --- vo-contextrecords (epic #554, #558): echte dimensienamen, synthetische rijen ---

_CONTEXTDIMENSIES = {
    "85566NED": ["OnderwijsPositieBasisjaar", "OnderwijsPositieVolgendSchooljaar"],
    "85381NED": ["OnderwijssoortInDetail"],
    "85382NED": ["Onderwijssoort"],
}
_VO_LABELS = [
    "Leerjaar 1",
    "Vmbo-b 3",
    "Havo 5 met diploma",
    "Vwo 6",
    "Praktijkonderwijs",
    "Totaal voortgezet onderwijs (vo)",
    "Totaal voortgezet speciaal onderwijs",
    "Vso uitstroomprofiel arbeidsmarkt",
    "Havo",
    "Vwo",
]
_HO_LABELS = [
    "Hoger beroepsonderwijs",
    "Wetenschappelijk onderwijs",
    "Totaal hoger onderwijs",
    "Mbo niveau 4 (inclusief extranei)",
]
_VO_SELECTIES = [
    *(("85566NED", "OnderwijsPositieBasisjaar", label) for label in _VO_LABELS),
    *(("85566NED", "OnderwijsPositieVolgendSchooljaar", label) for label in ("Havo 5 met diploma", "Vwo 6")),
    *(("85381NED", "OnderwijssoortInDetail", label) for label in _VO_LABELS),
    *(("85382NED", "Onderwijssoort", label) for label in ("Havo", "Vwo", "Totaal voortgezet onderwijs (vo)")),
]


def _contextselectie(dataset: str, dim: str, label: str) -> str:
    """Een CBS-key waarin alleen `dim` op `label` ligt; een andere dimensie heeft twee waarden."""
    df = pd.DataFrame({"Perioden": ["2024JJ00"] * 2, "Aantal_1": [1200, 800]})
    for d in _CONTEXTDIMENSIES[dataset]:
        gekozen = d == dim
        df[d] = ["A000001"] * 2 if gekozen else ["A000002", "A000003"]
        df[d + "_label"] = [label] * 2 if gekozen else ["Vmbo 3", "Wetenschappelijk onderwijs"]
    cbs.register_dimensions(dataset, [*_CONTEXTDIMENSIES[dataset], "Perioden"])
    store.put(f"cbs:{dataset}", df, KeyMeta(bron="cbs", dataset=dataset, periodekolom="Perioden"))
    return f"cbs:{dataset}"


@pytest.mark.parametrize(("dataset", "dim", "label"), _VO_SELECTIES)
def test_studenten_bij_een_vo_label_van_een_contextrecord_is_een_probleem(dataset, dim, label):
    key = _contextselectie(dataset, dim, label)

    [probleem] = verkeerde_dimensielabels("In 2024 ging het om 2.000 studenten.", _beurt(key))

    assert "studenten" in probleem and "leerlingen" in probleem and label in probleem


@pytest.mark.parametrize(("dataset", "dim", "label"), _VO_SELECTIES)
def test_leerlingen_bij_een_vo_label_van_een_contextrecord_is_in_orde(dataset, dim, label):
    key = _contextselectie(dataset, dim, label)

    assert verkeerde_dimensielabels("In 2024 ging het om 2.000 leerlingen, later studenten.", _beurt(key)) == []


@pytest.mark.parametrize("label", _HO_LABELS)
def test_studenten_bij_alleen_een_ho_label_is_in_orde(label):
    key = _contextselectie("85566NED", "OnderwijsPositieVolgendSchooljaar", label)

    assert verkeerde_dimensielabels("Een jaar later waren het 2.000 studenten.", _beurt(key)) == []
