"""Gecontroleerde getallen linken naar de meetwaarde waar ze vandaan komen (#365, #415)."""

import json

import pandas as pd
import pytest

from agent.citaties import citaties
from agent.meetwaarden import meetwaarden
from tools import store
from tools.store import KeyMeta

_CBS = json.dumps({"data_key": "cbs:1", "rijen": [{"Onderwijssoort_label": "Hbo", "Totaal": 378490}]})
_DUO = json.dumps({"data_key": "duo:2", "rijen": [{"aantal": 27135}]})
_BRONLOOS = json.dumps({"bron": None, "resultaat": 55555})
# Dezelfde cijfers als code, rijtelling en key-fragment: geen van drieën is een meetwaarde.
_CODE = json.dumps(
    {
        "data_key": "duo:p01hoinges:3:36201e2d",
        "totaal_rijen": 36201,
        "preview": [{"OPLEIDINGSCODE": 36201, "INSTELLINGSCODE": "36201", "OPLEIDINGSNAAM": "Rechten"}],
    }
)
_MAAT = json.dumps(
    {
        "data_key": "duo:p01hoinges:3:abc",
        "rijen": [{"STUDIEJAAR": 2023, "OPLEIDING_NAAM": "Rechten", "AANTAL_INGESCHREVENEN": 36201}],
    }
)


def test_code_met_hetzelfde_getal_is_geen_herkomst():
    [citatie] = citaties("Er zijn 36.201 studenten.", [("get_duo_data", _CODE)])
    assert citatie == {"getal": "36.201", "vastgesteld": False, "reden": "geen_meetwaarde"}


def test_maat_wint_van_code_met_hetzelfde_getal():
    [citatie] = citaties("Er zijn 36.201 studenten.", [("get_duo_data", _CODE), ("query_data", _MAAT)])
    assert citatie["vastgesteld"] is True
    assert (citatie["stap"], citatie["tool"], citatie["maat"]) == (2, "query_data", "Aantal ingeschrevenen")
    assert citatie["selectie"] == "Studiejaar: 2023 · Opleiding naam: Rechten"


def test_getal_krijgt_de_eerste_stap_waarin_het_als_maat_staat():
    steps = [("get_cbs_data", _CBS), ("get_duo_data", _DUO)]
    result = citaties("Er zijn 378.490 en 27.135 studenten.", steps)
    assert [(c["getal"], c["stap"], c["data_key"]) for c in result] == [("378.490", 1, "cbs:1"), ("27.135", 2, "duo:2")]
    assert result[0]["selectie"] == "Onderwijssoort: Hbo"


def test_bron_in_woorden_met_de_hash_ernaast():
    store.put("duo:2", pd.DataFrame({"aantal": [27135]}), KeyMeta(bron="duo", dataset="p01hoinges"))
    store.derive("duo:2", "duo:2:sel", pd.DataFrame({"aantal": [27135]}))
    steps = [("query_data", json.dumps({"data_key": "duo:2:sel", "rijen": [{"aantal": 27135}]}))]
    [citatie] = citaties("Het waren 27.135 studenten.", steps)
    assert citatie["bron"].startswith("DUO · ")
    assert citatie["data_key"] == "duo:2:sel"


def test_eenheid_uit_het_schema_van_de_laadstap():
    laad = json.dumps({"data_key": "cbs:1", "kolommen": [{"kolom": "Totaal", "eenheid": "aantal"}], "preview": []})
    [citatie] = citaties("Er zijn 378.490 studenten.", [("get_cbs_data", laad), ("query_data", _CBS)])
    assert citatie["eenheid"] == "aantal"


def test_ongebonden_getal_in_dataantwoord_krijgt_herkomst_niet_vastgesteld():
    assert citaties("Het waren 99.999 studenten.", [("get_cbs_data", _CBS)]) == [
        {"getal": "99.999", "vastgesteld": False, "reden": "geen_meetwaarde"}
    ]


