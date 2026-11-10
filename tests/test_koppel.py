"""koppel_data: de code koppelt twee tabellen, niet een script van het model (#988, reaudit A02/A03).

Een koppeling in run_analysis verloor rijen: `pivot_table` met `dropna=True`, een filter op `nse_oordeel.notna()` vóór
de koppeling, `how="left"` vanuit de verkeerde kant. Hier staan de twee casussen uit de reaudit als vaste fixture:
HU (N09: 100 SKDB-codes, 70 DUO-codes, samen 101) en ICT 30020 (N07: 14 instellingen, Avans met NSE maar zonder
DUO-rij, Capabel zonder oordeel). Er staat geen data van LCSK in de repo: de getallen zijn verzonnen, de vorm niet.
"""

import json

import pandas as pd
import pytest
from onderwijsbronnen import skdb
from onderwijsbronnen.skdb import proefbestand

import tools
from data import instellingen
from tools import herlaad, koppel, relaties, snippet, store, studiekeuze
from tools.analysis import run_analysis
from tools.csv_export import export_key, naar_csv
from tools.outcome import outcome
from tools.query import query_data
from tools.schemas import TOOL_KOPPEL_DATA
from tools.store import KeyMeta

_SKDB = "skdb:opleidingen:proef988"
_DUO = "duo:p01hoinges:0"
_SKDB_META = KeyMeta(bron="skdb", dataset="skdb:studiekeuzedatabase")
_DUO_META = KeyMeta(bron="duo", dataset="p01hoinges", resource=0)


@pytest.fixture(autouse=True)
def geen_register(monkeypatch):
    monkeypatch.setattr(instellingen, "get_all", lambda: [])


def _koppel(data_key=_SKDB, andere_key=_DUO, sleutels=("croho",), **extra) -> dict:
    uit, _ = tools.dispatch(
        TOOL_KOPPEL_DATA, {"data_key": data_key, "andere_key": andere_key, "sleutels": list(sleutels), **extra}
    )
    return json.loads(uit)


# --- Casus HU (N09): 100 SKDB-codes, 70 DUO-codes, vereniging 101 --------------------------------------------------

_ZONDER_SCORE = [39410, 40045, 49401]
_GEDEELD = [30020 + 10 * i for i in range(69)]
_ALLEEN_SKDB = [*_ZONDER_SCORE, *(50000 + i for i in range(28))]
_ALLEEN_DUO = [35999]
_DUO_SOM = 6388


def _hu() -> None:
    skdb_codes = [*_GEDEELD, *_ALLEEN_SKDB]
    score = [None if c in _ZONDER_SCORE else 3.5 for c in skdb_codes]
    skdb_df = pd.DataFrame({"brin": "25DW", "croho": skdb_codes, "nse_oordeel": score})
    duo_codes = [*_GEDEELD, *_ALLEEN_DUO]
    aantallen = [90] * 69 + [_DUO_SOM - 90 * 69]
    # Een opleidingscode die als getal met lege cellen is gelezen: 30020.0 is dezelfde code als 30020.
    duo_df = pd.DataFrame(
        {
            "INSTELLINGSCODE_ACTUEEL": "25DW",
            "OPLEIDINGSCODE_ACTUEEL": [float(c) for c in duo_codes],
            "AANTAL": aantallen,
        }
    )
    store.put(_SKDB, skdb_df, _SKDB_META)
    store.put(_DUO, duo_df, _DUO_META)


def test_hu_elke_code_van_beide_kanten_komt_voor():
    _hu()
    uit = _koppel()
    df = store.get(uit["data_key"])
    assert df["croho"].nunique() == 101
    assert len(df) == 101
    assert uit["uniek"] == {"SKDB": 100, "DUO": 70, "totaal": 101}
    assert uit["telling"] == {"beide": 69, "alleen SKDB": 31, "alleen DUO": 1}


def test_hu_codes_zonder_score_staan_erin_met_lege_score_en_alleen_skdb():
    _hu()
    df = store.get(_koppel()["data_key"]).set_index("croho")
    for code in map(str, _ZONDER_SCORE):
        assert pd.isna(df.loc[code, "nse_oordeel"])
        assert pd.isna(df.loc[code, "AANTAL"])  # leeg, geen 0
        assert df.loc[code, "koppelstatus"] == "alleen SKDB"


