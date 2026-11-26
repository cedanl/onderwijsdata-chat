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


def _rijen(per_graad: dict) -> dict[str, int]:
    """Alleen het aantal rijen per graad, zonder de score-tellingen (#1274)."""
    return {g: deel["rijen"] for g, deel in per_graad.items()}


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
    assert _rijen(uit[koppel.PER_GRAAD]) == {"bachelor": 1, "master": 29, "associate degree": 1}
    df = store.get(uit["data_key"])
    direct = df.loc[df["koppelstatus"] == _ALLEEN, "graad"].str.lower().value_counts().to_dict()
    assert _rijen(uit[koppel.PER_GRAAD]) == direct
    assert sum(_rijen(uit[koppel.PER_GRAAD]).values()) == uit["telling"][_ALLEEN] == 31


def test_een_onbekende_of_lege_graad_telt_onder_een_eigen_sleutel():
    _hu([("60000", "Master"), ("60001", None), ("60002", ""), ("60003", "Doctoraal"), ("80001", "ad")])
    uit = _koppel()
    assert _rijen(uit[koppel.PER_GRAAD]) == {"master": 1, "associate degree": 1, "doctoraal": 1, koppel.GEEN_GRAAD: 2}
    assert sum(_rijen(uit[koppel.PER_GRAAD]).values()) == uit["telling"][_ALLEEN]


def test_een_botsende_graadkolom_telt_de_skdb_kant():
    """Heeft DUO zelf een kolom graad, dan heet die van de SKDB SKDB_graad; de telling leest de SKDB-kant."""
    _hu()
    store.put(_DUO, store.get(_DUO).assign(graad="wo"), _DUO_META)
    uit = _koppel()
    assert _rijen(uit[koppel.PER_GRAAD]) == {"bachelor": 1, "master": 29, "associate degree": 1}


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


# --- alleen croho bij één instelling (#1273) --------------------------------------------------------------------------


@pytest.mark.parametrize("sleutels", [["croho"], ["croho", "brin"]])
def test_de_hu_koppeling_geeft_bij_beide_sleutelvormen_de_vlag_en_de_telling(sleutels):
    """Beide tabellen zijn al tot HU (25DW) begrensd: de sleutelnamen veranderen niets aan de waarborgen."""
    _hu()
    uit = _koppel(sleutels=sleutels)
    assert _rijen(uit[koppel.PER_GRAAD]) == {"bachelor": 1, "master": 29, "associate degree": 1}
    vlaggen = _vlaggen(uit)
    assert vlaggen["80166"] is True  # 28 respondenten
    assert {c: vlaggen[c] for c in _VERWACHT} == _VERWACHT
    for status in ("beide", _ALLEEN):
        assert "onzeker: true" in uit["toelichting"][status]


def test_alleen_croho_en_brin_plus_croho_geven_dezelfde_kolom_onzeker():
    _hu()
    beide = store.get(_koppel(sleutels=["brin", "croho"])["data_key"])
    alleen = store.get(_koppel(sleutels=["croho"])["data_key"])
    assert koppel.ONZEKER in alleen.columns
    assert list(alleen.columns).index(koppel.ONZEKER) == list(alleen.columns).index("koppelstatus") + 1
    assert beide.set_index("croho")[koppel.ONZEKER].to_dict() == alleen.set_index("croho")[koppel.ONZEKER].to_dict()
    assert alleen.set_index("croho").loc["80166", koppel.ONZEKER] is True


def test_alleen_croho_vraagt_rio_niet_om_opvolgers(monkeypatch):
    """De opvolgers van #1060 vragen RIO per brin + CROHO: bij alleen croho blijven ze uit."""
    _hu()
    gevraagd: list[str] = []
    monkeypatch.setattr(opvolger, "onderwijslicenties", lambda brin, peildatum=None: gevraagd.append(brin) or ())
    uit = _koppel(sleutels=["croho"])
    assert gevraagd == []
    assert opvolger.KOPPELREDEN not in store.get(uit["data_key"]).columns


# --- andere koppelingen blijven zoals ze waren ----------------------------------------------------------------------


def test_een_koppeling_zonder_skdb_kant_krijgt_geen_vlag_of_telling():
    _hu()
    tweede = pd.DataFrame(
        {"STUDIEJAAR": 2025, "INSTELLINGSCODE_ACTUEEL": ["25DW"], "OPLEIDINGSCODE_ACTUEEL": [30020], "AANTAL": 1}
    )
    store.put(_DUO2, tweede, KeyMeta(bron="duo", dataset="p02ho1ejrs", resource=0, periodekolom="STUDIEJAAR"))
    uit = _koppel(_DUO2, _DUO)
    assert koppel.PER_GRAAD not in uit and koppel.GEKOPPELD_PER_GRAAD not in uit and koppel.ALLEEN_DUO not in uit
    assert koppel.ONZEKER not in store.get(uit["data_key"]).columns