def test_zonder_gelezen_data_geen_citaties():
    assert citaties("Het waren 55.555 studenten.", [("run_analysis", _BRONLOOS)]) == []
    assert citaties("Er zijn 1.234 datasets.", [("search_catalog", json.dumps({"resultaten": []}))]) == []


def test_jaartallen_en_kleine_getallen_krijgen_er_geen():
    assert [c["getal"] for c in citaties("In 2024 waren er 12 van 378490.", [("get_cbs_data", _CBS)])] == ["378490"]


def test_elk_voorkomen_van_een_getal_krijgt_een_eigen_citatie():
    """CH-08 (#462): de tweede claim met hetzelfde getal kreeg nooit een eigen citatie."""
    assert len(citaties("378.490 is 378.490.", [("get_cbs_data", _CBS)])) == 2


def test_aantal_citaties_hangt_alleen_van_de_tekst_af():
    tekst = "Er zijn 378.490 studenten, 27.135 in het hbo en 36.201 met code."
    steps = [("get_duo_data", _CODE), ("get_cbs_data", _CBS), ("get_duo_data", _DUO)]
    runs = [citaties(tekst, steps) for _ in range(5)]
    assert all(run == runs[0] for run in runs)
    assert len(runs[0]) == 3


def test_kpi_uitkomst_is_een_meetwaarde():
    kpi = json.dumps(
        {
            "label": "Groei",
            "value": "+5.000",
            "raw": 5000,
            "periode": {"van": "2020/21", "tot": "2024/25"},
            "bron": {"data_key": "duo:2", "kolom": "AANTAL", "metric": "delta"},
        }
    )
    [citatie] = citaties("Een groei van 5.000 studenten.", [("compute_kpi", kpi)])
    assert (citatie["maat"], citatie["data_key"]) == ("Groei", "duo:2")
    assert "Periode: 2020/21 – 2024/25" in citatie["selectie"]


def test_analyse_resultaat_is_een_meetwaarde():
    assert citaties("Samen 12.345.", [("run_analysis", "12345")])[0]["vastgesteld"] is True
    gelezen = json.dumps({"gelezen": ["duo:2"], "resultaat": {"totaal": 12345}})
    assert citaties("Samen 12.345.", [("run_analysis", gelezen)])[0]["data_key"] == "duo:2"


def test_een_getal_dat_niet_van_de_data_afhangt_is_geen_meetwaarde():
    """CH-27: `a = 987650; result = a + 4 + len(df) * 0` gaf vastgesteld:true met bron DUO."""
    eigen = json.dumps({"gelezen": ["duo:2"], "resultaat": 987654, "scriptconstanten": [987654]})
    rijen = json.dumps(
        {"gelezen": ["duo:2"], "resultaat": {"totaal": 4600, "drempel": 1000}, "scriptconstanten": [1000]}
    )

    assert not any(c["vastgesteld"] for c in citaties("Samen 987.654.", [("run_analysis", eigen)]))
    assert [w.maat for w in meetwaarden(rijen, "run_analysis")] == ["totaal"]


def test_metadata_van_een_laadstap_is_geen_meetwaarde():
    assert meetwaarden(_CODE, "get_duo_data") == []
    assert meetwaarden("Fout (onbekende_key): 12345", "query_data") == []


def test_duo_labelkolom_wint_van_de_jaarcode():
    rij = {"STUDIEJAAR": 2023, "STUDIEJAAR_LABEL": "2023/2024", "AANTAL": 4567}
    [waarde] = meetwaarden(json.dumps({"data_key": "duo:1", "rijen": [rij]}))
    assert waarde.selectie == ("Studiejaar: 2023/2024",)


_A = json.dumps({"data_key": "duo:a", "rijen": [{"INSTELLINGSNAAM": "Hogeschool A", "AANTAL": 10000}]})
_B = json.dumps({"data_key": "duo:b", "rijen": [{"INSTELLINGSNAAM": "Hogeschool B", "AANTAL": 10000}]})


