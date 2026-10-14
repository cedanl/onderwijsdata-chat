"""get_maat (#188): het model kiest maat en afbakening, de code kiest dataset, bestand en codes.

De bronnen zijn hier fixtures (DUO via `tools.duo._duo.load`, CBS via `tools.cbs.data`); de
catalogus is echt, zodat de bestandskeuze op de gepinde titels staat. Het register is een nep.
"""

import json
from typing import Any
from unittest.mock import patch

import pandas as pd
import pytest

from tools import herlaad, maten, snippet, store
from tools.csv_export import bestandsnaam, export_key
from tools.maten import MATEN, get_maat, plan
from tools.schemas import TOOL_GET_MAAT, TOOL_SCHEMAS

_REGISTER = {
    "hogeschool utrecht": {"naam": "Hogeschool Utrecht", "sector": "hbo", "instellingscode": "25DW"},
    "hu": {"naam": "Hogeschool Utrecht", "sector": "hbo", "instellingscode": "25DW"},
    "universiteit utrecht": {"naam": "Universiteit Utrecht", "sector": "wo", "instellingscode": "21PD"},
    "roc mondriaan": {"naam": "ROC Mondriaan", "sector": "mbo", "instellingscode": "27GZ"},
}


def _ho(dataset: str, kolom: str) -> pd.DataFrame:
    rijen = [
        (2021, "25DW", "Hogeschool Utrecht", "VT", 100),
        (2021, "25DW", "Hogeschool Utrecht", "VT", 200),
        (2021, "25DW", "Hogeschool Utrecht", "DT", 50),
        (2022, "25DW", "Hogeschool Utrecht", "VT", 999),
        (2022, "25DW", "Hogeschool Utrecht", "VT", -1),
        (2021, "99ZZ", "Andere Hogeschool", "VT", 7),
    ]
    kolommen = ["STUDIEJAAR", "INSTELLINGSCODE_ACTUEEL", "INSTELLINGSNAAM_ACTUEEL", "OPLEIDINGSVORM", kolom]
    return pd.DataFrame(rijen, columns=kolommen)


_MBO = pd.DataFrame(
    [
        (2023, "27GZ", "ROC Mondriaan", 1000, 10, 5000, 40),
        (2024, "27GZ", "ROC Mondriaan", 1100, 20, 5100, -1),
        (2024, "25PZ", "Ander ROC", 1, 1, 1, 1),
    ],
    columns=["JAAR", "INSTELLINGSCODE", "INSTELLINGSNAAM", "BBL", "BOLDT", "BOLVT", "EX"],
)
_BESTANDEN = {
    ("p01hoinges", 3): _ho("p01hoinges", "AANTAL_INGESCHREVENEN"),
    ("p03hoinschr", 3): _ho("p03hoinschr", "AANTAL_INSCHRIJVINGEN"),
    ("p02ho1ejrs", 3): _ho("p02ho1ejrs", "AANTAL_EERSTEJAARS_INGESCHREVENEN"),
    ("mbo-studenten-per-instelling", 0): _MBO,
}
_CBS_DEFS = {
    "Onderwijssoort": {"type": "Dimension", "title": "Onderwijssoort"},
    "Opleidingsvorm": {"type": "Dimension", "title": "Opleidingsvorm"},
    "Opleidingsfase": {"type": "Dimension", "title": "Opleidingsfase"},
    "Geslacht": {"type": "Dimension", "title": "Geslacht"},
    "Perioden": {"type": "TimeDimension", "title": "Perioden"},
    "TotaalIngeschrevenen_1": {"type": "Topic", "title": "Totaal ingeschrevenen", "unit": "aantal"},
}
_CBS_RIJ = {
    "Onderwijssoort": "A025294",
    "Opleidingsvorm": "A028666",
    "Opleidingsfase": "A045745",
    "Geslacht": "T001038",
    "Perioden": "2024SJ00",
    "TotaalIngeschrevenen_1": 378490,
}