def test_hu_de_som_van_de_duo_kolom_blijft_gelijk():
    _hu()
    df = store.get(_koppel()["data_key"])
    assert df["AANTAL"].sum() == _DUO_SOM
    assert not (df["AANTAL"] == 0).any()


def test_een_rij_zonder_match_is_leeg_in_het_toolresultaat_nooit_0():
    _hu()
    uit = _koppel()
    rij = next(r for r in uit["rijen"] if r["croho"] == "35999")
    assert rij["koppelstatus"] == "alleen DUO"
    assert rij["nse_oordeel"] is None and rij["AANTAL"] == _DUO_SOM - 90 * 69


# --- Casus ICT 30020 (N07): 14 instellingen ------------------------------------------------------------------------

_INSTELLINGEN = ["21PD", "25DW", "28DN", "30GB", "00IC", "01OE", "02GA", "03EP", "09BM", "21RI", "22OJ", "27UM"]
_AVANS, _CAPABEL, _ZONDER_OORDEEL = "07GR", "30HC", "28DN"


def _ict() -> None:
    skdb_brins = [*_INSTELLINGEN, _AVANS]
    oordeel = [None if b == _ZONDER_OORDEEL else 3.4 for b in skdb_brins]
    skdb_df = pd.DataFrame({"brin": skdb_brins, "croho": 30020, "nse_oordeel": oordeel})
    duo_brins = [*_INSTELLINGEN, _CAPABEL]
    duo_df = pd.DataFrame(
        {
            "INSTELLINGSCODE_ACTUEEL": duo_brins,
            "OPLEIDINGSCODE_ACTUEEL": 30020.0,
            "AANTAL": range(10, 10 + len(duo_brins)),
        }
    )
    store.put(_SKDB, skdb_df, _SKDB_META)
    store.put(_DUO, duo_df, _DUO_META)


def test_ict_veertien_instellingen_met_status_en_toelichting():
    _ict()
    uit = _koppel(sleutels=["brin", "croho"])
    df = store.get(uit["data_key"]).set_index("brin")
    assert df.index.nunique() == 14
    assert df.loc[_AVANS, "koppelstatus"] == "alleen SKDB" and pd.isna(df.loc[_AVANS, "AANTAL"])
    assert df.loc[_CAPABEL, "koppelstatus"] == "alleen DUO" and pd.isna(df.loc[_CAPABEL, "nse_oordeel"])
    assert set(uit["toelichting"]) == {"beide", "alleen SKDB", "alleen DUO"}
    for status in ("alleen SKDB", "alleen DUO"):
        assert "andere bron" in uit["toelichting"][status] and "afbakening" in uit["toelichting"][status]
    assert uit["kolommen"] == {
        "SKDB": {"brin": "brin", "croho": "croho"},
        "DUO": {"brin": "INSTELLINGSCODE_ACTUEEL", "croho": "OPLEIDINGSCODE_ACTUEEL"},
    }


def test_een_groep_zonder_score_blijft_staan():
    """Een filter op nse_oordeel.notna() vóór de koppeling verloor deze instelling; hier blijft ze, met haar aantal."""
    _ict()
    df = store.get(_koppel(sleutels=["brin", "croho"])["data_key"]).set_index("brin")
    assert df.loc[_ZONDER_OORDEEL, "koppelstatus"] == "beide"
    assert pd.isna(df.loc[_ZONDER_OORDEEL, "nse_oordeel"]) and df.loc[_ZONDER_OORDEEL, "AANTAL"] > 0


def test_de_kant_van_de_vraag_maakt_niet_uit():
    """Een outer join: met DUO als eerste tabel dezelfde rijen, de statussen gespiegeld."""
    _ict()
    eerst = store.get(_koppel(sleutels=["brin", "croho"])["data_key"])
    omgekeerd = store.get(_koppel(_DUO, _SKDB, sleutels=["brin", "croho"])["data_key"])
    assert sorted(eerst["brin"]) == sorted(omgekeerd["brin"])
    assert omgekeerd.set_index("brin").loc[_AVANS, "koppelstatus"] == "alleen SKDB"


# --- Sleutels, kolommen en meldingen ---------------------------------------------------------------------------------


