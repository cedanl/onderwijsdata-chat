"""De app zet zelf onder het antwoord wat DUO telt en wanneer een totaal een ondergrens is (#321)."""

import json

import pandas as pd
import pytest

from agent.telling import met_telling, telling_blok
from tools import duo, store
from tools.store import KeyMeta

_PERSONEN = "Ingeschrevenen: van alle inschrijvingen op de peildatum 1 oktober worden de hoofdinschrijvingen bepaald."
_INSCHRIJVINGEN = "Inschrijvingen: voor de inschrijvingen op de peildatum 1 oktober worden zowel de hoofd- als ..."


def _beurt(*keys: str) -> list[str]:
    return [json.dumps({"data_key": k}) for k in keys]


@pytest.fixture(autouse=True)
def _keys():
    store.clear()
    store.put(
        "duo:p01hoinges:0",
        pd.DataFrame({"AANTAL": [26370, -1]}),
        KeyMeta(bron="duo", dataset="p01hoinges", teldefinitie=_PERSONEN),
    )
    store.put(
        "duo:p03hoinschr:0",
        pd.DataFrame({"AANTAL": [28889]}),
        KeyMeta(bron="duo", dataset="p03hoinschr", teldefinitie=_INSCHRIJVINGEN),
    )
    store.put("cbs:85423NED", pd.DataFrame({"AANTAL": [341720]}), KeyMeta(bron="cbs", dataset="85423NED"))
    yield
    store.clear()


def _selectie(met_minus_een: bool) -> str:
    """Een afgeleide key zoals query_data hem maakt, met of zonder onderdrukte cellen."""
    store.derive("duo:p01hoinges:0", "duo:p01hoinges:0:abc", pd.DataFrame({"AANTAL": [26370]}))
    cellen = pd.DataFrame({"AANTAL": [1 if met_minus_een else 0]})
    duo.record_sentinel_cells("duo:p01hoinges:0:abc", cellen)
    return "duo:p01hoinges:0:abc"


def test_blok_noemt_de_teldefinitie_uit_de_metadata():
    blok = telling_blok(_beurt("duo:p01hoinges:0"))
    assert blok.startswith("**Telling**") and _PERSONEN in blok and "p01hoinges" in blok


def test_vergelijking_van_p01_en_p03_noemt_beide_definities_een_keer():
    blok = telling_blok(_beurt("duo:p01hoinges:0", "duo:p03hoinschr:0", "duo:p01hoinges:0"))
    assert blok.count(_PERSONEN) == 1 and blok.count(_INSCHRIJVINGEN) == 1


def test_afgeleide_selectie_met_onderdrukte_cellen_geeft_de_ondergrensregel():
    blok = telling_blok(_beurt(_selectie(met_minus_een=True)))
    assert "Ondergrens" in blok and "p01hoinges" in blok and "-1" in blok and _PERSONEN in blok


def test_selectie_zonder_onderdrukte_cellen_geeft_geen_ondergrensregel():
    assert "Ondergrens" not in telling_blok(_beurt(_selectie(met_minus_een=False)))


def test_hele_resource_met_minus_een_is_geen_ondergrens():
    # #179: een telling over de hele resource zegt niets over een gefilterd totaal.
    assert "Ondergrens" not in telling_blok(_beurt("duo:p01hoinges:0"))


def test_cbs_en_zonder_data_geven_geen_blok():
    assert telling_blok(_beurt("cbs:85423NED")) == ""
    assert telling_blok([]) == ""


def test_blok_is_onafhankelijk_van_de_formulering_van_het_model():
    # Een parafrase van de DUO-tekst gaf vals alarm (#239); nu is het blok altijd hetzelfde.
    beurt = _beurt("duo:p01hoinges:0")
    eerste = met_telling("Het waren 26.370 personen op peildatum.", beurt)
    tweede = met_telling("In totaal 26.370 inschrijvingen op de peildatum.", beurt)
    assert eerste.split("\n\n", 1)[1] == tweede.split("\n\n", 1)[1]


def test_leeg_antwoord_blijft_leeg():
    assert met_telling("  ", _beurt("duo:p01hoinges:0")) == "  "
