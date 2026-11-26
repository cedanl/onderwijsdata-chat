"""Dashboardlaag: de vacatures van CBS 83599NED per sector via de koppeltabel (#1225), geen DUO -1 als getal (#228).

Tot #1225 kwamen de vacatures uit UWV Open Match (beroepenclusters, een momentopname van mei 2023); de regels die
bleven: geen stille terugval op alle vacatures (#229) en een gedeelde bedrijfstak telt naar rato (#455).
"""

import inspect
import json
from unittest.mock import patch

import pandas as pd
import pytest

import data.dashboard as dashboard
from data import arbeidsmarkt, sbi_koppeling, vacatures_cbs

_KW = tuple(vacatures_cbs.Periode(f"2026KW0{i}", f"2026 {i}e kwartaal", True) for i in (1, 2, 3))
_VIER = (vacatures_cbs.Periode("2025KW04", "2025 4e kwartaal", True), *_KW)


def _sectie(code: str, naam: str, laatste: int | None, gemiddelde: int | None) -> vacatures_cbs.Sectie:
    return vacatures_cbs.Sectie(
        code, naam, vacatures_cbs.Waarde(_KW[-1:], laatste), vacatures_cbs.Waarde(_VIER, gemiddelde)
    )


_STAND = vacatures_cbs.Provinciestand(
    provincie="Utrecht",
    laatste=_KW[-1],
    gemiddeld_over=_VIER,
    totaal=_sectie("A-U", "Alle economische activiteiten", 3000, 2800),
    secties=(
        _sectie("C", "Industrie", 1000, 1000),
        _sectie("M", "Specialistische zakelijke diensten", 900, 900),
        _sectie("K", "Financiële dienstverlening", 500, 300),
        _sectie("S", "Overige dienstverlening", None, None),
    ),
)
# C bij TECHNIEK; M bij TECHNIEK en ECONOMIE (elk de helft); K bij ECONOMIE; S bij geen hbo-sector.
_RIJEN = (
    sbi_koppeling.Rij("C", "Industrie", {"mbo": (), "hbo": ("TECHNIEK",), "wo": ()}, "r"),
    sbi_koppeling.Rij("M", "Zakelijk", {"mbo": (), "hbo": ("TECHNIEK", "ECONOMIE"), "wo": ()}, "r"),
    sbi_koppeling.Rij("K", "Financieel", {"mbo": (), "hbo": ("ECONOMIE",), "wo": ()}, "r"),
    sbi_koppeling.Rij("S", "Overig", {"mbo": (), "hbo": (), "wo": ()}, "r"),
)
_DEELKAART = {"TECHNIEK": ["C", "M"], "ECONOMIE": ["M", "K"]}
_GPS = {"TECHNIEK": 50, "ECONOMIE": 50}


@pytest.fixture
def cbs_stand():
    with (
        patch.object(vacatures_cbs, "stand", return_value=_STAND),
        patch.object(sbi_koppeling, "koppeltabel", return_value=_RIJEN),
    ):
        yield


def _match(gevonden: dict) -> dict:
    with (
        patch.object(dashboard, "resolve_alias", side_effect=lambda naam: naam),
        patch.object(dashboard, "_arbeidsmarktmatch_ho", return_value=gevonden),
        patch.object(dashboard, "_roa_schoolverlaters", return_value={}),
    ):
        return dashboard.load_dashboard_arbeidsmarktmatch("Hogeschool Utrecht")


_HO = {
    "type": "ho",
    "niveau": "hbo",
    "provincie": "Utrecht",
    "arbeidsmarktregio": "Midden-Utrecht",
    "laatste_jaar": 2024,
    "gediplomeerden_per_sector": {**_GPS, "SECTOROVERSTIJGEND": 40},
}


def test_arbeidsmarktmatch_telt_een_gedeelde_bedrijfstak_naar_rato(cbs_stand):
    uit = _match(dict(_HO))

    # TECHNIEK: C 1000 + de helft van M 450; ECONOMIE: de andere helft van M 450 + K 300. Samen de 2200 van C, M en K.
    assert uit["vacatures_per_sector"] == {"TECHNIEK": 1450, "ECONOMIE": 750}
    assert uit["sector_sbi_mapping"] == {"ECONOMIE": ["M", "K"], "SECTOROVERSTIJGEND": [], "TECHNIEK": ["C", "M"]}
    # De bedrijfstakken achter de score, gemiddeld over vier kwartalen, aflopend; S hoort bij geen sector.
    assert uit["vacatures_per_bedrijfstak"] == {
        "C Industrie": 1000,
        "M Specialistische zakelijke diensten": 900,
        "K Financiële dienstverlening": 300,
    }
    assert "vacatures_per_cluster" not in uit and "sector_cluster_mapping" not in uit