def test_een_rij_met_een_lege_sleutel_blijft_met_haar_eigen_status():
    store.put(_SKDB, pd.DataFrame({"brin": ["25DW", None], "x": [1, 2]}), _SKDB_META)
    store.put(_DUO, pd.DataFrame({"INSTELLINGSCODE": ["25DW", None], "AANTAL": [5, 7]}), _DUO_META)
    uit = _koppel(sleutels=["brin"])
    df = store.get(uit["data_key"])
    assert len(df) == 3  # pd.merge koppelt NaN aan NaN; hier niet
    assert sorted(df["koppelstatus"]) == ["alleen DUO", "alleen SKDB", "beide"]
    assert uit["zonder_sleutel"] == {"SKDB": 1, "DUO": 1}
    assert "lege of onleesbare sleutel" in uit["waarschuwing"]


def test_een_dubbelzinnige_kolom_geeft_de_kandidaten_en_laat_niets_achter():
    store.put(_SKDB, pd.DataFrame({"brin": ["25DW"]}), _SKDB_META)
    duo_df = pd.DataFrame({"INSTELLINGSCODE": ["25DW"], "INSTELLINGSCODE_ACTUEEL": ["25DW"], "AANTAL": [5]})
    store.put(_DUO, duo_df, _DUO_META)
    voor = store.list_keys()
    uit = _koppel(sleutels=["brin"])
    assert "data_key" not in uit
    assert "INSTELLINGSCODE" in uit["melding"] and "kolommen_rechts" in uit["melding"]
    assert uit["kandidaten"]["DUO"]["brin"] == ["INSTELLINGSCODE", "INSTELLINGSCODE_ACTUEEL"]
    assert store.list_keys() == voor
    gekozen = _koppel(sleutels=["brin"], kolommen_rechts={"brin": "INSTELLINGSCODE_ACTUEEL"})
    assert gekozen["kolommen"]["DUO"] == {"brin": "INSTELLINGSCODE_ACTUEEL"}


def test_een_kolom_buiten_de_kandidaten_wordt_niet_gekozen():
    store.put(_SKDB, pd.DataFrame({"brin": ["25DW"]}), _SKDB_META)
    store.put(_DUO, pd.DataFrame({"INSTELLINGSCODE": ["25DW"], "AANTAL": [5]}), _DUO_META)
    uit = _koppel(sleutels=["brin"], kolommen_rechts={"brin": "AANTAL"})
    assert "AANTAL" in uit["melding"] and "INSTELLINGSCODE" in uit["melding"]


def test_een_sleutel_die_een_tabel_niet_heeft_geeft_een_melding():
    store.put(_SKDB, pd.DataFrame({"brin": ["25DW"], "croho": [30020]}), _SKDB_META)
    store.put(_DUO, pd.DataFrame({"INSTELLINGSCODE": ["25DW"], "AANTAL": [5]}), _DUO_META)
    voor = store.list_keys()
    uit = _koppel(sleutels=["brin", "croho"])
    assert "DUO heeft geen kolom met sleutel croho" in uit["melding"]
    assert store.list_keys() == voor


@pytest.mark.parametrize("sleutels", [[], ["postcode"], [1]])
def test_onbekende_of_lege_sleutels_geven_een_melding(sleutels):
    _hu()
    uit, _ = tools.dispatch(TOOL_KOPPEL_DATA, {"data_key": _SKDB, "andere_key": _DUO, "sleutels": sleutels})
    assert "melding" in json.loads(uit)


@pytest.mark.parametrize("welke", ["data_key", "andere_key"])
def test_een_onbekende_key_geeft_de_vaste_fout(welke):
    _hu()
    args = {"data_key": _SKDB, "andere_key": _DUO, "sleutels": ["croho"], welke: "duo:bestaat_niet:0"}
    uit, _ = tools.dispatch(TOOL_KOPPEL_DATA, args)
    assert uit.startswith("Fout (onbekende_data_key)")
    assert outcome(TOOL_KOPPEL_DATA, uit)["status"] == "error"


def test_de_andere_key_wordt_net_als_data_key_opgezocht():
    _hu()
    assert _koppel(andere_key="DUO:P01HOINGES:0")["telling"]["beide"] == 69


def test_een_tabel_met_zichzelf_koppelen_is_een_melding():
    _hu()
    assert "verschillende" in _koppel(andere_key=_SKDB)["melding"]


