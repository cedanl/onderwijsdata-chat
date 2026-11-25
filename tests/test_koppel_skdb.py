"""koppel_data: SKDB naast DUO geeft de kleine-n-vlag per rij en de rijen zonder DUO-rij per graad, in code (#1231).

Het patroon van HU (25DW): in de koppeling van de Studiekeuzedatabase met DUO noemde het antwoord een opleiding met 28
NSE-respondenten (CROHO 80166) niet onzeker, en 31 opleidingen zonder DUO-rij "bijna allemaal masters": het model
telde zelf. Nu zet de code per SKDB-rij `onzeker` (de regel van get_studiekeuze: minder dan MIN_RESPONDENTEN, of geen
bekend aantal bij een NSE-cijfer) en telt ze de rijen `alleen SKDB` per graad (`niet_gekoppeld_per_graad`). De aantallen
van HU zijn verzonnen; de vorm (29 master, 1 bachelor, 1 associate degree zonder DUO-rij) is die van het issue.
"""

import json

import pandas as pd
import pytest

import tools
from data import instellingen
from tools import koppel, opvolger, store, studiekeuze
from tools.schemas import TOOL_KOPPEL_DATA, TOOL_SCHEMAS
from tools.store import KeyMeta

_SKDB = "skdb:opleidingen:proef1231"
_DUO = "duo:p01hoinges:0"
_DUO2 = "duo:p02ho1ejrs:0"
_SKDB_META = KeyMeta(bron="skdb", dataset="skdb:studiekeuzedatabase")
_DUO_META = KeyMeta(bron="duo", dataset="p01hoinges", resource=0, periodekolom="STUDIEJAAR")
_ALLEEN = "alleen SKDB"

# Met een DUO-rij: CROHO -> (nse_respondenten, nse_oordeel). 80166 is de HU-rij met 28 respondenten.
_GEKOPPELD = {
    "30020": (16, 3.4),
    "80166": (28, 3.9),
    "34479": (29, 3.7),
    "39280": (30, 3.8),
    "30010": (None, 3.6),  # een oordeel zonder bekend aantal (#979): onzeker
    "34410": (None, None),  # geen NSE-cijfer: niets om onzeker te noemen
}
_VERWACHT = {"30020": True, "80166": True, "34479": True, "39280": False, "30010": True, "34410": False}
# Zonder DUO-rij: 29 masters, 1 bachelor, 1 associate degree.
_ZONDER_DUO = [(f"6{i:04d}", "Master") for i in range(29)] + [("31000", "Bachelor"), ("80001", "Associate degree")]


@pytest.fixture(autouse=True)
def geen_netwerk(monkeypatch):
    """Geen register en een RIO zonder licenties: geen opvolger, de koppeling zoals zonder RIO."""
    monkeypatch.setattr(instellingen, "get_all", lambda: [])
    monkeypatch.setattr(opvolger, "onderwijslicenties", lambda brin, peildatum=None: ())
    opvolger.wis_caches()


def _hu(zonder_duo=_ZONDER_DUO) -> pd.DataFrame:
    rijen = [
        {"brin": "25DW", "croho": c, "graad": "Bachelor", "nse_oordeel": o, "nse_respondenten": n}
        for c, (n, o) in _GEKOPPELD.items()
    ] + [{"brin": "25DW", "croho": c, "graad": g, "nse_oordeel": None, "nse_respondenten": None} for c, g in zonder_duo]
    skdb = pd.DataFrame(rijen)
    store.put(_SKDB, skdb, _SKDB_META)
    duo = pd.DataFrame(
        {
            "STUDIEJAAR": 2025,
            "INSTELLINGSCODE_ACTUEEL": "25DW",
            "OPLEIDINGSCODE_ACTUEEL": [float(c) for c in [*_GEKOPPELD, "99999"]],
            "AANTAL_INGESCHREVENEN": range(100, 100 + len(_GEKOPPELD) + 1),
        }
    )
    store.put(_DUO, duo, _DUO_META)
    return skdb