def test_een_sector_zonder_koppeling_krijgt_geen_score_maar_de_reden(cbs_stand):
    uit = _match(dict(_HO))

    assert uit["match_score"]["SECTOROVERSTIJGEND"] is None
    assert uit["match_verhouding"]["SECTOROVERSTIJGEND"] is None
    assert uit["match_weggelaten"] == {"SECTOROVERSTIJGEND": "geen vacaturegegevens per bedrijfstak voor deze sector"}
    assert dashboard._MATCH_GEEN_KOPPELING == "geen vacaturegegevens per bedrijfstak voor deze sector"


def test_de_score_rekent_met_het_gemiddelde_van_vier_kwartalen(cbs_stand):
    uit = _match(dict(_HO))

    # Diploma-aandelen 50/140 en 50/140; vacature-aandelen 1450/2200 en 750/2200 (het gemiddelde, niet het laatste
    # kwartaal: K had 500 in het laatste kwartaal en 300 gemiddeld).
    dipl = 50 / 140
    assert uit["match_verhouding"] == {
        "ECONOMIE": round((750 / 2200) / dipl, 2),
        "SECTOROVERSTIJGEND": None,
        "TECHNIEK": round((1450 / 2200) / dipl, 2),
    }
    assert uit["match_score"] == {"ECONOMIE": "evenwicht", "SECTOROVERSTIJGEND": None, "TECHNIEK": "schaarste"}


def test_een_bedrijfstak_zonder_cijfer_is_geen_nul():
    # C heeft bij CBS geen cijfer; ONDERWIJS hoort hier alleen bij C.
    stand = vacatures_cbs.Provinciestand(
        "Utrecht", _KW[-1], _VIER, _STAND.totaal, (_sectie("C", "Industrie", None, None), *_STAND.secties[1:])
    )
    rijen = (sbi_koppeling.Rij("C", "Industrie", {"mbo": (), "hbo": ("ONDERWIJS",), "wo": ()}, "r"), *_RIJEN[1:])
    with (
        patch.object(vacatures_cbs, "stand", return_value=stand),
        patch.object(sbi_koppeling, "koppeltabel", return_value=rijen),
    ):
        uit = _match({**_HO, "gediplomeerden_per_sector": {"TECHNIEK": 50, "ECONOMIE": 50, "ONDERWIJS": 50}})

    # Geen 0 en dus geen "overaanbod", maar een reden.
    assert "ONDERWIJS" not in uit["vacatures_per_sector"]
    assert uit["match_score"]["ONDERWIJS"] is None
    assert uit["match_weggelaten"]["ONDERWIJS"] == dashboard._MATCH_GEEN_GEGEVENS


def test_dashboard_zonder_cbs_heeft_geen_vacatures_en_meldt_het_gat():
    with patch.object(vacatures_cbs, "stand", side_effect=ConnectionError("CBS onbereikbaar")):
        uit = _match(dict(_HO))

    assert uit["vacatures_per_sector"] == {}
    assert set(uit["match_weggelaten"].values()) == {dashboard._MATCH_GEEN_VACATURES}
    assert uit["niet_beschikbaar"] == [
        {"onderdeel": "Vacatures (CBS)", "bron": "CBS", "reden": "de bron was niet bereikbaar"}
    ]


def test_match_scores_met_gewogen_vacatures():
    # Ongewogen (een gedeelde bedrijfstak bij elke sector helemaal) kregen beide sectoren "schaarste" (#455).
    scores = dashboard._match_scores(_GPS, {"TECHNIEK": 1500, "ECONOMIE": 1300}, _DEELKAART)

    assert scores == {"TECHNIEK": "evenwicht", "ECONOMIE": "evenwicht"}


def test_match_scores_schaarste_en_overaanbod():
    scores = dashboard._match_scores({"TECHNIEK": 320, "ECONOMIE": 80}, {"TECHNIEK": 200, "ECONOMIE": 800}, _DEELKAART)

    assert scores == {"TECHNIEK": "overaanbod", "ECONOMIE": "schaarste"}
    assert dashboard._MATCH_DREMPEL == 1.2