@pytest.fixture(autouse=True)
def _bronnen():
    def laad(dataset_id, resource):
        return _BESTANDEN[(dataset_id, resource)].copy()

    with (
        patch(
            "tools.maten.instellingen.instellingsprofiel", side_effect=lambda naam: _REGISTER.get(naam.strip().lower())
        ),
        patch("tools.duo._duo.load", side_effect=laad),
        patch("tools.cbs.definitions", return_value=_CBS_DEFS),
        patch("tools.cbs.data", return_value=[_CBS_RIJ]) as cbs_data,
    ):
        yield cbs_data


def _uit(tekst: str) -> dict:
    uit = json.loads(tekst)
    assert "data_key" in uit, uit
    return uit


# --- het plan: geen gok --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("args", "tekst"),
    [
        ({"maat": "studenten"}, "Onbekende maat"),
        ({"maat": "ingeschreven_personen_ho"}, "Geef voor ingeschreven_personen_ho de instelling"),
        ({"maat": "ingeschreven_personen_ho", "instelling": "Hogeschool Nergens"}, "Onbekende instelling"),
        ({"maat": "ingeschreven_personen_ho", "instelling": "HU", "vorm": "bol"}, "past niet bij"),
        ({"maat": "ingeschreven_personen_ho", "instelling": "HU", "schooljaren": ["ooit"]}, "niet begrepen"),
        ({"maat": "deelnemers_ho_landelijk"}, "Geef voor deelnemers_ho_landelijk de sector"),
        ({"maat": "ingeschreven_personen_ho", "instelling": "ROC Mondriaan"}, "is een mbo-instelling"),
        ({"maat": "mbo_studenten_instelling", "instelling": "HU"}, "is een hbo-instelling"),
    ],
)
def test_een_fout_in_maat_of_afbakening_is_een_melding_geen_gok(args: dict[str, Any], tekst):
    uitkomst = plan(**args)
    assert isinstance(uitkomst, str) and tekst in uitkomst
    assert tekst in get_maat(**args)


def test_het_plan_kiest_het_opleidingsvormbestand_per_sector_en_vertaalt_vorm_en_schooljaar():
    hbo = plan("ingeschreven_personen_ho", "Hogeschool Utrecht", vorm="voltijd", schooljaren=["2022/23", "2021"])
    assert isinstance(hbo, maten.Plan)
    assert (hbo.bestand, hbo.sector, hbo.jaren) == (3, "hbo", (2021, 2022))
    assert maten.filters(hbo) == {"INSTELLINGSCODE_ACTUEEL": "25DW", "OPLEIDINGSVORM": "VT", "STUDIEJAAR": [2021, 2022]}
    assert maten.aggregate(hbo) == {"AANTAL_INGESCHREVENEN": "sum"}
    wo = plan("eerstejaars_ho", "Universiteit Utrecht")
    assert isinstance(wo, maten.Plan) and (wo.bestand, wo.vorm, wo.jaren) == (4, "alle", ())
    assert maten.filters(wo) == {"INSTELLINGSCODE_ACTUEEL": "21PD"}


def test_het_cbs_plan_pint_elke_dimensie_op_een_vaste_code():
    p = plan("deelnemers_ho_landelijk", sector="wo", vorm="deeltijd", schooljaren=["2024/25"])
    assert isinstance(p, maten.Plan)
    assert maten.selectie(p) == {
        "dimensies": {
            "Onderwijssoort": "A025297",
            "Opleidingsvorm": "A028667",
            "Opleidingsfase": "A045745",
            "Geslacht": "T001038",
        },
        "periode": ["2024/25"],
        "onderwerpen": ["TotaalIngeschrevenen_1"],
        "sector": "wo",
    }