def test_kolomnamen_die_botsen_krijgen_het_bronlabel_ervoor():
    store.put(_SKDB, pd.DataFrame({"brin": ["25DW"], "naam": ["HU"]}), _SKDB_META)
    store.put(_DUO, pd.DataFrame({"INSTELLINGSCODE": ["25DW"], "naam": ["Hogeschool Utrecht"]}), _DUO_META)
    df = store.get(_koppel(sleutels=["brin"])["data_key"])
    assert list(df.columns) == ["brin", "koppelstatus", "SKDB_brin", "SKDB_naam", "INSTELLINGSCODE", "DUO_naam"]


def test_twee_tabellen_van_dezelfde_bron_heten_naar_hun_key():
    store.put("duo:a:0", pd.DataFrame({"INSTELLINGSCODE": ["25DW"]}), KeyMeta(bron="duo", dataset="a"))
    store.put("duo:b:0", pd.DataFrame({"INSTELLINGSCODE": ["21PD"]}), KeyMeta(bron="duo", dataset="b"))
    uit = _koppel("duo:a:0", "duo:b:0", sleutels=["brin"])
    assert uit["telling"] == {"alleen duo:a:0": 1, "alleen duo:b:0": 1}


# --- Korrel ----------------------------------------------------------------------------------------------------------


def test_one_to_one_zonder_korrelwaarschuwing():
    _ict()
    uit = _koppel(sleutels=["brin", "croho"])
    assert uit["korrel"] == {"SKDB": "one", "DUO": "one", "koppeling": "one_to_one"}
    assert "dataset_profiel" not in uit.get("waarschuwing", "")


def test_veel_op_veel_geeft_een_waarschuwing_over_herhaalde_waarden():
    """DUO per opleiding en vorm tegen SKDB per opleiding en vorm, op alleen croho: elke rij herhaalt de andere kant."""
    store.put(_SKDB, pd.DataFrame({"croho": [30020, 30020], "vorm": ["voltijd", "deeltijd"]}), _SKDB_META)
    duo_df = pd.DataFrame({"OPLEIDINGSCODE_ACTUEEL": [30020, 30020], "AANTAL": [100, 20]})
    store.put(_DUO, duo_df, _DUO_META)
    uit = _koppel()
    assert uit["korrel"]["koppeling"] == "many_to_many"
    assert "herhaald" in uit["waarschuwing"] and "dataset_profiel" in uit["waarschuwing"]
    assert len(store.get(uit["data_key"])) == 4


# --- Omvang: eerst tellen, dan koppelen (de join draait in het serverproces, niet in de sandbox) -------------------


def _veel_op_veel(n: int) -> None:
    """n rijen per kant, allemaal dezelfde brin: de outer join is een kruisproduct van n x n rijen."""
    store.put(_SKDB, pd.DataFrame({"brin": ["25DW"] * n, "x": range(n)}), _SKDB_META)
    store.put(_DUO, pd.DataFrame({"INSTELLINGSCODE": ["25DW"] * n, "AANTAL": range(n)}), _DUO_META)


def test_een_te_grote_koppeling_gaat_niet_door_en_laat_niets_achter():
    _veel_op_veel(1500)
    voor = store.list_keys()
    uit = _koppel(sleutels=["brin"])
    assert "data_key" not in uit and "rijen" not in uit
    assert uit["verwachte_rijen"] == 2_250_000 and uit["korrel"] == "many_to_many"
    assert str(koppel.MAX_RIJEN) in uit["melding"] and "query_data" in uit["melding"]
    assert store.list_keys() == voor


def _sleutelloos() -> None:
    store.put(_SKDB, pd.DataFrame({"brin": ["25DW", None, "25DW"], "x": [1, 2, 3]}), _SKDB_META)
    store.put(_DUO, pd.DataFrame({"INSTELLINGSCODE": ["25DW", None, "21PD"], "AANTAL": [5, 7, 9]}), _DUO_META)


@pytest.mark.parametrize(
    ("vul", "sleutels"),
    [(_hu, ["croho"]), (_ict, ["brin", "croho"]), (lambda: _veel_op_veel(4), ["brin"]), (_sleutelloos, ["brin"])],
)
def test_de_telling_vooraf_is_precies_het_aantal_rijen(monkeypatch, vul, sleutels):
    """De grens telt wat de join zou geven: precies op de grens gaat hij door, één rij eronder niet."""
    vul()
    rijen = len(store.get(_koppel(sleutels=sleutels)["data_key"]))
    monkeypatch.setattr(koppel, "MAX_RIJEN", rijen)
    assert "data_key" in _koppel(sleutels=sleutels)
    monkeypatch.setattr(koppel, "MAX_RIJEN", rijen - 1)
    assert _koppel(sleutels=sleutels)["verwachte_rijen"] == rijen


