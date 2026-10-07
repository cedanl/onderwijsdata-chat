"""Gecontroleerde getallen linken naar de meetwaarde waar ze vandaan komen (#365, #415)."""

import json

import pandas as pd

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
    assert citatie == {"getal": "36.201", "vastgesteld": False}


def test_maat_wint_van_code_met_hetzelfde_getal():
    [citatie] = citaties("Er zijn 36.201 studenten.", [("get_duo_data", _CODE), ("query_data", _MAAT)])
    assert citatie["vastgesteld"] is True
    assert (citatie["stap"], citatie["tool"], citatie["maat"]) == (2, "query_data", "Aantal ingeschrevenen")
    assert citatie["selectie"] == "STUDIEJAAR: 2023 · Opleiding naam: Rechten"


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
        {"getal": "99.999", "vastgesteld": False}
    ]


def test_zonder_gelezen_data_geen_citaties():
    assert citaties("Het waren 55.555 studenten.", [("run_analysis", _BRONLOOS)]) == []
    assert citaties("Er zijn 1.234 datasets.", [("search_catalog", json.dumps({"resultaten": []}))]) == []


def test_jaartallen_en_kleine_getallen_krijgen_er_geen():
    assert [c["getal"] for c in citaties("In 2024 waren er 12 van 378490.", [("get_cbs_data", _CBS)])] == ["378490"]


def test_zelfde_getal_twee_keer_geeft_een_citatie():
    assert len(citaties("378.490 is 378.490.", [("get_cbs_data", _CBS)])) == 1


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


def test_metadata_van_een_laadstap_is_geen_meetwaarde():
    assert meetwaarden(_CODE, "get_duo_data") == []
    assert meetwaarden("Fout (onbekende_key): 12345", "query_data") == []


def test_duo_labelkolom_wint_van_de_jaarcode():
    rij = {"STUDIEJAAR": 2023, "STUDIEJAAR_LABEL": "2023/2024", "AANTAL": 4567}
    [waarde] = meetwaarden(json.dumps({"data_key": "duo:1", "rijen": [rij]}))
    assert waarde.selectie == ("Studiejaar: 2023/2024",)