def _koppel(data_key=_SKDB, andere_key=_DUO, sleutels=("brin", "croho")) -> dict:
    uit, _ = tools.dispatch(
        TOOL_KOPPEL_DATA, {"data_key": data_key, "andere_key": andere_key, "sleutels": list(sleutels)}
    )
    return json.loads(uit)


def _vlaggen(uit: dict) -> dict[str, object]:
    return {r["croho"]: r[koppel.ONZEKER] for r in uit["rijen"]}


# --- onzeker per rij -------------------------------------------------------------------------------------------------


def test_de_kleine_n_vlag_staat_per_skdb_rij_in_het_resultaat():
    """16, 28 en 29 respondenten zijn onzeker, 30 niet; zonder aantal maar met een oordeel ook (#979)."""
    _hu()
    uit = _koppel()
    vlaggen = _vlaggen(uit)
    for croho, onzeker in _VERWACHT.items():
        assert vlaggen[croho] is onzeker, croho
    assert vlaggen["80166"] is True  # het HU-geval: 28 respondenten


def test_de_vlag_staat_ook_in_de_bewaarde_tabel_na_koppelstatus():
    _hu()
    uit = _koppel()
    df = store.get(uit["data_key"])
    assert list(df.columns[:4]) == ["brin", "croho", "koppelstatus", koppel.ONZEKER]
    vlag = df.set_index("croho")[koppel.ONZEKER]
    assert {c: vlag[c] for c in _VERWACHT} == _VERWACHT
    assert vlag["99999"] is None  # een rij alleen uit DUO heeft geen SKDB-kant
    assert vlag["60000"] is False  # zonder DUO-rij en zonder NSE-cijfer


def test_de_vlag_volgt_de_regel_van_get_studiekeuze():
    """Dezelfde regel, geen tweede getal: wat studiekeuze.is_onzeker zegt, zegt de koppeling."""
    _hu()
    df = store.get(_koppel()["data_key"])
    skdb = df[df["koppelstatus"] != "alleen DUO"]
    rijen = skdb[["nse_respondenten", "nse_oordeel"]].astype(object).to_dict(orient="records")
    assert list(skdb[koppel.ONZEKER]) == [studiekeuze.is_onzeker(r) for r in rijen]
    assert studiekeuze.MIN_RESPONDENTEN == 30


@pytest.mark.parametrize(
    ("n", "onzeker"), [(16, True), (28, True), (29, True), (30, False), (None, True), (28.0, True), (30.0, False)]
)
def test_is_onzeker_bij_de_grens(n, onzeker):
    """Na een koppeling is een aantal een float (28.0, NaN): 30.0 is genoeg, NaN is geen bekend aantal."""
    assert studiekeuze.is_onzeker({"nse_respondenten": n, "nse_oordeel": 3.9}) is onzeker
    assert studiekeuze.is_onzeker({"nse_respondenten": float("nan") if n is None else n, "nse_oordeel": 3.9}) is onzeker
    assert studiekeuze.is_onzeker({"nse_respondenten": n, "nse_oordeel": float("nan")}) is False


def test_de_kant_van_de_vraag_maakt_niet_uit():
    _hu()
    assert _vlaggen(_koppel(_DUO, _SKDB)) == _vlaggen(_koppel())


# --- niet gekoppeld per graad ----------------------------------------------------------------------------------------


def test_de_rijen_zonder_duo_rij_staan_per_graad_geteld():
    """HU: 29 masters, 1 bachelor, 1 associate degree zonder DUO-rij; gelijk aan een telling op de tabel zelf."""
    _hu()
    uit = _koppel()
    assert uit[koppel.PER_GRAAD] == {"bachelor": 1, "master": 29, "associate degree": 1}
    df = store.get(uit["data_key"])
    direct = df.loc[df["koppelstatus"] == _ALLEEN, "graad"].str.lower().value_counts().to_dict()
    assert uit[koppel.PER_GRAAD] == direct
    assert sum(uit[koppel.PER_GRAAD].values()) == uit["telling"][_ALLEEN] == 31