def _twee_brins(kant: str) -> None:
    """Een rij van een tweede instelling (21PK) aan één kant, met een CROHO die geen DUO-rij heeft."""
    if kant == "skdb":
        rij = {"brin": "21PK", "croho": "34000", "graad": "Master", "nse_oordeel": 3.5, "nse_respondenten": 12}
        store.put(_SKDB, pd.concat([store.get(_SKDB), pd.DataFrame([rij])], ignore_index=True), _SKDB_META)
    else:
        rij = {"STUDIEJAAR": 2025, "INSTELLINGSCODE_ACTUEEL": "21PK", "OPLEIDINGSCODE_ACTUEEL": 34000.0}
        store.put(_DUO, pd.concat([store.get(_DUO), pd.DataFrame([rij])], ignore_index=True), _DUO_META)


@pytest.mark.parametrize("kant", ["skdb", "duo"])
def test_een_koppeling_op_alleen_croho_over_meer_instellingen_krijgt_geen_vlag_of_telling(kant):
    """Zonder brin als sleutel kan een CROHO van twee instellingen op één rij vallen: dan geen waarborgen (#1273)."""
    _hu()
    _twee_brins(kant)
    uit = _koppel(sleutels=["croho"])
    assert koppel.PER_GRAAD not in uit
    assert koppel.ONZEKER not in store.get(uit["data_key"]).columns
    assert "onzeker" not in json.dumps(uit.get("toelichting", {}), ensure_ascii=False)


def test_een_koppeling_op_alleen_croho_zonder_brin_kolom_krijgt_geen_vlag_of_telling():
    """Zonder brin-kolom aan de SKDB-kant is niet aantoonbaar één instelling: zoals vóór #1273."""
    _hu()
    store.put(_SKDB, store.get(_SKDB).drop(columns="brin"), _SKDB_META)
    uit = _koppel(sleutels=["croho"])
    # Koppelen op alleen croho is #1273; tot die er is krijgt zo'n koppeling geen van de velden van #1231 en #1274.
    assert koppel.PER_GRAAD not in uit and koppel.GEKOPPELD_PER_GRAAD not in uit and koppel.ALLEEN_DUO not in uit
    assert koppel.ONZEKER not in store.get(uit["data_key"]).columns


def test_een_koppeling_op_alleen_croho_met_een_lege_brin_krijgt_geen_vlag_of_telling():
    _hu()
    skdb = store.get(_SKDB)
    skdb.loc[0, "brin"] = None
    store.put(_SKDB, skdb, _SKDB_META)
    uit = _koppel(sleutels=["croho"])
    assert koppel.PER_GRAAD not in uit
    assert koppel.ONZEKER not in store.get(uit["data_key"]).columns


def test_een_koppeling_op_alleen_brin_krijgt_geen_vlag_of_telling():
    _hu()
    skdb = store.get(_SKDB).drop_duplicates("brin")
    store.put(_SKDB, skdb, _SKDB_META)
    uit = _koppel(sleutels=["brin"])
    assert koppel.PER_GRAAD not in uit
    assert koppel.ONZEKER not in store.get(uit["data_key"]).columns


def test_een_skdb_tabel_zonder_nse_cijfers_krijgt_geen_vlag():
    _hu()
    store.put(_SKDB, store.get(_SKDB).drop(columns=["nse_oordeel", "nse_respondenten"]), _SKDB_META)
    uit = _koppel()
    assert koppel.ONZEKER not in store.get(uit["data_key"]).columns
    assert "onzeker" not in json.dumps(uit["toelichting"], ensure_ascii=False)
    assert _rijen(uit[koppel.PER_GRAAD]) == {"bachelor": 1, "master": 29, "associate degree": 1}
    # Zonder NSE-cijfer niets om te tellen: per graad alleen het aantal rijen (#1274).
    assert uit[koppel.GEKOPPELD_PER_GRAAD] == {"bachelor": {"rijen": 6}}
    assert uit[koppel.PER_GRAAD]["master"] == {"rijen": 29}


def test_een_eigen_kolom_onzeker_blijft_staan():
    _hu()
    store.put(_SKDB, store.get(_SKDB).assign(onzeker="eigen"), _SKDB_META)
    df = store.get(_koppel()["data_key"])
    assert set(df.loc[df["koppelstatus"] != "alleen DUO", koppel.ONZEKER]) == {"eigen"}