def _breed(rijen: int, kolommen: int) -> None:
    """Twee tabellen van `rijen` rijen op één brin, elk met `kolommen` tekstkolommen: onder de rijgrens, toch breed."""
    df = pd.DataFrame({"brin": ["25DW"] * rijen, **{f"c{i}": [f"tekst {i}"] * rijen for i in range(kolommen)}})
    store.put(_SKDB, df, _SKDB_META)
    store.put(_DUO, df.copy(), _DUO_META)


def test_een_te_brede_koppeling_onder_de_rijgrens_gaat_niet_door_en_laat_niets_achter():
    """#1011: 447 x 447 = 199.809 rijen (onder MAX_RIJEN) met 40 tekstkolommen per kant; weigeren vóór de join."""
    _breed(447, 40)
    voor = store.list_keys()
    uit = _koppel(sleutels=["brin"])
    assert "data_key" not in uit and "rijen" not in uit
    assert uit["verwachte_rijen"] == 199_809 < koppel.MAX_RIJEN
    assert uit["korrel"] == "many_to_many"
    # brin één keer, per kant de eigen brin en c0..c39, plus koppelstatus
    assert uit["verwachte_cellen"] == 199_809 * (1 + 41 + 41 + 1) > koppel.MAX_CELLEN
    melding = uit["melding"]
    assert str(koppel.MAX_CELLEN) in melding and str(uit["verwachte_cellen"]) in melding
    assert "niets gekoppeld" in melding and "query_data" in melding and "meer sleutels" in melding
    assert store.list_keys() == voor


@pytest.mark.parametrize(
    ("vul", "sleutels"),
    [
        (_hu, ["croho"]),
        (_ict, ["brin", "croho"]),
        (lambda: _veel_op_veel(4), ["brin"]),
        (_sleutelloos, ["brin"]),
        (lambda: _breed(5, 3), ["brin"]),
    ],
)
def test_de_celtelling_vooraf_is_precies_rijen_maal_kolommen(monkeypatch, vul, sleutels):
    """De celgrens telt wat de join zou geven: precies op de grens gaat hij door, één cel eronder niet."""
    vul()
    cellen = store.get(_koppel(sleutels=sleutels)["data_key"]).size
    monkeypatch.setattr(koppel, "MAX_CELLEN", cellen)
    assert "data_key" in _koppel(sleutels=sleutels)
    monkeypatch.setattr(koppel, "MAX_CELLEN", cellen - 1)
    uit = _koppel(sleutels=sleutels)
    assert "data_key" not in uit and uit["verwachte_cellen"] == cellen


def test_boven_beide_grenzen_gaat_de_rijmelding_voor():
    """Eén melding: bij een kruisproduct boven MAX_RIJEN helpen minder kolommen niet, dus geen celmelding."""
    _veel_op_veel(1500)
    uit = _koppel(sleutels=["brin"])
    assert uit["verwachte_rijen"] > koppel.MAX_RIJEN and uit["verwachte_cellen"] > koppel.MAX_CELLEN
    assert str(koppel.MAX_RIJEN) in uit["melding"]
    assert "cellen" not in uit["melding"] and str(koppel.MAX_CELLEN) not in uit["melding"]


def test_een_koppeling_ketenen_kiest_de_genormaliseerde_sleutelkolom():
    """Een koppeling heeft brin twee keer (de eigen kolom en vooraan de genormaliseerde): geen melding bij ketenen."""
    _ict()
    eerste = _koppel(sleutels=["brin", "croho"])["data_key"]
    store.put(
        "duo:derde:0",
        pd.DataFrame({"INSTELLINGSCODE": ["25DW"], "PERSONEEL": [80]}),
        KeyMeta(bron="duo", dataset="derde"),
    )
    uit = _koppel(eerste, "duo:derde:0", sleutels=["brin"])
    assert "melding" not in uit
    assert uit["kolommen"]["SKDB"] == {"brin": "brin"}
    assert uit["telling"]["beide"] == 1
    df = store.get(uit["data_key"])
    assert df.columns.is_unique  # brin werd SKDB_brin, maar die was er al: SKDB_SKDB_brin
    assert {"SKDB_brin", "SKDB_SKDB_brin", "SKDB_koppelstatus", "koppelstatus"} <= set(df.columns)


