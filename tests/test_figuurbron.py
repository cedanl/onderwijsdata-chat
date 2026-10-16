"""De bronregel onder een grafiek in het rapport komt uit code, met een link naar de bron (#569)."""

import asyncio
from unittest.mock import patch

import pandas as pd
import plotly.graph_objects as go
import pytest

from agent import report
from agent.figuurbron import figuurbron
from agent.loop import LoopResult, ToolCall
from agent.report import _parse_spec_from_response
from tools import store
from tools.catalog import documentatie_url
from tools.store import KeyMeta

_TITELS = {"85423NED": "Hoger onderwijs; ingeschrevenen", "p01hoinges": "Ingeschrevenen hoger onderwijs"}
_URLS = {
    "85423NED": "https://opendata.cbs.nl/ODataApi/OData/85423NED",
    "p01hoinges": "https://onderwijsdata.duo.nl/dataset/p01hoinges",
}


@pytest.fixture
def catalogus():
    with (
        patch("agent.selectie.bron_titel", side_effect=lambda d: _TITELS.get(d, d)),
        patch("agent.figuurbron.documentatie_url", side_effect=_URLS.get),
        patch("agent.selectie.tabelbestanden", return_value=[]),
    ):
        yield


def _cbs(key: str = "cbs:85423NED", statussen=("Voorlopig", "Definitief")) -> None:
    df = pd.DataFrame({"Perioden": ["2019SJ00", "2024SJ00"], "Periodestatus": list(statussen), "Totaal": [1, 2]})
    store.put(key, df, KeyMeta(bron="cbs", dataset="85423NED", schooljaren=(2019, 2024)))


def test_cbs_regel_met_titel_id_periode_status_en_link(catalogus):
    _cbs()

    assert figuurbron("cbs:85423NED") == {
        "bron": "CBS",
        "dataset": "85423NED",
        "tekst": "CBS · Hoger onderwijs; ingeschrevenen (85423NED), 2019/20 t/m 2024/25, status Definitief/Voorlopig",
        "url": "https://opendata.cbs.nl/ODataApi/OData/85423NED",
    }


def test_afgeleide_key_noemt_de_bron_en_de_periode_van_de_selectie(catalogus):
    # De grafiek toont de selectie, niet de hele geladen dataset: de periode is die van de getekende rijen.
    _cbs()
    store.derive(
        "cbs:85423NED",
        "cbs:85423NED:abc",
        pd.DataFrame({"Periodestatus": ["Voorlopig"], "Totaal": [2]}),
        schooljaren=(2024,),
    )

    bron = figuurbron("cbs:85423NED:abc") or {}

    assert bron["tekst"] == "CBS · Hoger onderwijs; ingeschrevenen (85423NED), 2024/25, status Voorlopig"
    assert bron["url"] == "https://opendata.cbs.nl/ODataApi/OData/85423NED"


def test_duo_regel_noemt_het_bestand_als_de_dataset_er_meer_heeft(catalogus):
    store.put(
        "duo:p01hoinges:3",
        pd.DataFrame({"STUDIEJAAR": [2023], "AANTAL": [5]}),
        KeyMeta(bron="duo", dataset="p01hoinges", resource=3, schooljaren=(2023,)),
    )
    with (
        patch("agent.selectie.tabelbestanden", return_value=[(1, "hbo"), (3, "wo")]),
        patch("agent.selectie.resource_titel", return_value="Ingeschrevenen wo"),
    ):
        bron = figuurbron("duo:p01hoinges:3") or {}

    assert bron["tekst"] == "DUO · Ingeschrevenen hoger onderwijs (p01hoinges), bestand Ingeschrevenen wo, 2023/24"
    assert bron["url"] == "https://onderwijsdata.duo.nl/dataset/p01hoinges"


def test_zonder_periode_of_status_alleen_bron_en_id(catalogus):
    store.put("rio:erkenningen", pd.DataFrame({"a": [1]}), KeyMeta(bron="rio", dataset="erkenningen"))

    assert figuurbron("rio:erkenningen") == {
        "bron": "RIO",
        "dataset": "erkenningen",
        "tekst": "RIO · erkenningen (erkenningen)",
        "url": None,
    }


