"""Citaties, telling, export, herladen en snippet voor get_bestuursfinancien en get_wo_personeel (#956).

Op test gaf een financiënantwoord "Citaties n.v.t., Telling n.v.t., Export n.v.t.": agent/meetwaarden.py kende de
resultaatvorm van de twee tools niet en ze zetten geen tabel in de store. Hier per tool: welke getallen een meetwaarde
zijn, dat een voorbeeldantwoord voor elk getal uit de tool een vastgestelde citatie krijgt, en dat de tabel achter het
resultaat met haar KeyMeta in de store staat, als CSV met inhoudshash te exporteren is, uit haar recept terugkomt en in
de snippet van een volgende stap dezelfde tabel geeft.

Zonder netwerk: dezelfde synthetische verantwoording als tests/test_financien.py en het proefbestand van
`onderwijsbronnen.unl` (tests/test_wo_personeel.py).
"""

import json
from decimal import Decimal

import pandas as pd
import pytest
from onderwijsbronnen import unl
from onderwijsbronnen.unl import proefbestand

from agent.bronvermelding import bronnen_van
from agent.citaties import citaties
from agent.datasetcontext import build_recipe, sources_from_recipe
from agent.meetwaarden import meetwaarden, schrijft
from agent.telling import telling_blok
from core import config
from data import instellingen
from tests.test_financien import _BESTUUR, _DATA, _PROFIELEN
from tests.test_wo_personeel import _profiel
from tools import beschikbaarheid, csv_export, fusies, herlaad, inhoudshash, snippet, store, wo_personeel
from tools import financien as fin
from tools.query import query_data
from tools.schemas import TOOL_GET_BESTUURSFINANCIEN, TOOL_GET_WO_PERSONEEL, TOOL_QUERY_DATA


@pytest.fixture(autouse=True)
def bronnen(monkeypatch):
    monkeypatch.setattr(fin.instellingen, "instellingsprofiel", lambda naam: _PROFIELEN.get(naam.strip().lower()))
    monkeypatch.setattr(fin, "bestuur_van", lambda code: _BESTUUR.get(code))
    monkeypatch.setattr(fin, "_bron", lambda: _DATA)
    monkeypatch.setattr(fusies, "_voorgangers", lambda code, sinds: ())
    monkeypatch.setattr(beschikbaarheid.Config, "APP_ENV", "test")
    monkeypatch.setattr(unl, "haal_op", proefbestand.standaard)
    monkeypatch.setattr(unl.wopi, "haal_op", proefbestand.standaard)
    wo_personeel._wopi.cache_clear()
    yield
    wo_personeel._wopi.cache_clear()


@pytest.fixture
def register_wo(monkeypatch):
    """Het instellingenregister zoals get_wo_personeel het leest (dezelfde functie als de financiën gebruiken)."""
    monkeypatch.setattr(instellingen, "instellingsprofiel", _profiel)


def _meta(key: str) -> store.KeyMeta:
    known = store.meta(key)
    assert known is not None, key
    return known


def _csv(key: str | None) -> str:
    assert key is not None
    tekst = csv_export.naar_csv(key)
    assert tekst is not None, key
    return tekst


def _financien(vraag: str = "ROC Midden Nederland") -> str:
    return fin.get_bestuursfinancien(vraag)


def _wopi(**args) -> str:
    return wo_personeel.get_wo_personeel(**args)


# --- meetwaarden -------------------------------------------------------------------------------------------------


