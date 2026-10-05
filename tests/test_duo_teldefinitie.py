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


@pytest.mark.parametrize("dataset", ["p01hoinges", "p02ho1ejrs", "p03hoinschr"])
def test_get_duo_data_geeft_de_publicatieregel(dataset):
    [regel] = _get(dataset)["publicatieregels"]

    assert regel["bereik"] == [1, 4]
    assert regel["gepubliceerd_als"] == 4
    assert regel["bronpassage"]


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