@pytest.mark.parametrize("volgorde", [1, -1])
def test_de_zin_bepaalt_de_selectie_niet_de_toolvolgorde(volgorde):
    """CH-08: met B vóór A wees 'Instelling A had 10.000' naar B (eerste numerieke match)."""
    steps = [("query_data", _B), ("query_data", _A)][::volgorde]

    [citatie] = citaties("Hogeschool A had 10.000 studenten.", steps)

    assert citatie["vastgesteld"] is True
    assert citatie["data_key"] == "duo:a"
    assert "Hogeschool A" in citatie["selectie"]


@pytest.mark.parametrize("volgorde", [1, -1])
def test_niet_te_onderscheiden_kandidaten_geven_herkomst_niet_vastgesteld(volgorde):
    steps = [("query_data", _B), ("query_data", _A)][::volgorde]

    assert citaties("Het waren 10.000 studenten.", steps) == [
        {"getal": "10.000", "vastgesteld": False, "reden": "meerdere"}
    ]


# --- CH-38 (#458): één getal in een selectie én in een analyse op die selectie ---


@pytest.fixture
def keten():
    """De HAN-route uit audit 17: query_data op p04hogdipl, run_analysis op die selectie."""
    store.clear()
    store.put("duo:p04:0", pd.DataFrame({"x": [1]}), KeyMeta(bron="duo", dataset="p04hogdipl"))
    store.derive("duo:p04:0", "duo:p04:0:sel", pd.DataFrame({"x": [1]}))
    store.derive("duo:p04:0:sel", "analysis:han", pd.DataFrame({"x": [1]}), gelezen=("duo:p04:0:sel",))
    yield
    store.clear()


_SELECTIE = json.dumps(
    {
        "data_key": "duo:p04:0:sel",
        "rijen": [{"DIPLOMAJAAR": 2020, "INSTELLINGSNAAM": "HAN", "AANTAL_GEDIPLOMEERDEN": 6323}],
    }
)
_ANALYSE = json.dumps({"data_key": "analysis:han", "rijen": [{"DIPLOMAJAAR": 2020, "HAN": 6323, "andere": 1910}]})


@pytest.mark.parametrize("volgorde", [1, -1])
def test_een_getal_in_een_selectie_en_een_analyse_daarop_krijgt_de_bron(keten, volgorde):
    """Audit 17: 6.323 stond in beide en kreeg 'staat niet als meetwaarde in de opgehaalde data'."""
    steps = [("query_data", _SELECTIE), ("run_analysis", _ANALYSE)][::volgorde]

    [citatie] = citaties("| 2020 | 6.323 | 76,8% |", steps)

    assert citatie["vastgesteld"] is True
    assert citatie["data_key"] == "duo:p04:0:sel"  # het dichtst bij de bron


def test_twijfel_tussen_losse_selecties_blijft_twijfel(keten):
    """De afleidingsketen beslist alleen binnen één keten; Hogeschool A en B blijven onbeslist (CH-08)."""
    steps = [("query_data", _B), ("query_data", _A), ("run_analysis", _ANALYSE)]

    assert citaties("Het waren 10.000 studenten.", steps)[0]["reden"] == "meerdere"


# --- CH-39 (#459): arbeidsmarktantwoorden hadden nul citaties ---

_UWV = json.dumps(
    {
        "bron": "UWV Open Match",
        "dataset": "uwv-open-match-data",
        "peildatum": "mei 2023",
        "provincie": "Gelderland",
        "totaal_vacatures": 23574,
        "clusters": {"Zorg en welzijn": 9607, "Techniek": 5426},
    }
)
_ROA = json.dumps(
    {
        "bron": "ROA, AIS tot 2030",
        "dataset": "ais2030",
        "versie": "v20251218",
        "regio": "provincie Gelderland",
        "herkomst": {"schoolverlaters_sis_2024": "Nederland", "prognose_tot_2030": "provincie Gelderland"},
        "schoolverlaters_sis_2024": {"Bachelor": {"werkloosheid": {"perc": 4}}},
        "prognose_tot_2030": {
            "Bachelor": {
                "verwachte baanopeningen tot 2030": {"aantal": 435600},
                "ITA toekomstige arbeidsmarktsituatie in 2030": {"typering": "matig"},
            }
        },
    }
)