def test_financien_elk_kengetal_van_bestuur_en_sector_is_een_meetwaarde():
    uit = _financien()
    waarden = meetwaarden(uit, TOOL_GET_BESTUURSFINANCIEN)
    key = json.loads(uit)["data_key"]
    j2025 = {
        (w.maat, w.selectie[-1].split(": ")[0], w.decimaal)
        for w in waarden
        if "Verslagjaar: 2025" in w.selectie and w.maat == "Solvabiliteit I"
    }
    # Bestuur 0,69, sectorcijfer 0,64, verschil 0,05 (tests/test_financien.py), elk met zijn rol in de selectie.
    assert j2025 == {
        ("Solvabiliteit I", "Variant", Decimal("0.69")),
        ("Solvabiliteit I", "Verslagjaar", Decimal("0.64")),
        ("Solvabiliteit I", "Verschil met de sector", Decimal("0.05")),
    }
    rente = next(w for w in waarden if w.maat == "Rentabiliteit" and "Variant: geconsolideerd" in w.selectie)
    assert rente.eenheid == "%"
    rijk = {w.eenheid: w.decimaal for w in waarden if w.maat == "Rijksbijdragen" and "Verslagjaar: 2025" in w.selectie}
    assert rijk == {"€": Decimal(197_021_000), "€ mln": Decimal("197.0")}
    assert all(w.data_key == key for w in waarden)
    # De signaleringswaarde is van de Inspectie, niet van DUO: die bron noemt de citatie.
    grens = next(w for w in waarden if "Grens: signaleringswaarde" in w.selectie)
    assert grens.decimaal == Decimal("0.5") and "Inspectie" in str(grens.bron)
    # Het aantal eenheden in het sectorcijfer (8 in 2025, 40833 telt drie keer).
    assert any(w.maat == "Eenheden" and w.decimaal == 8 and "Verslagjaar: 2025" in w.selectie for w in waarden)


def test_wopi_elk_getal_is_een_meetwaarde_met_eenheid_en_variant(register_wo):
    uit = _wopi(instelling="Universiteit Utrecht", uitsplitsing="wp_obp")
    waarden = {w.maat: w for w in meetwaarden(uit, TOOL_GET_WO_PERSONEEL)}
    assert {m: w.decimaal for m, w in waarden.items()} == {
        "Personeel": Decimal("6184.36"),
        "Wetenschappelijk personeel": Decimal("3584.05"),
        "Ondersteunend en beheerspersoneel (OBP)": Decimal("2600.31"),
    }
    personeel = waarden["Personeel"]
    assert personeel.eenheid == "fte" and personeel.cijfers == {"6184"}
    assert personeel.selectie == (
        "Instelling: Universiteit Utrecht",
        "Peildatum: 31-12-2025",
        "Variant: zonder het HOOP-gebied Gezondheid (GEZO)",
    )
    assert personeel.bron == "WOPI 2025, Universiteiten van Nederland, peildatum 31-12-2025, excl. sector Gezondheid"


def test_wopi_aandelen_in_procent_en_leeftijd_in_personen(register_wo):
    geslacht = {w.maat: w for w in meetwaarden(_wopi(instelling="UU", uitsplitsing="geslacht"), TOOL_GET_WO_PERSONEEL)}
    assert geslacht["Aandeel vrouwen"].eenheid == "%"
    leeftijd = meetwaarden(_wopi(instelling="UU", eenheid="personen", uitsplitsing="leeftijd"), TOOL_GET_WO_PERSONEEL)
    assert {w.maat for w in leeftijd} >= {"Personeel", "Leeftijd <25"}
    assert {w.eenheid for w in leeftijd} == {"personen"}


@pytest.mark.parametrize(
    ("geschreven", "waarde", "past"),
    [
        ("0,69", "0.69", True),
        ("0,7", "0.69", True),
        ("0,50", "0.5", True),
        ("0,50", "0.57", False),
        ("3,2", "3.24", True),
    ],
)
def test_een_getal_met_komma_past_op_de_decimalen_van_de_tekst(geschreven, waarde, past):
    from agent.meetwaarden import Meetwaarde

    w = Meetwaarde(frozenset({"0"}), "x", decimaal=Decimal(waarde))
    assert schrijft(w, Decimal(geschreven.replace(",", "."))) is past


# --- citaties ----------------------------------------------------------------------------------------------------