@pytest.mark.parametrize("sleutels", [("brin", "croho"), ("croho",)])
def test_de_celtelling_vooraf_rekent_de_kolom_onzeker_mee(monkeypatch, sleutels):
    """De grens van #1011 telt wat er in de store komt: de koppeling plus de kolom onzeker, ook bij alleen croho."""
    _hu()
    df = store.get(_koppel(sleutels=sleutels)["data_key"])
    assert koppel.ONZEKER in df.columns
    cellen = df.size
    monkeypatch.setattr(koppel, "MAX_CELLEN", cellen)
    assert "data_key" in _koppel(sleutels=sleutels)
    monkeypatch.setattr(koppel, "MAX_CELLEN", cellen - 1)
    assert _koppel(sleutels=sleutels)["verwachte_cellen"] == cellen


# --- alle opleidingen: per graad gekoppeld, met score, en alleen DUO met reden (#1274) ----------------------------


def _hu_alle() -> pd.DataFrame:
    """De vorm van HU in #1274: 69 opleidingen met een DUO-rij (54 bachelor, 15 associate degree), 31 zonder (29 master,
    waarvan 27 met een NSE-score, 1 bachelor, 1 associate degree) en één DUO-rij zonder SKDB-rij (CROHO 80065): 101
    rijen. 80166 heeft 28 respondenten. De aantallen zijn verzonnen."""
    gekoppeld: list[tuple[str, str, int | None, float | None]] = [("80166", "Bachelor", 28, 3.9)]
    gekoppeld += [(f"3{i:04d}", "Bachelor", 40 + i, 3.5) for i in range(50)]
    gekoppeld += [(f"3{i:04d}", "Bachelor", None, None) for i in range(50, 53)]  # drie bachelors zonder NSE-cijfer
    gekoppeld += [(f"8{i:04d}", "Associate degree", 10 if i < 3 else 35, 3.6) for i in range(1, 16)]
    zonder: list[tuple[str, str, int | None, float | None]] = [(f"6{i:04d}", "Master", 50, 3.8) for i in range(27)]
    zonder += [(f"6{i:04d}", "Master", None, None) for i in (27, 28)]
    zonder += [("31000", "Bachelor", None, None), ("80999", "Associate degree", 12, 3.1)]
    skdb = pd.DataFrame(
        [
            {"brin": "25DW", "croho": c, "graad": g, "nse_oordeel": o, "nse_respondenten": n}
            for c, g, n, o in gekoppeld + zonder
        ]
    )
    store.put(_SKDB, skdb, _SKDB_META)
    codes = [float(c) for c, *_ in gekoppeld] + [80065.0]
    duo = pd.DataFrame(
        {
            "STUDIEJAAR": 2025,
            "INSTELLINGSCODE_ACTUEEL": "25DW",
            "OPLEIDINGSCODE_ACTUEEL": codes,
            "AANTAL_INGESCHREVENEN": range(100, 100 + len(codes)),
        }
    )
    store.put(_DUO, duo, _DUO_META)
    return skdb


def test_gekoppeld_per_graad_telt_op_tot_beide():
    """HU: 69 opleidingen met een DUO-rij, 54 bachelor en 15 associate degree, met per graad met_score en onzeker."""
    _hu_alle()
    uit = _koppel()
    per_graad = uit[koppel.GEKOPPELD_PER_GRAAD]
    assert per_graad == {
        "bachelor": {"rijen": 54, "met_score": 51, "onzeker": 1},
        "associate degree": {"rijen": 15, "met_score": 15, "onzeker": 2},
    }
    assert sum(deel["rijen"] for deel in per_graad.values()) == uit["telling"]["beide"] == 69


def test_gekoppeld_per_graad_gelijk_aan_de_tabel_zelf():
    """Dezelfde aantallen als een telling op de bewaarde tabel: de vlag onzeker en een NSE-cijfer per rij."""
    _hu_alle()
    uit = _koppel()
    df = store.get(uit["data_key"])
    beide = df[df["koppelstatus"] == "beide"]
    for graad, deel in uit[koppel.GEKOPPELD_PER_GRAAD].items():
        rijen = beide[beide["graad"].str.lower() == graad]
        assert deel["rijen"] == len(rijen)
        assert deel["met_score"] == int(rijen["nse_oordeel"].notna().sum())
        assert deel["onzeker"] == int((rijen[koppel.ONZEKER] == True).sum())  # noqa: E712


def test_de_opleiding_met_28_respondenten_blijft_in_gekoppeld_per_graad():
    _hu_alle()
    uit = _koppel()
    df = store.get(uit["data_key"])
    rij = df.set_index("croho").loc["80166"]
    assert rij["koppelstatus"] == "beide" and rij[koppel.ONZEKER] is True
    assert uit[koppel.GEKOPPELD_PER_GRAAD]["bachelor"]["onzeker"] == 1