def test_match_scores_sector_zonder_koppeling_is_none():
    scm = {"TECHNIEK": ["J"], "ONDERWIJS": []}

    scores = dashboard._match_scores({"TECHNIEK": 50, "ONDERWIJS": 50}, {"TECHNIEK": 500, "ONDERWIJS": 0}, scm)

    assert scores == {"TECHNIEK": "schaarste", "ONDERWIJS": None}


@pytest.mark.parametrize("vacatures", [{}, {"TECHNIEK": 0, "ECONOMIE": 0}])
def test_match_scores_zonder_vacatures_is_alles_none(vacatures):
    assert dashboard._match_scores(_GPS, vacatures, _DEELKAART) == {"TECHNIEK": None, "ECONOMIE": None}
    assert dashboard._match_verhoudingen(_GPS, vacatures, _DEELKAART) == {"TECHNIEK": None, "ECONOMIE": None}


def test_match_verhouding_is_vacature_aandeel_gedeeld_door_diploma_aandeel():
    # #949: de lengte van de staaf. TECHNIEK 0,2 / 0,76 = 0,26 (overaanbod, onder 1 / 1,2); ECONOMIE 0,8 / 0,19 = 4,2
    # (schaarste, boven 1,2); ONDERWIJS heeft geen bedrijfstak en dus geen verhouding, net als geen label.
    gps = {"TECHNIEK": 320, "ECONOMIE": 80, "ONDERWIJS": 20}
    vacatures = {"TECHNIEK": 200, "ECONOMIE": 800}
    scm = {**_DEELKAART, "ONDERWIJS": []}

    verhouding = dashboard._match_verhoudingen(gps, vacatures, scm)
    scores = dashboard._match_scores(gps, vacatures, scm)

    assert verhouding == {"TECHNIEK": 0.26, "ECONOMIE": 4.2, "ONDERWIJS": None}
    assert scores == {"TECHNIEK": "overaanbod", "ECONOMIE": "schaarste", "ONDERWIJS": None}
    drempel = dashboard._MATCH_DREMPEL
    assert (techniek := verhouding["TECHNIEK"]) is not None and techniek < 1 / drempel
    assert (economie := verhouding["ECONOMIE"]) is not None and economie > drempel


def test_match_verhouding_zonder_gediplomeerden_in_een_sector_is_none():
    verhouding = dashboard._match_verhoudingen(
        {"TECHNIEK": 0, "ECONOMIE": 40}, {"TECHNIEK": 5, "ECONOMIE": 5}, _DEELKAART
    )

    assert verhouding == {"TECHNIEK": None, "ECONOMIE": 0.5}


# ─── #952: een kleine sector krijgt geen verhouding ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("n", "met_verhouding"), [(29, False), (30, True)])
def test_onder_de_drempel_geen_label_en_geen_verhouding_maar_een_reden(n, met_verhouding):
    # Tilburg University, Techniek: 52,15 bij 63 gediplomeerden; BUas 7,73 bij 13. Eén diploma meer of minder
    # verschoof de verhouding met tientallen procenten. De drempel geldt voor het gemiddelde per jaar.
    assert dashboard._MATCH_MIN_GEDIPLOMEERDEN == 30
    gps = {"TECHNIEK": n, "ECONOMIE": 600}
    vacatures = {"TECHNIEK": 900, "ECONOMIE": 100}

    verhouding = dashboard._match_verhoudingen(gps, vacatures, _DEELKAART)
    scores = dashboard._match_scores(gps, vacatures, _DEELKAART)
    weggelaten = dashboard._match_weggelaten(gps, vacatures, _DEELKAART)

    if met_verhouding:
        assert verhouding["TECHNIEK"] == round(0.9 / (n / (n + 600)), 2)
        assert scores["TECHNIEK"] == "schaarste"
        assert "TECHNIEK" not in weggelaten
    else:
        assert verhouding["TECHNIEK"] is None and scores["TECHNIEK"] is None
        assert weggelaten == {"TECHNIEK": dashboard._MATCH_TE_WEINIG}
        assert "30" in dashboard._MATCH_TE_WEINIG
    # De kleine sector telt mee in de totalen: de verhouding van de andere hangt niet van de drempel af.
    assert verhouding["ECONOMIE"] == round(0.1 / (600 / (n + 600)), 2)


