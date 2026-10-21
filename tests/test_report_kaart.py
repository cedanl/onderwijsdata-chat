"""Het rapport van een kaartvraag bevat de kaart (#648): de kaarttool hoort bij de rapporttools, de prompt
noemt haar, en een kaart uit de rapportrun komt als `choroplethmap` in de spec, zonder harde controlefout."""

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from agent import report
from agent.dashboard import build_dataset_context
from agent.loop import LoopResult, ToolCall
from agent.probleem import harde
from agent.report_checks import report_problems
from tools import store
from tools.plot import create_choropleth_map
from tools.schemas import TOOL_CREATE_CHOROPLETH_MAP

_VORM = {"type": "Polygon", "coordinates": [[[5, 52], [6, 52], [6, 53], [5, 52]]]}
_PROVINCIES = {"PV20": "Groningen", "PV22": "Drenthe", "PV26": "Utrecht"}
_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {"type": "Feature", "id": code, "properties": {"statnaam": naam}, "geometry": _VORM}
        for code, naam in _PROVINCIES.items()
    ],
}
_KEY = "test:kaart648"
_KAART = {"data_key": _KEY, "location_col": "PROVINCIE", "value_col": "AANTAL", "title": "Mbo-studenten per provincie"}
_ANTWOORD = json.dumps(
    {
        "onderzoeksvraag": "Hoeveel mbo-studenten zijn er per provincie?",
        "beantwoordt": ["Het aantal mbo-studenten per provincie"],
        "beantwoordt_niet": ["De ontwikkeling over de jaren"],
        "visualisaties": [{"titel": "Mbo-studenten per provincie", "toelichting": "Utrecht kleurt het donkerst."}],
        "conclusie": "Utrecht heeft met 41230 de meeste mbo-studenten van deze provincies.",
    }
)


@pytest.fixture(autouse=True)
def _geojson():
    with patch("tools.plot._load_geojson", side_effect=lambda niveau: _GEOJSON):
        yield


@pytest.fixture
def sessie():
    store.put(_KEY, pd.DataFrame({"PROVINCIE": ["Utrecht", "Drenthe", "Groningen"], "AANTAL": [41230, 12040, 20500]}))
    return {
        "data_keys": [_KEY],
        "turns": [
            {
                "question": "Maak een kaart met het aantal mbo-studenten per provincie",
                "tool_calls": [{"name": TOOL_CREATE_CHOROPLETH_MAP, "arguments": json.dumps(_KAART)}],
            }
        ],
    }


def test_de_rapportrun_kan_een_kaart_maken():
    namen = [s["function"]["name"] for s in report._REPORT_TOOLS]
    assert sorted(namen) == sorted(["query_data", "create_plot", TOOL_CREATE_CHOROPLETH_MAP])


def test_de_rapportprompt_noemt_de_kaarttool():
    prompt = (Path(report.__file__).parent.parent / "prompts" / "report.md").read_text()
    assert TOOL_CREATE_CHOROPLETH_MAP in prompt


def test_de_kaart_uit_het_gesprek_staat_bij_haar_dataset_in_de_prompt(sessie, monkeypatch):
    """Het model ziet welke kaart het gesprek van deze data tekende, met kolommen en titel."""
    prompts: list[str] = []

    async def loop(messages, **_):
        prompts.append(messages[0]["content"])
        return LoopResult(text=_ANTWOORD)

    monkeypatch.setattr(report, "tool_loop", loop)
    asyncio.run(report.generate(sessie, _stil))

    blok = prompts[0].split(f"### {_KEY}", 1)[1]
    assert f"Kaart in het gesprek: {TOOL_CREATE_CHOROPLETH_MAP} " in blok
    assert '"location_col": "PROVINCIE"' in blok and '"value_col": "AANTAL"' in blok


def test_zonder_kaart_in_het_gesprek_geen_kaartregel(sessie, monkeypatch):
    sessie["turns"] = [{"question": "Hoeveel?", "tool_calls": [{"name": "query_data", "arguments": "{}"}]}]
    prompts: list[str] = []

    async def loop(messages, **_):
        prompts.append(messages[0]["content"])
        return LoopResult(text=_ANTWOORD)

    monkeypatch.setattr(report, "tool_loop", loop)
    asyncio.run(report.generate(sessie, _stil))

    blok = prompts[0].split(f"### {_KEY}", 1)[1]
    assert "Kaart in het gesprek" not in blok


@pytest.mark.parametrize("argumenten", ["geen json", "[1, 2]", '{"data_key": 7}', None])
def test_een_onleesbare_kaartaanroep_wordt_overgeslagen(sessie, argumenten):
    sessie["turns"][0]["tool_calls"] = [{"name": TOOL_CREATE_CHOROPLETH_MAP, "arguments": argumenten}]
    assert report._kaarten_in_gesprek(sessie) == {}


def test_de_kaart_van_de_rapportrun_komt_als_kaart_in_het_rapport(sessie, monkeypatch):
    meldingen: list[str] = []
    harde_problemen: list[list[str]] = []

    async def loop(messages, *, on_tool_result, check, **_):
        melding, figuur = create_choropleth_map(**_KAART)
        assert figuur is not None
        meldingen.append(melding)
        call = ToolCall(id="k", name=TOOL_CREATE_CHOROPLETH_MAP, arguments=json.dumps(_KAART), args=dict(_KAART))
        await on_tool_result(call, melding, figuur)
        # De controle van de rapportrun zelf, met haar eigen bronnen.
        problemen = check(_ANTWOORD, [melding])
        harde_problemen.append(harde(problemen))
        return LoopResult(text=_ANTWOORD, problems=problemen)

    monkeypatch.setattr(report, "tool_loop", loop)
    spec = asyncio.run(report.generate(sessie, _stil))

    assert 1 <= len(spec.visualisaties) <= report._MAX_VISUALISATIES
    figuur = json.loads(spec.visualisaties[0]["figure_json"])
    assert [t["type"] for t in figuur["data"]] == ["choroplethmap"]
    assert sorted(figuur["data"][0]["locations"]) == sorted(_PROVINCIES)
    assert harde_problemen == [[]]
    # Ook op de uiteindelijke spec, met de toolmelding en de datasetcontext als bron (zoals generate ze geeft).
    bronnen = [*meldingen, json.dumps(build_dataset_context(sessie), default=str)]
    figuren = [v["figure_json"] for v in spec.visualisaties]
    assert harde(report_problems(spec, figuren, bronnen)) == []


async def _stil(event):
    pass