def test_een_financienantwoord_heeft_een_vastgestelde_citatie_voor_elk_getal_uit_de_tool():
    uit = _financien()
    tekst = (
        "ROC Midden Nederland had in 2025 een solvabiliteit I van 0,69, tegen 0,64 voor de mbo-sector (verschil "
        "0,05). De liquiditeit was 3,2 en ligt boven de signaleringswaarde van 0,50. De rentabiliteit was 2,01 %. "
        "De rijksbijdragen waren € 197,0 miljoen (€ 197.021.000)."
    )
    gevonden = citaties(tekst, [(TOOL_GET_BESTUURSFINANCIEN, uit)])
    assert [c["getal"] for c in gevonden] == ["0,69", "0,64", "0,05", "3,2", "0,50", "2,01", "197,0", "197.021.000"]
    assert all(c["vastgesteld"] for c in gevonden)
    per_getal = {c["getal"]: c for c in gevonden}
    assert per_getal["0,64"]["selectie"] == "Sectorcijfer: mbo · Verslagjaar: 2025"
    # 3,2 is ook de rentabiliteit van 2024 (3,24 %): de zin noemt de liquiditeit.
    assert per_getal["3,2"]["maat"] == "Liquiditeit"
    assert per_getal["0,50"]["bron"].startswith("Inspectie van het Onderwijs")
    assert per_getal["197,0"]["eenheid"] == "€ mln"
    assert per_getal["0,69"]["bron"].startswith("DUO · Financiële verantwoording uit XBRL")
    assert per_getal["0,69"]["data_key"] == json.loads(uit)["data_key"]


def test_een_wopi_antwoord_heeft_een_vastgestelde_citatie_voor_elk_getal_uit_de_tool(register_wo):
    uit = _wopi(instelling="Universiteit Utrecht", uitsplitsing="wp_obp")
    tekst = (
        "De Universiteit Utrecht had op 31-12-2025 6.184,36 fte personeel (zonder GEZO), waarvan 3.584,05 fte "
        "wetenschappelijk personeel en 2.600 fte OBP."
    )
    gevonden = citaties(tekst, [(TOOL_GET_WO_PERSONEEL, uit)])
    assert [(c["getal"], c["vastgesteld"], c.get("maat")) for c in gevonden] == [
        ("6.184,36", True, "Personeel"),
        ("3.584,05", True, "Wetenschappelijk personeel"),
        ("2.600", True, "Ondersteunend en beheerspersoneel (OBP)"),
    ]
    assert {c["eenheid"] for c in gevonden} == {"fte"}
    assert {c["bron"] for c in gevonden} == {json.loads(uit)["bron"]["regel"]}


def test_een_getal_met_komma_zonder_meetwaarde_krijgt_geen_citatie():
    """Buiten de twee tools blijft een getal met komma buiten de citaties, zoals voor #956."""
    tekst = "Het aandeel was 12,5 % en de solvabiliteit I 0,69."
    assert [c["getal"] for c in citaties(tekst, [(TOOL_GET_BESTUURSFINANCIEN, _financien())])] == ["0,69"]


# --- bronnen en telling ------------------------------------------------------------------------------------------


def test_de_bronregel_staat_er_een_keer_ook_met_de_tabel_in_de_store():
    uit = _financien()
    assert len(bronnen_van([(TOOL_GET_BESTUURSFINANCIEN, uit)])) == 1


def test_telling_financien_noemt_de_eenheden_in_het_sectorcijfer():
    uit = _financien()
    blok = telling_blok([uit], "Solvabiliteit I 0,69.")
    assert blok.startswith("**Telling**")
    assert "het gewogen cijfer van de Inspectie over alle eenheden van de sector (8 in 2025, 4 in 2024)" in blok


def test_telling_wopi_zegt_wat_fte_en_personen_tellen(register_wo):
    blok = telling_blok([_wopi(instelling="UU", gezo="incl")], "")
    assert "WOPI telt fte (1 fte is een volledige werkweek; geen aantal personen)" in blok
    assert "met het HOOP-gebied Gezondheid (GEZO)" in blok
    assert "elk één keer per universiteit" in telling_blok([_wopi(eenheid="personen")], "")


