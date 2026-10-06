"""DUO-teldefinitie, publicatieregels en opleidingsvorm-codes komen uit DUO zelf (#172, #369).

Live-audit 5: een model noemde DT 'duaal-tijd' (officieel: deeltijd) en
verwisselde p01 (personen) en p03 (inschrijvingen) zonder dat te melden. De
definities komen uit de gepinde riodata-catalogus, niet uit een live CKAN-aanroep.
"""

import json
import math
from unittest.mock import patch

import pandas as pd
import pytest

from agent.telling import telling_blok
from tools import duo_meta
from tools.catalog import dataset_details
from tools.duo import get_duo_data


@pytest.fixture(autouse=True)
def geen_ckan():
    with patch("httpx.get", side_effect=AssertionError("geen netwerkaanroep naar CKAN")):
        yield


def _get(dataset_id: str, df: pd.DataFrame | None = None) -> dict:
    df = pd.DataFrame({"OPLEIDINGSVORM": ["VT", "DT"], "AANTAL": [10, 5]}) if df is None else df
    with patch("tools.duo._duo.load", return_value=df):
        return json.loads(get_duo_data(dataset_id, 3))


def test_p01_p02_en_p03_zijn_onderscheidbaar():
    p01, p02, p03 = (duo_meta.record(d)["_teldefinitie"] for d in ("p01hoinges", "p02ho1ejrs", "p03hoinschr"))

    assert (p01["teleenheid"], p01["inschrijvingstype"]) == ("personen", "hoofdinschrijvingen")
    assert p02["teleenheid"] == "personen"
    assert (p03["teleenheid"], p03["inschrijvingstype"]) == ("inschrijvingen", "hoofd- en neveninschrijvingen")
    assert "natuurlijke personen" in _get("p01hoinges")["teldefinitie"]
    assert "neveninschrijvingen" in _get("p03hoinschr")["teldefinitie"]


_VIER = pd.DataFrame({"AANTAL LEERLINGEN": [4, 4, 25]})
_MIN_EEN = pd.DataFrame({"AANTAL_INGESCHREVENEN": [-1, 12, 30]})


@pytest.mark.usefixtures("zonder_scopegrens")
def test_publicatieregel_wordt_meegegeven_als_de_data_hem_volgt():
    [regel] = _get("01voins-v1", _VIER)["publicatieregels"]

    assert regel["bereik"] == [1, 4]
    assert regel["gepubliceerd_als"] == 4
    assert regel["bronpassage"]


@pytest.mark.parametrize("dataset", ["p01hoinges", "p02ho1ejrs", "p03hoinschr"])
def test_publicatieregel_ontbreekt_als_de_data_kleine_aantallen_als_min_een_geeft(dataset):
    """#407: de HO-beschrijving noemt '1-4 als 4', de bestanden gebruiken -1."""
    result = _get(dataset, _MIN_EEN)

    assert "publicatieregels" not in result
    assert "-1" in result["publicatieregels_niet_gebruikt"]


@pytest.mark.usefixtures("zonder_scopegrens")
def test_publicatieregel_niet_gebruikt_bij_1_tot_3_cellen():
    assert "publicatieregels" not in _get("01voins-v1", pd.DataFrame({"AANTAL LEERLINGEN": [4, 2, 25]}))


def test_publicatieregel_maakt_4_niet_leeg():
    # De 1-4-regel is geen sentinel: een gepubliceerde 4 blijft 4, alleen -1 wordt leeg.
    df = pd.DataFrame({"AANTAL_INGESCHREVENEN": [4, -1, 12]})
    result = _get("p01hoinges", df)

    vier, leeg, twaalf = (r["AANTAL_INGESCHREVENEN"] for r in result["preview"])
    assert (vier, twaalf) == (4, 12)
    assert math.isnan(leeg)


def test_get_duo_data_defines_opleidingsvorm_codes():
    kolom = next(k for k in _get("p01hoinges")["kolommen"] if k["kolom"] == "OPLEIDINGSVORM")
    assert "DT = deeltijd" in kolom["definitie"]