def test_niet_gekoppeld_per_graad_telt_ook_met_score():
    """HU: 29 masters zonder DUO-rij, waarvan 27 met een NSE-score; samen 31 = telling alleen SKDB."""
    _hu_alle()
    uit = _koppel()
    per_graad = uit[koppel.PER_GRAAD]
    assert per_graad["master"] == {"rijen": 29, "met_score": 27, "onzeker": 0}
    assert per_graad["bachelor"] == {"rijen": 1, "met_score": 0, "onzeker": 0}
    assert per_graad["associate degree"] == {"rijen": 1, "met_score": 1, "onzeker": 1}
    assert sum(deel["rijen"] for deel in per_graad.values()) == uit["telling"][_ALLEEN] == 31


def test_alleen_duo_staat_erin_met_een_vaste_reden():
    """HU: één DUO-rij zonder SKDB-rij (CROHO 80065), met een vaste reden; de delen tellen op tot 101 rijen."""
    _hu_alle()
    uit = _koppel()
    alleen_duo = uit[koppel.ALLEEN_DUO]
    assert alleen_duo["rijen"] == uit["telling"]["alleen DUO"] == 1
    assert alleen_duo["opleidingen"] == [{"brin": "25DW", "croho": "80065", "reden": koppel.REDEN_ALLEEN_DUO}]
    assert "alleen in DUO" in koppel.REDEN_ALLEEN_DUO
    delen = (
        sum(d["rijen"] for d in uit[koppel.GEKOPPELD_PER_GRAAD].values())
        + sum(d["rijen"] for d in uit[koppel.PER_GRAAD].values())
        + alleen_duo["rijen"]
    )
    assert delen == sum(uit["telling"].values()) == len(store.get(uit["data_key"])) == 101


def test_alleen_duo_noemt_hooguit_een_maximum_aan_opleidingen(monkeypatch):
    """Een DUO-tabel van alle instellingen geeft duizenden rijen alleen DUO: de lijst is begrensd, het aantal niet."""
    _hu_alle()
    duo = store.get(_DUO)
    extra = pd.DataFrame(
        {
            "STUDIEJAAR": 2025,
            "INSTELLINGSCODE_ACTUEEL": "21PB",
            "OPLEIDINGSCODE_ACTUEEL": [float(50000 + i) for i in range(10)],
            "AANTAL_INGESCHREVENEN": 1,
        }
    )
    store.put(_DUO, pd.concat([duo, extra], ignore_index=True), _DUO_META)
    monkeypatch.setattr(koppel, "MAX_ALLEEN_DUO", 4)
    alleen_duo = _koppel()[koppel.ALLEEN_DUO]
    assert alleen_duo["rijen"] == 11
    assert len(alleen_duo["opleidingen"]) == 4 and alleen_duo["niet_getoond"] == 7


def test_de_kant_van_de_vraag_geeft_dezelfde_tellingen_per_graad():
    _hu_alle()
    links, rechts = _koppel(), _koppel(_DUO, _SKDB)
    for veld in (koppel.GEKOPPELD_PER_GRAAD, koppel.PER_GRAAD, koppel.ALLEEN_DUO):
        assert links[veld] == rechts[veld], veld


def test_de_toelichting_zegt_bij_alle_een_tabel_per_graad():
    """Bij een vraag naar alle opleidingen: een tabel per graad, de niet-gekoppelde rijen met reden, onzeker met label,
    de graad niet vernauwen, tellingen overnemen. Ook de tooltekst zegt het."""
    _hu_alle()
    uit = _koppel()
    beide = uit["toelichting"]["beide"]
    for woord in ("alle opleidingen", "één tabel per graad", koppel.GEKOPPELD_PER_GRAAD, koppel.PER_GRAAD):
        assert woord in beide, woord
    assert koppel.ALLEEN_DUO in beide and "reden" in beide
    assert "onzeker: true" in beide and "laat ze niet weg" in beide
    assert "vernauw de graad niet" in beide and "tel niet zelf" in beide
    assert koppel.ALLEEN_DUO in uit["toelichting"]["alleen DUO"]
    assert "onzeker" not in uit["toelichting"]["alleen DUO"]
    beschrijving = next(t for t in TOOL_SCHEMAS if t["function"]["name"] == TOOL_KOPPEL_DATA)["function"]["description"]
    assert koppel.GEKOPPELD_PER_GRAAD in beschrijving and "tabel per graad" in beschrijving