def test_een_fusie_in_de_reeks_staat_in_de_telling(monkeypatch):
    from onderwijsbronnen.rio import Stap

    stap = Stap("40295", "Stg. Alg. Voortgez. Onderwijs", "volledig", "2025-01-01", via="30932", wet=None)
    monkeypatch.setattr(fusies, "_voorgangers", lambda code, sinds: (stap,) if code == "30932" else ())
    assert "Fusie bij Stg. Firda (30932)" in telling_blok([_financien("Firda")], "")


# --- store, export, inhoudshash ----------------------------------------------------------------------------------


def test_financien_de_tabel_staat_met_keymeta_in_de_store():
    uit = json.loads(_financien("ROC van Amsterdam"))
    assert (uit["data_key"], uit["dataset"]) == ("financien:40833-25pz", "duo:financien")
    known = _meta(uit["data_key"])
    assert (known.bron, known.dataset) == ("duo", "duo:financien")
    assert known.laad == (TOOL_GET_BESTUURSFINANCIEN, {"instelling_of_bestuur": "40833-25PZ"})
    assert known.peilmoment == (
        "editie verslagjaren 2021-2025, peildatum 31 december 2025, versie van 15 september 2026"
    )
    df = store.get(uit["data_key"])
    assert list(df["verslagjaar"]) == [2024, 2025] and set(df["eenheid"]) == {"40833-25PZ"}


def test_financien_export_is_een_csv_met_editie_en_inhoudshash():
    uit = _financien()
    key = csv_export.export_key(TOOL_GET_BESTUURSFINANCIEN, uit)
    assert key == "financien:40597"
    csv = _csv(key)
    regels = csv.splitlines()
    assert regels[0] == (
        "# bron: DUO, dataset duo:financien, editie verslagjaren 2021-2025, peildatum 31 december 2025, versie van "
        "15 september 2026"
    )
    assert f"# inhoudshash van de brontabel: {inhoudshash.inhoudshash(store.get(key))} " in csv
    assert regels[2].startswith("eenheid;naam;sector;groepering;verslagjaar;variant;solvabiliteit_1")


def test_wopi_export_is_een_csv_met_peildatum_variant_en_inhoudshash(register_wo):
    uit = _wopi(instelling="UU", uitsplitsing="wp_obp")
    key = csv_export.export_key(TOOL_GET_WO_PERSONEEL, uit)
    assert key == "wopi:21pd:fte:excl:wp_obp:2025"
    known = _meta(key)
    assert (known.bron, known.dataset) == ("unl", "unl:wopi")
    assert known.laad == (
        TOOL_GET_WO_PERSONEEL,
        {"instelling": "21PD", "jaar": 2025, "uitsplitsing": "wp_obp", "eenheid": "fte", "gezo": "excl"},
    )
    regels = _csv(key).splitlines()
    assert regels[0] == "# bron: UNL, dataset unl:wopi, peildatum 31-12-2025, excl. sector Gezondheid"
    assert regels[1].startswith("# inhoudshash van de brontabel: ")
    assert regels[2:] == [
        "instelling;eenheid;gezo;jaar;totaal;obp;wetenschappelijk_personeel",
        "21PD;fte;excl;2025;6184,36;2600,31;3584,05",
    ]


def test_een_melding_zet_niets_in_de_store():
    assert "data_key" not in _financien("12345")
    assert store.list_keys() == []


# --- herladen en rapport -----------------------------------------------------------------------------------------


def test_financien_komt_na_een_herstart_uit_haar_recept():
    uit = _financien()
    key = json.loads(uit)["data_key"]
    recept = herlaad.recept(key, {"name": TOOL_GET_BESTUURSFINANCIEN, "arguments": {"instelling_of_bestuur": "x"}})
    assert recept is not None and recept == {"laad": [TOOL_GET_BESTUURSFINANCIEN, {"instelling_of_bestuur": "40597"}]}
    voor = store.get(key)
    store.clear()
    assert herlaad.herlaad(key, recept).gelukt
    pd.testing.assert_frame_equal(store.get(key), voor)