@pytest.mark.parametrize("data_key", [None, "", "cbs:onbekend", 42])
def test_zonder_herleidbare_bron_geen_regel(catalogus, data_key):
    assert figuurbron(data_key) is None


def test_de_link_komt_uit_de_catalogus_en_is_altijd_https():
    # Tegen de echte catalogus: elke spelling van het ID vindt dezelfde link; een onbekend ID geen.
    assert documentatie_url("85423NED") == "https://opendata.cbs.nl/ODataApi/OData/85423NED"
    assert documentatie_url("cbs:85423ned") == "https://opendata.cbs.nl/ODataApi/OData/85423NED"
    assert (documentatie_url("p01hoinges") or "").startswith("https://")
    assert documentatie_url("bestaat-niet") is None


def test_een_link_die_geen_http_adres_is_blijft_weg():
    record = {"_cbs_id": "85423NED", "documentatie": {"url": "javascript:alert(1)"}}
    with patch("tools.catalog._ruw_record", return_value=record):
        assert documentatie_url("85423NED") is None


# ── In de spec: per figuur de regel, in volgorde ─────────────────────────────


def test_elke_visualisatie_krijgt_haar_eigen_bronregel():
    bronnen = [{"bron": "CBS", "dataset": "85423NED", "tekst": "CBS · A", "url": None}, None]
    spec = _parse_spec_from_response(
        '{"visualisaties": [{"titel": "Eerste"}, {"titel": "Tweede"}, {"titel": "Derde"}]}',
        figures_json=["fig1", "fig2", "fig3"],
        context={"topic": "V"},
        figuurbronnen=bronnen,
    )

    assert [v["bron"] for v in spec.visualisaties] == [bronnen[0], None, None]


def test_zonder_bronregels_blijft_de_spec_bruikbaar():
    spec = _parse_spec_from_response(
        '{"visualisaties": [{"titel": "T"}]}', figures_json=["fig"], context={"topic": "V"}
    )

    assert spec.visualisaties[0]["bron"] is None
    assert "bron" in spec.to_dict()["visualisaties"][0]


def test_de_rapportrun_leest_de_bron_uit_de_create_plot_aanroep(monkeypatch, catalogus):
    """Twee grafieken uit verschillende datasets: elk krijgt de regel van haar eigen data_key."""
    _cbs()
    store.put(
        "duo:p01hoinges:0",
        pd.DataFrame({"STUDIEJAAR": [2023], "AANTAL": [5]}),
        KeyMeta(bron="duo", dataset="p01hoinges", resource=0, schooljaren=(2023,)),
    )

    async def loop(messages, *, on_tool_result, check, **_):
        for key in ("cbs:85423NED", "duo:p01hoinges:0", "zonder-bron"):
            call = ToolCall(id=key, name="create_plot", arguments="{}", args={"data_key": key})
            await on_tool_result(call, "Grafiek aangemaakt", go.Figure())
        check("{}", [])
        return LoopResult(text='{"visualisaties": [{"titel": "Hbo"}, {"titel": "Wo"}]}')

    monkeypatch.setattr(report, "build_dataset_context", lambda session: {"datasets": [{"data_key": "cbs:85423NED"}]})
    monkeypatch.setattr(report, "_build_system_prompt", lambda context: "")
    monkeypatch.setattr(report, "report_problems", lambda *args: [])
    monkeypatch.setattr(report, "tool_loop", loop)

    async def emit(event):
        pass

    spec = asyncio.run(report.generate({}, emit))

    # Maximaal twee figuren (#_MAX_VISUALISATIES); de derde telt niet mee, ook niet voor de bronregels.
    bronnen = [v["bron"] or {} for v in spec.visualisaties]
    assert [b["dataset"] for b in bronnen] == ["85423NED", "p01hoinges"]
    assert bronnen[0]["tekst"].startswith("CBS · Hoger onderwijs; ingeschrevenen (85423NED)")
    assert bronnen[1]["url"] == "https://onderwijsdata.duo.nl/dataset/p01hoinges"