def test_elke_sector_zonder_label_heeft_een_reden():
    gps = {"TECHNIEK": 100, "ECONOMIE": 10, "ONDERWIJS": 100}
    scm = {**_DEELKAART, "ONDERWIJS": []}

    assert dashboard._match_weggelaten(gps, {"TECHNIEK": 5, "ECONOMIE": 5}, scm) == {
        "ECONOMIE": dashboard._MATCH_TE_WEINIG,
        "ONDERWIJS": dashboard._MATCH_GEEN_KOPPELING,
    }
    assert dashboard._match_weggelaten(gps, {}, scm) == dict.fromkeys(gps, dashboard._MATCH_GEEN_VACATURES)
    scores = dashboard._match_scores(gps, {"TECHNIEK": 5, "ECONOMIE": 5}, scm)
    assert {s for s, label in scores.items() if label is None} == {"ECONOMIE", "ONDERWIJS"}


# --- #228: het dashboard telt DUO -1 niet als getal mee, net als de chat ---


@pytest.fixture
def mbo_met_sentinels():
    ruw = pd.DataFrame(
        [
            {
                "JAAR": 2024,
                "INSTELLINGSNAAM": "Grafisch Lyceum",
                "INSTELLINGSCODE": "1",
                "BBL": 300,
                "BOLDT": -1,
                "BOLVT": 2079,
                "EX": -1,
            },
            {
                "JAAR": 2025,
                "INSTELLINGSNAAM": "Grafisch Lyceum",
                "INSTELLINGSCODE": "1",
                "BBL": 310,
                "BOLDT": 0,
                "BOLVT": 2100,
                "EX": 0,
            },
        ]
    )
    _leeg_laadcaches()
    with patch.object(dashboard.duo, "load", return_value=ruw):
        yield
    # Anders houdt een gecachte loader de nepdata vast voor de tests die echte data laden.
    _leeg_laadcaches()


def _leeg_laadcaches():
    for functie in vars(dashboard).values():
        if hasattr(functie, "cache_clear"):
            functie.cache_clear()


def test_mbo_dashboard_sluit_minus_een_uit(mbo_met_sentinels):
    # Audit ronde 2, D1: Grafisch Lyceum Utrecht 2024 toonde 2377 (= 2379 − 2).
    # De lading van het mbo-bestand en de reeks van het regiodashboard; dit nepbestand is alleen mbo, dus niet de hele lader.
    df = dashboard._load_mbo_studenten()
    result = dashboard._mbo_kern(df[df["INSTELLINGSNAAM"] == "Grafisch Lyceum"])
    assert result["ingeschrevenen"] == {2024: 2379, 2025: 2410}


def test_dashboard_laadt_duo_alleen_via_de_maskerende_helper():
    # Elke nieuwe duo.load in het dashboard zou het -1-gat opnieuw openen.
    bron = inspect.getsource(dashboard)
    assert bron.count("duo.load(") == 1, "laad DUO-data in data/dashboard.py via _duo_load"


# --- #313: de sector-clustermapping draagt haar peildatum ---


def test_mapping_bestand_heeft_een_manifest():
    import json
    from datetime import date
    from pathlib import Path

    ruw = json.loads((Path(arbeidsmarkt.__file__).parent / "sector_cluster_mapping.json").read_text())
    manifest = ruw["_manifest"]
    date.fromisoformat(manifest["bijgewerkt"])
    assert "UWV" in manifest["bron"]


def test_manifest_is_geen_sector(tmp_path):
    bestand = tmp_path / "sector_cluster_mapping.json"
    bestand.write_text('{"_manifest": {"bijgewerkt": "2026-08-17"}, "TECHNIEK": ["ICT"]}')
    assert arbeidsmarkt.load_sector_cluster_map(bestand) == {"TECHNIEK": ["ICT"]}


# --- #460: de mapping zegt dat ze van een taalmodel komt, niet van UWV ---


def test_mapping_bestand_zegt_dat_de_indeling_niet_van_uwv_is():
    ruw = json.loads(arbeidsmarkt.SECTOR_CLUSTER_PATH.read_text())

    assert ruw["_manifest"]["herkomst"] == arbeidsmarkt.MAPPING_HERKOMST
    assert "LLM" in arbeidsmarkt.MAPPING_HERKOMST and "niet van UWV" in arbeidsmarkt.MAPPING_HERKOMST
    assert ruw["_manifest"]["model"]