def test_zonder_bevestigde_licentie_haalt_een_recept_de_financien_niet_op(monkeypatch):
    key = json.loads(_financien())["data_key"]
    recept = herlaad.recept(key, {"name": TOOL_GET_BESTUURSFINANCIEN, "arguments": {}})
    assert recept is not None
    store.clear()
    monkeypatch.setattr(beschikbaarheid.Config, "APP_ENV", "playground")
    monkeypatch.setattr(beschikbaarheid, "LICENTIE_BEVESTIGD", False)
    uitkomst = herlaad.herlaad(key, recept)
    assert not uitkomst.gelukt and "in deze omgeving geen cijfers" in uitkomst.melding


@pytest.mark.parametrize("vlag", [True, False])
def test_wopi_komt_alleen_met_de_vlag_terug_uit_zijn_recept(monkeypatch, register_wo, vlag):
    key = json.loads(_wopi(instelling="UU", reeks=True))["data_key"]
    recept = herlaad.recept(key, {"name": TOOL_GET_WO_PERSONEEL, "arguments": {}})
    assert recept is not None and recept == {
        "laad": [
            TOOL_GET_WO_PERSONEEL,
            {"instelling": "21PD", "reeks": True, "uitsplitsing": "geen", "eenheid": "fte", "gezo": "excl"},
        ]
    }
    store.clear()
    monkeypatch.setattr(config, "WO_PERSONEEL_ENABLED", vlag)
    assert herlaad.herlaad(key, recept).gelukt is vlag


def test_het_rapport_noemt_de_bron_van_beide_tools():
    """Zonder vlag kent de catalogus WOPI niet: dan het ID als titel (met de vlag: tests/test_beschikbaarheid.py)."""
    datasets = [
        {"data_key": "financien:40597", "herkomst": [{"name": TOOL_GET_BESTUURSFINANCIEN, "arguments": {}}]},
        {"data_key": "wopi:landelijk", "herkomst": [{"name": TOOL_GET_WO_PERSONEEL, "arguments": {}}]},
    ]
    assert sources_from_recipe(build_recipe(datasets)) == [
        "DUO — Financiële verantwoording uit XBRL: kengetallen en rijksbijdragen per bestuur (duo:financien)",
        "UNL — unl:wopi",
    ]


# --- snippet (#945) ----------------------------------------------------------------------------------------------


def _draai(code: str | None) -> pd.DataFrame:
    assert code is not None
    ruimte: dict = {}
    exec(compile(code.replace("print(df)", ""), "<snippet>", "exec"), ruimte)
    return ruimte["df"]


def test_de_snippet_van_de_financien_geeft_de_tabel_in_de_store(monkeypatch):
    uit = _financien("ROC van Amsterdam")
    code = snippet.generate(TOOL_GET_BESTUURSFINANCIEN, {"instelling_of_bestuur": "ROC van Amsterdam"}, uit)
    monkeypatch.setattr(fin.financien, "laad", lambda *a, **k: _DATA)
    pd.testing.assert_frame_equal(_draai(code), store.get(json.loads(uit)["data_key"]))


def test_een_selectie_op_de_wopi_tabel_begint_haar_snippet_bij_unl_load(register_wo):
    """Een volgende stap op de key (query_data) laadt via de laadregels van WOPI, niet via een kopie van de rijen."""
    uit = _wopi(reeks=True, uitsplitsing="wp_obp")
    key = json.loads(uit)["data_key"]
    args = {"data_key": key, "filters": {"jaar__gte": 2024}}
    selectie = query_data(key, filters={"jaar__gte": 2024})
    recepten = {key: herlaad.recept(key, {"name": TOOL_GET_WO_PERSONEEL, "arguments": {}})}
    code = snippet.generate(TOOL_QUERY_DATA, args, selectie, recept_van=recepten.get)
    assert code is not None and "unl.load(" in code and "kopie van een eerdere stap" not in code
    gekregen = _draai(code)
    verwacht = store.get(json.loads(selectie)["data_key"])
    pd.testing.assert_frame_equal(gekregen.reset_index(drop=True), verwacht.reset_index(drop=True))
