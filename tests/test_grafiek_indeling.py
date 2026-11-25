"""De titel van een grafiek noemt de indeling en de bron uit de metadata, niet uit het model (#1232)."""

import pandas as pd
import plotly.io as pio
import pytest

from agent.figuurbron import figuurbron
from agent.report_figuren import _maak
from tools import store
from tools.indeling import indeling_in_woorden, indelingsregel, titel_met_indeling
from tools.plot import create_plot
from tools.store import KeyMeta

_DUO_KEY = "duo:p01hoinges:sector"
_CBS_KEY = "cbs:85525NED:richting"


@pytest.fixture
def duo_sector():
    store.put(
        _DUO_KEY,
        pd.DataFrame([{"ONDERDEEL": "Economie", "AANTAL": 120}, {"ONDERDEEL": "Techniek", "AANTAL": 80}]),
        KeyMeta(bron="duo", dataset="p01hoinges"),
    )
    return _DUO_KEY


@pytest.fixture
def cbs_studierichting():
    store.put(
        _CBS_KEY,
        pd.DataFrame(
            [{"Studierichting": "Economie", "Studenten_1": 300}, {"Studierichting": "Zorg", "Studenten_1": 200}]
        ),
        KeyMeta(
            bron="cbs",
            dataset="85525NED",
            kolomtitels={"Studierichting": "Studierichting", "Studenten_1": "Studenten"},
        ),
    )
    return _CBS_KEY


def _titel(fig) -> str:
    return fig.layout.title.text


def test_duo_sector_noemt_indeling_en_bron(duo_sector):
    _, fig = create_plot(data_key=duo_sector, chart_type="bar", x="ONDERDEEL", y="AANTAL", title="Hbo-studenten")
    assert _titel(fig) == "Hbo-studenten per sector (DUO)"
    assert fig.layout.meta["indeling"] == "per sector (DUO)"


def test_duo_mbo_hoofdgroep_is_ook_sector():
    known = KeyMeta(bron="duo", dataset="p02mboinges")
    assert indeling_in_woorden(known, "HOOFDGROEP NAAM") == "per sector (DUO)"


def test_cbs_studierichting_uit_kolomtitels(cbs_studierichting):
    _, fig = create_plot(
        data_key=cbs_studierichting, chart_type="bar", x="Studierichting", y="Studenten_1", title="Hbo-studenten"
    )
    assert _titel(fig) == "Hbo-studenten per studierichting (CBS)"
    assert fig.layout.meta["indeling"] == "per studierichting (CBS)"


def test_cbs_titel_van_de_dimensie_telt_niet_de_kolomnaam():
    known = KeyMeta(bron="cbs", dataset="x", kolomtitels={"OpleidingsrichtingEnSector": "Opleidingsrichting en sector"})
    assert indeling_in_woorden(known, "OpleidingsrichtingEnSector", known.kolomtitels) == (
        "per opleidingsrichting en sector (CBS)"
    )


@pytest.mark.parametrize(
    ("titel", "verwacht"),
    [
        ("Hbo-studenten per sector", "Hbo-studenten per sector (DUO)"),
        ("Hbo-studenten (DUO)", "Hbo-studenten (DUO) per sector"),
        ("Hbo-studenten per sector (DUO)", "Hbo-studenten per sector (DUO)"),
        ("Hbo-studenten per Sector, bron duo", "Hbo-studenten per Sector, bron duo"),
    ],
)
def test_niets_dubbel(titel, verwacht):
    known = KeyMeta(bron="duo", dataset="p01hoinges")
    assert titel_met_indeling(titel, known, "ONDERDEEL") == verwacht


def test_niets_dubbel_in_de_grafiek(duo_sector):
    _, fig = create_plot(
        data_key=duo_sector, chart_type="bar", x="ONDERDEEL", y="AANTAL", title="Hbo-studenten per sector (DUO)"
    )
    assert _titel(fig) == "Hbo-studenten per sector (DUO)"


def test_zonder_data_key_blijft_de_titel():
    rijen = [{"ONDERDEEL": "Economie", "AANTAL": 1}, {"ONDERDEEL": "Techniek", "AANTAL": 2}]
    _, fig = create_plot(rijen, "bar", "ONDERDEEL", "AANTAL", "Hbo-studenten")
    assert _titel(fig) == "Hbo-studenten"
    assert "indeling" not in fig.layout.meta


@pytest.mark.parametrize("x", ["JAAR", "PROVINCIE"])
def test_geen_indeling_op_jaren_of_regio(x):
    key = f"duo:p01hoinges:{x}"
    store.put(key, pd.DataFrame([{x: "a", "AANTAL": 1}, {x: "b", "AANTAL": 2}]), KeyMeta(bron="duo", dataset="x"))
    _, fig = create_plot(data_key=key, chart_type="bar", x=x, y="AANTAL", title="Hbo-studenten")
    assert _titel(fig) == "Hbo-studenten"
    assert "indeling" not in fig.layout.meta


def test_cbs_regio_is_geen_indeling():
    known = KeyMeta(bron="cbs", dataset="x", kolomtitels={"RegioS": "Regio's"})
    assert indeling_in_woorden(known, "RegioS", known.kolomtitels) is None
    assert indeling_in_woorden(None, "ONDERDEEL") is None


def test_csv_kop_noemt_dezelfde_woorden(duo_sector):
    _, fig = create_plot(data_key=duo_sector, chart_type="bar", x="ONDERDEEL", y="AANTAL", title="Hbo-studenten")
    assert indelingsregel("per sector (DUO)") in fig.layout.meta["herkomst"]


def test_rapportfiguur_noemt_dezelfde_woorden(duo_sector):
    stap = {
        "tool": "create_plot",
        "arguments": {"data_key": duo_sector, "chart_type": "bar", "x": "ONDERDEEL", "y": "AANTAL", "title": "T"},
        "keys": [duo_sector],
    }
    vast = _maak(stap)
    assert vast is not None
    assert vast.indeling == "per sector (DUO)"
    assert pio.from_json(vast.figure_json).layout.title.text == "T per sector (DUO)"
    regel = figuurbron(vast.data_key, vast.indeling)
    assert regel is not None
    assert regel["tekst"].endswith(", " + indelingsregel("per sector (DUO)"))


def test_rapportfiguur_zonder_indeling_houdt_de_bronregel(duo_sector):
    zonder = figuurbron(duo_sector)
    assert zonder is not None
    assert "indeling" not in zonder["tekst"]