def test_uwv_vacatures_krijgen_een_citatie_met_provincie_en_cluster():
    [totaal, zorg] = citaties(
        "In Gelderland stonden 23.574 vacatures open, waarvan 9.607 in Zorg en welzijn.",
        [("get_uwv_vacatures", _UWV)],
    )
    assert totaal["vastgesteld"] is True and "UWV" in totaal["bron"] and "Gelderland" in totaal["selectie"]
    assert zorg["vastgesteld"] is True and "Zorg en welzijn" in zorg["selectie"]


_UWV_SECTOR = json.dumps(
    {
        "bron": "UWV Open Match",
        "dataset": "uwv-open-match-data",
        "peildatum": "mei 2023",
        "provincie": "Utrecht",
        "totaal_vacatures": 25225,
        "uwv_broncijfer": {"toelichting": "Ongewogen", "clusters": {"Chauffeurs": 2104, "Programmeurs": 1530}},
        "lokale_classificatie": {"sector": "TECHNIEK", "clusters": ["Chauffeurs", "Programmeurs"]},
        "gewogen_aandeel": {"vacatures_sector": 2582, "gedeelde_clusters": {"Chauffeurs": ["ECONOMIE"]}},
    }
)


def test_uwv_met_sector_houdt_citaties_en_noemt_het_sectorgetal_lokaal_gewogen():
    """#460: de lagen staan genest; het cluster blijft een UWV-cijfer, het sectorgetal heet lokaal gewogen."""
    [sector, cluster] = citaties(
        "In Utrecht telt TECHNIEK 2.582 vacatures, waarvan 2.104 bij Chauffeurs.",
        [("get_uwv_vacatures", _UWV_SECTOR)],
    )
    assert sector["vastgesteld"] is True and "lokaal gewogen" in sector["maat"]
    assert "TECHNIEK" in sector["selectie"]
    assert cluster["vastgesteld"] is True and cluster["maat"] == "Vacatures"
    assert "Chauffeurs" in cluster["selectie"] and "TECHNIEK" in cluster["selectie"]


def test_een_roa_prognose_krijgt_een_citatie_met_regio_uit_de_herkomst():
    [citatie] = citaties("Tot 2030 verwacht ROA 435.600 baanopeningen voor bachelors.", [("get_roa_benchmark", _ROA)])
    assert citatie["vastgesteld"] is True
    assert "ROA" in citatie["bron"] and "v20251218" in citatie["bron"]
    assert "Bachelor" in citatie["selectie"] and "provincie Gelderland" in citatie["selectie"]
    assert citatie["maat"] == "verwachte baanopeningen tot 2030"


def test_een_ander_getal_in_een_arbeidsmarktantwoord_is_expliciet_onbepaald():
    """Klaar als: elk getal uit een ROA-/UWV-antwoord heeft een citatie of expliciet 'onbepaald'."""
    assert citaties("Er zijn 12.345 vacatures.", [("get_uwv_vacatures", _UWV)]) == [
        {"getal": "12.345", "vastgesteld": False, "reden": "geen_meetwaarde"}
    ]


# --- CH-08 (#462): hetzelfde getal in twee claims ---


@pytest.mark.parametrize("volgorde", [1, -1])
def test_twee_claims_met_hetzelfde_getal_krijgen_elk_hun_eigen_selectie(volgorde):
    """Audit 17: 'Instelling B had 10.000. Instelling A had 10.000.' gaf één B-citatie."""
    steps = [("query_data", _B), ("query_data", _A)][::volgorde]

    b, a = citaties("Hogeschool B had 10.000 studenten. Hogeschool A had 10.000 studenten.", steps)

    assert (b["data_key"], a["data_key"]) == ("duo:b", "duo:a")