@pytest.mark.usefixtures("zonder_scopegrens")
def test_get_duo_data_without_teldefinitie_omits_field():
    result = _get("zonder-selectie", pd.DataFrame({"AANTAL": [1]}))

    assert "teldefinitie" not in result
    assert "publicatieregels" not in result


def test_onleesbare_beschrijving_meldt_onbekend():
    entry = {"_notes_provenance": {"parse_status": "ongestructureerd", "parse_fouten": ["geen secties"]}}

    assert set(duo_meta.metadata(entry)) == {"metadata_onbekend"}


def test_gedeeltelijk_gelezen_beschrijving_geeft_wat_er_is_en_meldt_onbekend():
    entry = {
        "_teldefinitie": {"selectie": "Leerlingen:  op 1 oktober."},
        "_notes_provenance": {"parse_status": "gedeeltelijk"},
    }

    velden = duo_meta.metadata(entry)

    assert velden["teldefinitie"] == "Leerlingen: op 1 oktober."
    assert "metadata_onbekend" in velden


def test_dataset_details_includes_teldefinitie_for_duo():
    entry = {**duo_meta.record("p01hoinges"), "leverancier": "DUO", "_resources": [{"naam": "hbo"}]}
    with patch("tools.catalog._cbs", return_value=[]), patch("tools.catalog._rio_duo", return_value=[entry]):
        result = json.loads(dataset_details("p01hoinges"))

    assert "natuurlijke personen" in result["teldefinitie"]
    assert result["publicatieregels"][0]["gepubliceerd_als"] == 4


# --- #402: een teldefinitie over een ander onderwijstype dan het bestand ---


@pytest.mark.usefixtures("zonder_scopegrens")
def test_voprognoses_krijgt_geen_basisonderwijstekst():
    """Audit 14 §3.4: de DUO-beschrijving van voprognoses is een kopie van de po-tekst."""
    result = _get("voprognoses", pd.DataFrame({"JAAR": [2030], "AANTAL": [10.5]}))

    assert "teldefinitie" not in result
    assert "basisonderwijs" in result["teldefinitie_niet_gebruikt"]
    assert "VO" in result["teldefinitie_niet_gebruikt"]


@pytest.mark.parametrize("dataset", ["wpoprognoses", "pogemeente", "p01hoinges", "weccluster-v1"])
def test_teldefinitie_over_het_eigen_onderwijstype_blijft(dataset):
    assert duo_meta.teldefinitie(duo_meta.record(dataset))


@pytest.mark.usefixtures("zonder_scopegrens")
def test_dataset_details_volgt_dezelfde_regel():
    details = json.loads(dataset_details("voprognoses"))

    assert "teldefinitie" not in details
    assert "teldefinitie_niet_gebruikt" in details


@pytest.mark.usefixtures("zonder_scopegrens")
def test_telling_blok_onder_een_voprognoses_antwoord_noemt_geen_basisonderwijs():
    key = _get("voprognoses", pd.DataFrame({"JAAR": [2030], "AANTAL": [10.5]}))["data_key"]

    with patch("agent.telling.catalogus_titel", side_effect=lambda d: d):
        assert "basisonderwijs" not in telling_blok([json.dumps({"data_key": key})])


def test_zonder_onderwijstype_wordt_niets_weggelaten():
    entry = {"_teldefinitie": {"selectie": "Leerlingen in het basisonderwijs."}}

    assert duo_meta.teldefinitie(entry) == "Leerlingen in het basisonderwijs."


def test_html_regeleinden_uit_de_duo_beschrijving_worden_spaties():
    entry = {"_teldefinitie": {"selectie": "Het aantal bestaat uit: <br> • bol <br/> • bbl <BR>  Per instelling."}}

    assert duo_meta.teldefinitie(entry) == "Het aantal bestaat uit: • bol • bbl Per instelling."