def test_een_onbekende_of_lege_graad_telt_onder_een_eigen_sleutel():
    _hu([("60000", "Master"), ("60001", None), ("60002", ""), ("60003", "Doctoraal"), ("80001", "ad")])
    uit = _koppel()
    assert uit[koppel.PER_GRAAD] == {"master": 1, "associate degree": 1, "doctoraal": 1, koppel.GEEN_GRAAD: 2}
    assert sum(uit[koppel.PER_GRAAD].values()) == uit["telling"][_ALLEEN]


def test_een_botsende_graadkolom_telt_de_skdb_kant():
    """Heeft DUO zelf een kolom graad, dan heet die van de SKDB SKDB_graad; de telling leest de SKDB-kant."""
    _hu()
    store.put(_DUO, store.get(_DUO).assign(graad="wo"), _DUO_META)
    uit = _koppel()
    assert uit[koppel.PER_GRAAD] == {"bachelor": 1, "master": 29, "associate degree": 1}


def test_de_toelichting_zegt_de_vlag_en_de_telling_over_te_nemen():
    _hu()
    uit = _koppel()
    alleen = uit["toelichting"][_ALLEEN]
    assert koppel.PER_GRAAD in alleen and "tel de rijen niet zelf" in alleen
    for status in ("beide", _ALLEEN):
        assert "onzeker: true" in uit["toelichting"][status] and "neem haar over" in uit["toelichting"][status]
        assert f"minder dan {studiekeuze.MIN_RESPONDENTEN} NSE-respondenten" in uit["toelichting"][status]
    assert "onzeker" not in uit["toelichting"]["alleen DUO"]
    beschrijving = next(t for t in TOOL_SCHEMAS if t["function"]["name"] == TOOL_KOPPEL_DATA)["function"]["description"]
    assert koppel.ONZEKER in beschrijving and koppel.PER_GRAAD in beschrijving


def test_zonder_rijen_alleen_skdb_geen_telling_per_graad():
    _hu([])
    uit = _koppel()
    assert koppel.PER_GRAAD not in uit and _ALLEEN not in uit["telling"]


# --- andere koppelingen blijven zoals ze waren ----------------------------------------------------------------------


def test_een_koppeling_zonder_skdb_kant_krijgt_geen_vlag_of_telling():
    _hu()
    tweede = pd.DataFrame(
        {"STUDIEJAAR": 2025, "INSTELLINGSCODE_ACTUEEL": ["25DW"], "OPLEIDINGSCODE_ACTUEEL": [30020], "AANTAL": 1}
    )
    store.put(_DUO2, tweede, KeyMeta(bron="duo", dataset="p02ho1ejrs", resource=0, periodekolom="STUDIEJAAR"))
    uit = _koppel(_DUO2, _DUO)
    assert koppel.PER_GRAAD not in uit
    assert koppel.ONZEKER not in store.get(uit["data_key"]).columns


def test_een_koppeling_op_alleen_croho_krijgt_geen_vlag_of_telling():
    _hu()
    store.put(_SKDB, store.get(_SKDB).drop(columns="brin"), _SKDB_META)
    uit = _koppel(sleutels=["croho"])
    assert koppel.PER_GRAAD not in uit
    assert koppel.ONZEKER not in store.get(uit["data_key"]).columns


def test_een_skdb_tabel_zonder_nse_cijfers_krijgt_geen_vlag():
    _hu()
    store.put(_SKDB, store.get(_SKDB).drop(columns=["nse_oordeel", "nse_respondenten"]), _SKDB_META)
    uit = _koppel()
    assert koppel.ONZEKER not in store.get(uit["data_key"]).columns
    assert "onzeker" not in json.dumps(uit["toelichting"], ensure_ascii=False)
    assert uit[koppel.PER_GRAAD] == {"bachelor": 1, "master": 29, "associate degree": 1}