def test_een_ruwe_tabel_met_een_kolom_brin_blijft_dubbelzinnig():
    """De voorkeur geldt alleen voor een koppeling; in een gewone tabel kiest de code geen kolom zelf."""
    store.put(_SKDB, pd.DataFrame({"brin": ["25DW"], "INSTELLINGSCODE": ["25DW"]}), _SKDB_META)
    store.put(_DUO, pd.DataFrame({"INSTELLINGSCODE": ["25DW"], "AANTAL": [5]}), _DUO_META)
    assert "kolommen_links" in _koppel(sleutels=["brin"])["melding"]


def test_een_naamsleutel_neemt_de_naamwaarschuwing_over():
    store.put(_SKDB, pd.DataFrame({"INSTELLINGSNAAM": ["Hogeschool Utrecht"]}), _SKDB_META)
    store.put(_DUO, pd.DataFrame({"INSTELLINGSNAAM_ACTUEEL": ["hogeschool utrecht "], "AANTAL": [5]}), _DUO_META)
    uit = _koppel(sleutels=["instellingsnaam"])
    assert uit["telling"] == {"beide": 1}
    assert relaties.NAAMWAARSCHUWING in uit["waarschuwing"]


# --- De nieuwe key ---------------------------------------------------------------------------------------------------


def test_de_key_is_deterministisch():
    _hu()
    assert _koppel()["data_key"] == _koppel()["data_key"]
    assert _koppel()["data_key"].startswith("koppel:")


def test_andere_invoer_geeft_een_andere_key():
    """De key hangt aan de inhoud van beide tabellen, niet alleen aan hun keys."""
    _hu()
    eerst = _koppel()["data_key"]
    store.put(_DUO, store.get(_DUO).assign(AANTAL=1), _DUO_META)
    assert _koppel()["data_key"] != eerst


def test_de_key_is_een_afgeleide_van_beide_tabellen():
    _hu()
    known = store.meta(_koppel()["data_key"])
    assert known is not None
    assert known.afgeleid_van == _SKDB and known.gelezen == (_SKDB, _DUO)
    assert (
        known.stap is not None
        and known.stap.startswith(koppel.STAP)
        and "croho" in known.stap
        and "one_to_one" in known.stap
    )
    assert known.volledig


def test_onvolledig_als_een_van_beide_tabellen_afgekapt_is():
    _hu()
    store.put(_DUO, store.get(_DUO), KeyMeta(bron="duo", dataset="p01hoinges", resource=0, volledig=False))
    uit = _koppel()
    assert not store.volledig(uit["data_key"])
    assert store.ONVOLLEDIG in uit["waarschuwing"]


def test_query_data_en_run_analysis_werken_op_de_nieuwe_key():
    _hu()
    key = _koppel()["data_key"]
    gefilterd = json.loads(query_data(data_key=key, filters={"koppelstatus": "alleen SKDB"}))
    assert len(gefilterd["rijen"]) == 31
    analyse = run_analysis("result = int(df['AANTAL'].sum())", data_key=key)
    assert isinstance(analyse, str) and str(_DUO_SOM) in analyse


def test_veel_rijen_worden_begrensd_zoals_bij_run_analysis():
    store.put(_SKDB, pd.DataFrame({"croho": range(1000, 3000), "x": 1}), _SKDB_META)
    store.put(_DUO, pd.DataFrame({"OPLEIDINGSCODE_ACTUEEL": range(1000, 3000), "y": 2}), _DUO_META)
    uit = _koppel()
    assert len(uit["rijen"]) < 2000 and uit["totaal_rijen"] == 2000
    assert "query_data" in uit["waarschuwing"]


# --- Herkomst, CSV, herladen en snippet ----------------------------------------------------------------------------


@pytest.fixture
def proefexport(monkeypatch):
    monkeypatch.setattr(skdb, "haal_op", lambda *a, **k: proefbestand.standaard())
    monkeypatch.setattr(
        instellingen,
        "instellingsprofiel",
        lambda naam: (
            {"naam": "Hogeschool Utrecht", "sector": "hbo", "instellingscode": "25DW"} if naam == "HU" else None
        ),
    )
    studiekeuze._export.cache_clear()
    yield
    studiekeuze._export.cache_clear()