def test_schema_en_recepten_zeggen_hetzelfde():
    schema = next(s for s in TOOL_SCHEMAS if s["function"]["name"] == TOOL_GET_MAAT)["function"]["parameters"]
    assert schema["properties"]["maat"]["enum"] == list(MATEN)
    alle_vormen = {v for r in MATEN.values() for v in maten.vormen(r)}
    assert set(schema["properties"]["vorm"]["enum"]) == alle_vormen


# --- de uitvoering: dezelfde tools, één rij per studiejaar ---------------------------------------


def test_personen_hu_voltijd_per_studiejaar_met_de_onderdrukte_cel_als_ondergrens():
    uit = _uit(get_maat("ingeschreven_personen_ho", "Hogeschool Utrecht", vorm="voltijd"))
    assert uit["data_key"].startswith("duo:p01hoinges:3:")
    assert {r["STUDIEJAAR"]: r["AANTAL_INGESCHREVENEN"] for r in uit["rijen"]} == {2021: 300, 2022: 999}
    assert uit["maat"] == "ingeschreven_personen_ho" and uit["teldefinitie"].startswith("personen")
    assert uit["instelling"] == _REGISTER["hogeschool utrecht"] and uit["vorm"] == "voltijd"
    assert (uit["periodekolom"], uit["waardekolom"], uit["totaal_rijen"]) == ("STUDIEJAAR", "AANTAL_INGESCHREVENEN", 2)
    assert uit["recept"]["bestand"] == 3 and uit["recept"]["filters"]["OPLEIDINGSVORM"] == "VT"
    assert any("-1" in regel or "onderdrukt" in regel.lower() for regel in uit["databewerking"])
    known = store.meta(uit["data_key"])
    assert known is not None and known.afgeleid_van == "duo:p01hoinges:3"


def test_alle_vormen_telt_voltijd_en_deeltijd_samen_en_een_gevraagd_jaar_zonder_data_staat_erbij():
    uit = _uit(get_maat("ingeschreven_personen_ho", "HU", schooljaren=["2021/22", "2030/31"]))
    assert [r["AANTAL_INGESCHREVENEN"] for r in uit["rijen"]] == [350]
    assert uit["ontbrekende_schooljaren"] == ["2030/31"]
    assert "OPLEIDINGSVORM" not in uit["recept"]["filters"]


def test_inschrijvingen_zeggen_dat_het_geen_personen_zijn():
    uit = _uit(get_maat("inschrijvingen_ho", "Hogeschool Utrecht", vorm="voltijd", schooljaren=["2021/22"]))
    assert uit["rijen"] == [{"STUDIEJAAR": 2021, "STUDIEJAAR_LABEL": "2021/2022", "AANTAL_INSCHRIJVINGEN": 300}]
    assert "inschrijvingen" in uit["noot"] and "ingeschreven_personen_ho" in uit["noot"]


def test_mbo_telt_de_leerwegkolommen_van_de_vorm_op_als_aantal():
    bol = _uit(get_maat("mbo_studenten_instelling", "ROC Mondriaan", vorm="bol"))
    assert {r["JAAR"]: r["AANTAL"] for r in bol["rijen"]} == {2023: 5010, 2024: 5120}
    assert bol["data_key"].endswith(":mbo_studenten_instelling") and bol["waardekolom"] == "AANTAL"
    alle = _uit(get_maat("mbo_studenten_instelling", "ROC Mondriaan"))
    assert {r["JAAR"]: r["AANTAL"] for r in alle["rijen"]} == {2023: 6050, 2024: 6220}  # 2024: EX is -1, telt niet
    known = store.meta(alle["data_key"])
    assert known is not None and known.stap is not None and "AANTAL = BBL + BOLDT + BOLVT + EX" in known.stap