def test_sector_mapping_manifest_geeft_herkomst_versie_en_model(tmp_path):
    bestand = tmp_path / "sector_cluster_mapping.json"
    manifest = {"bijgewerkt": "2026-08-17", "herkomst": "LLM-classificatie, niet van UWV", "model": "claude-x"}
    bestand.write_text(json.dumps({"_manifest": manifest, "TECHNIEK": ["ICT"]}))

    assert arbeidsmarkt.sector_mapping_manifest(bestand) == {
        "herkomst": "LLM-classificatie, niet van UWV",
        "mapping_versie": "2026-08-17",
        "model": "claude-x",
    }


def test_refresh_script_schrijft_herkomst_en_model_in_het_manifest(tmp_path):
    from core.config import MODEL
    from scripts.refresh_sector_mapping import manifest

    geschreven = manifest(["prompt"])
    bestand = tmp_path / "sector_cluster_mapping.json"
    bestand.write_text(json.dumps({"_manifest": geschreven, "TECHNIEK": ["ICT"]}))

    assert arbeidsmarkt.sector_mapping_manifest(bestand) == {
        "herkomst": arbeidsmarkt.MAPPING_HERKOMST,
        "mapping_versie": geschreven["bijgewerkt"],
        "model": MODEL,
    }


@pytest.mark.parametrize("inhoud", ['{"TECHNIEK": ["ICT"]}', '{"_manifest": {}}', '{"_manifest": "kapot"}', "{kapot"])
def test_sector_mapping_manifest_zonder_velden_is_onbekend(tmp_path, inhoud):
    """Een ontbrekend veld is geen exceptie; de herkomst blijft dan wat het refresh-script schrijft."""
    bestand = tmp_path / "sector_cluster_mapping.json"
    bestand.write_text(inhoud)

    assert arbeidsmarkt.sector_mapping_manifest(bestand) == {
        "herkomst": arbeidsmarkt.MAPPING_HERKOMST,
        "mapping_versie": "onbekend",
        "model": "onbekend",
    }


# De thema's zoals editie 2026 ze spelt; de app leest ze uit het bestand (#1091).
_SIS_THEMA = "Schoolverlatersinformatie (SIS 2025)"
_PROGNOSE_THEMA = "Risicoindicatoren en arbeidsmarktprognoses tot 2030, actualisering"


def test_roa_prognose_in_het_dashboard_is_landelijk():
    """Per niveau staan er 48 regio's; zonder filter won de typering van de laatst gelezen regio (#441)."""
    rijen = pd.DataFrame(
        [
            {
                "regionaam": r,
                "thema": _PROGNOSE_THEMA,
                "aggregatieniveau": arbeidsmarkt._ROA_NIVEAU,
                "detailniveau": "Mbo4",
                "onderwerp": "ITA toekomstige arbeidsmarktsituatie in 2030",
                "perc": None,
                "aantal": None,
                "typering": t,
                "versie": "v1",
            }
            for r, t in (("Nederland", "redelijk"), ("Groningen", "slecht"))
        ]
    )
    with patch.object(arbeidsmarkt, "_roa", return_value=rijen):
        assert dashboard._roa_prognose("mbo") == {"Mbo4": {"ITA toekomstige arbeidsmarktsituatie in 2030": "redelijk"}}


def test_roa_prognose_geeft_de_baanopeningen_en_de_instroom_als_aantal():
    # #951: ROA geeft de baanopeningen en de instroom van schoolverlaters als aantal, zonder typering; het dashboard
    # las alleen typeringen en toonde die twee overal als "—".
    def rij(onderwerp, aantal=None, typering=None):
        return {
            "regionaam": "Nederland",
            "thema": _PROGNOSE_THEMA,
            "aggregatieniveau": arbeidsmarkt._ROA_NIVEAU,
            "detailniveau": "Mbo4",
            "onderwerp": onderwerp,
            "perc": None,
            "aantal": aantal,
            "typering": typering,
            "versie": "v1",
        }

    rijen = pd.DataFrame(
        [
            rij("ITA toekomstige arbeidsmarktsituatie in 2030", typering="redelijk"),
            rij("verwachte baanopeningen tot 2030", aantal=325800.0),
            rij("verwachte instroom van schoolverlaters tot 2030", aantal=358700.0),
        ]
    )
    with patch.object(arbeidsmarkt, "_roa", return_value=rijen):
        assert dashboard._roa_prognose("mbo") == {
            "Mbo4": {
                "ITA toekomstige arbeidsmarktsituatie in 2030": "redelijk",
                "verwachte baanopeningen tot 2030": 325800,
                "verwachte instroom van schoolverlaters tot 2030": 358700,
            }
        }