def _skdb_en_duo() -> tuple[str, str]:
    skdb_key = json.loads(studiekeuze.get_studiekeuze(instelling="HU", opleiding="ICT", vorm="voltijd"))["data_key"]
    duo_df = pd.DataFrame(
        {"INSTELLINGSCODE_ACTUEEL": ["25DW", "21PD"], "OPLEIDINGSCODE_ACTUEEL": [30020.0, 30020.0], "AANTAL": [120, 80]}
    )
    store.put(_DUO, duo_df, _DUO_META)
    return skdb_key, _DUO


@pytest.mark.parametrize("volgorde", ["skdb_eerst", "duo_eerst"])
def test_herkomst_en_csv_noemen_lcsk_en_duo(proefexport, volgorde):
    skdb_key, duo_key = _skdb_en_duo()
    eerst, dan = (skdb_key, duo_key) if volgorde == "skdb_eerst" else (duo_key, skdb_key)
    result, _ = tools.dispatch(TOOL_KOPPEL_DATA, {"data_key": eerst, "andere_key": dan, "sleutels": ["brin", "croho"]})
    key = json.loads(result)["data_key"]

    regels = store.herkomst(key)
    assert sum(skdb.VERPLICHTE_ZIN in r for r in regels) == 1
    assert "bron: DUO, dataset p01hoinges, resource 0" in regels
    assert any(r.startswith(f"selectie: {koppel.STAP}") for r in regels)

    csv = naar_csv(key)
    assert csv is not None
    kop = [r for r in csv.splitlines() if r.startswith("# ")]
    assert any(skdb.VERPLICHTE_ZIN in r for r in kop) and any("dataset p01hoinges" in r for r in kop)
    assert "koppelstatus" in next(r for r in csv.splitlines() if not r.startswith("# "))
    assert export_key(TOOL_KOPPEL_DATA, result) == key


def test_een_koppeling_komt_na_een_herstart_niet_vanzelf_terug(proefexport):
    skdb_key, duo_key = _skdb_en_duo()
    args = {"data_key": skdb_key, "andere_key": duo_key, "sleutels": ["brin", "croho"]}
    result, _ = tools.dispatch(TOOL_KOPPEL_DATA, args)
    key = json.loads(result)["data_key"]
    recept = herlaad.recept(key, {"name": TOOL_KOPPEL_DATA, "arguments": args})
    assert recept is not None and recept["herlaadbaar"] is False and recept["stap"].startswith(koppel.STAP)
    store.clear()
    uitkomst = herlaad.herlaad(key, recept)
    assert not uitkomst.gelukt and "niet automatisch opnieuw uitgevoerd" in uitkomst.melding


def test_een_snippet_op_de_koppeling_crasht_niet():
    _ict()
    key = _koppel(sleutels=["brin", "croho"])["data_key"]
    regels = snippet._laadregels(key)
    assert any("pd.DataFrame(" in r for r in regels)
    assert snippet.generate(TOOL_KOPPEL_DATA, {"data_key": _SKDB}) is None


def test_de_tool_staat_in_schemas_labels_en_handlers():
    assert TOOL_KOPPEL_DATA in {s["function"]["name"] for s in tools.SCHEMAS}
    assert TOOL_KOPPEL_DATA in tools.LABELS and TOOL_KOPPEL_DATA in tools._HANDLERS


def test_de_rijen_tellen_als_bewijs_en_de_stap_als_geslaagd():
    """Bronwaarden, geen eigen berekening: de rijen zijn meetwaarden zoals bij query_data (agent/meetwaarden.py)."""
    from agent.meetwaarden import meetwaarden

    _hu()
    result, _ = tools.dispatch(TOOL_KOPPEL_DATA, {"data_key": _SKDB, "andere_key": _DUO, "sleutels": ["croho"]})
    assert outcome(TOOL_KOPPEL_DATA, result) == {}
    gemeten = {c for w in meetwaarden(result, TOOL_KOPPEL_DATA) if w.maat == "AANTAL" for c in w.cijfers}
    assert str(_DUO_SOM - 90 * 69) in gemeten


def test_een_onbekende_key_gaat_voor_een_ongeldige_sleutel():
    """Dezelfde foutcode als elke tool met een data_key (tests/test_tool_keten_contract.py)."""
    uit, _ = tools.dispatch(TOOL_KOPPEL_DATA, {"data_key": "duo:bestaat_niet", "andere_key": _DUO, "sleutels": "x"})
    assert uit.startswith("Fout (onbekende_data_key)")