def test_landelijk_cbs_met_vaste_codes(_bronnen):
    uit = _uit(get_maat("deelnemers_ho_landelijk", sector="hbo", vorm="voltijd", schooljaren=["2024/25"]))
    params = _bronnen.call_args.kwargs
    for code in ("A025294", "A028666", "A045745", "T001038", "2024SJ00"):
        assert code in params["$filter"]
    assert uit["rijen"][0]["TotaalIngeschrevenen_1"] == 378490 and uit["rijen"][0]["Perioden"] == "2024SJ00"
    assert uit["sector"] == "hbo" and uit["waardekolom"] == "TotaalIngeschrevenen_1"
    assert uit["recept"]["selectie"]["dimensies"]["Onderwijssoort"] == "A025294"


# --- herladen en snippet: het recept is de herkomst --------------------------------------------


def test_een_key_uit_get_maat_komt_na_een_herstart_terug_door_het_recept():
    args: dict[str, Any] = {"maat": "ingeschreven_personen_ho", "instelling": "HU", "vorm": "voltijd"}
    key = _uit(get_maat(**args))["data_key"]
    recept = herlaad.recept(key, {"name": "get_maat", "arguments": args})
    known = store.meta(key)
    assert known is not None
    assert recept == {"afgeleid_van": "duo:p01hoinges:3", "tool": "get_maat", "args": args, "stap": known.stap}
    store.clear()
    uitkomst = herlaad.herlaad(key, recept)
    assert uitkomst.gelukt and store.get(key) is not None
    mbo = _uit(get_maat("mbo_studenten_instelling", "ROC Mondriaan"))["data_key"]
    store.clear()
    assert herlaad.herlaad(
        mbo, {"tool": "get_maat", "args": {"maat": "mbo_studenten_instelling", "instelling": "ROC Mondriaan"}}
    ).gelukt


def test_de_snippet_is_het_recept_als_script():
    duo_script = snippet.generate(
        "get_maat",
        {"maat": "ingeschreven_personen_ho", "instelling": "HU", "vorm": "voltijd", "schooljaren": ["2021/22"]},
    )
    assert duo_script is not None
    assert 'duo.load("p01hoinges", 3)' in duo_script and "'25dw'" in duo_script and "'vt'" in duo_script
    assert "groupby(group_by" in duo_script and "'STUDIEJAAR'" in duo_script
    mbo_script = snippet.generate(
        "get_maat", {"maat": "mbo_studenten_instelling", "instelling": "ROC Mondriaan", "vorm": "bol"}
    )
    assert mbo_script is not None and "['BOLVT', 'BOLDT']" in mbo_script
    cbs_script = snippet.generate("get_maat", {"maat": "deelnemers_ho_landelijk", "sector": "hbo", "vorm": "voltijd"})
    assert cbs_script is not None and "85423NED" in cbs_script and "A028666" in cbs_script
    assert snippet.generate("get_maat", {"maat": "x"}) == "# Onbekende maat 'x'. Kies uit: " + ", ".join(MATEN) + "."


# --- de tabel achter het antwoord is te downloaden (#538) -----------------------------------------


@pytest.mark.parametrize(
    "args",
    [
        {"maat": "ingeschreven_personen_ho", "instelling": "Hogeschool Utrecht", "vorm": "voltijd"},
        {"maat": "mbo_studenten_instelling", "instelling": "ROC Mondriaan"},  # eigen key met het totaal
    ],
)
def test_de_uitkomst_van_get_maat_is_exporteerbaar_met_recept(args):
    """Zonder export_key geen CSV-knop; zonder recept geeft de route na een herstart 404."""
    uit = _uit(get_maat(**args))
    key = export_key(TOOL_GET_MAAT, json.dumps(uit))
    assert key is not None
    assert key == uit["data_key"]
    dataset = uit["data_key"].split(":")[1]
    assert bestandsnaam(key).endswith(f"_{dataset.replace('-', '_')}.csv")  # <titel>_<dataset-id>.csv (#533)
    recept = herlaad.recept(key, {"name": TOOL_GET_MAAT, "arguments": args})
    assert recept is not None and recept["tool"] == TOOL_GET_MAAT
