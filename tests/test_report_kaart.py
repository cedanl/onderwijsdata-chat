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


def _kaartbeurt(kaart: dict) -> dict:
    """Een beurt zoals de chatroute haar bewaart: de aanroep van het model en de figuur die ze tekende."""
    _, figuur = create_choropleth_map(
        data_key=kaart["data_key"],
        location_col=kaart["location_col"],
        value_col=kaart["value_col"],
        title=kaart.get("title", ""),
    )
    return {
        "question": "Maak een kaart met het aantal mbo-studenten per provincie",
        "tool_calls": [{"name": TOOL_CREATE_CHOROPLETH_MAP, "arguments": json.dumps(kaart)}],
        "figures": [figuur] if figuur is not None else [],
    }


@pytest.fixture
def sessie():
    store.put(_KEY, pd.DataFrame({"PROVINCIE": ["Utrecht", "Drenthe", "Groningen"], "AANTAL": [41230, 12040, 20500]}))
    return {"data_keys": [_KEY], "turns": [_kaartbeurt(_KAART)]}


def test_de_rapportrun_kan_een_kaart_maken():
    namen = [s["function"]["name"] for s in report._REPORT_TOOLS]
    assert sorted(namen) == sorted(["query_data", "create_plot", TOOL_CREATE_CHOROPLETH_MAP])


def test_de_rapportprompt_noemt_de_kaarttool():
    prompt = (Path(report.__file__).parent.parent / "prompts" / "report.md").read_text()
    assert TOOL_CREATE_CHOROPLETH_MAP in prompt


def _systeemprompt(sessie, monkeypatch) -> str:
    prompts: list[str] = []

    async def loop(messages, **_):
        prompts.append(messages[0]["content"])
        return LoopResult(text=_ANTWOORD)

    monkeypatch.setattr(report, "tool_loop", loop)
    asyncio.run(report.generate(sessie, _stil))
    return prompts[0]


def test_de_kaart_uit_het_gesprek_staat_bij_haar_dataset_in_de_prompt(sessie, monkeypatch):
    """Het model ziet welke kaart het gesprek van deze data tekende, met haar kolommen."""
    blok = _systeemprompt(sessie, monkeypatch).split(f"### {_KEY}", 1)[1]
    assert f"Kaart in het gesprek: {TOOL_CREATE_CHOROPLETH_MAP} " in blok
    assert '"location_col": "PROVINCIE"' in blok and '"value_col": "AANTAL"' in blok


def test_de_kaartregel_noemt_alleen_data_key_kolommen_en_niveau(sessie, monkeypatch):
    """De titel is tekst van het model en `data` zijn rijen buiten de store (#211): geen van beide hoort in de
    prompt, anders herhaalt het rapport ze en komen ze via het toolresultaat toch als bewijs terug."""
    kaart = {**_KAART, "level": "provincie", "title": "Samen 98765 studenten", "data": [{"PROVINCIE": "X"}]}
    sessie["turns"][0]["tool_calls"] = [{"name": TOOL_CREATE_CHOROPLETH_MAP, "arguments": json.dumps(kaart)}]

    regel = _systeemprompt(sessie, monkeypatch).split("Kaart in het gesprek: ", 1)[1].split("\n", 1)[0]

    argumenten = json.loads(regel.removeprefix(f"{TOOL_CREATE_CHOROPLETH_MAP} "))
    assert argumenten == {"data_key": _KEY, "location_col": "PROVINCIE", "value_col": "AANTAL", "level": "provincie"}


def test_zonder_kaart_in_het_gesprek_geen_kaartregel(sessie, monkeypatch):
    sessie["turns"] = [{"question": "Hoeveel?", "tool_calls": [{"name": "query_data", "arguments": "{}"}]}]
    blok = _systeemprompt(sessie, monkeypatch).split(f"### {_KEY}", 1)[1]
    assert "Kaart in het gesprek" not in blok


@pytest.mark.parametrize("argumenten", ["geen json", "[1, 2]", '{"data_key": 7}', None])
def test_een_onleesbare_kaartaanroep_wordt_overgeslagen(sessie, argumenten):
    sessie["turns"][0]["tool_calls"] = [{"name": TOOL_CREATE_CHOROPLETH_MAP, "arguments": argumenten}]
    assert report._kaarten_in_gesprek(sessie) == {}


def test_een_getal_uit_de_kaarttitel_van_het_gesprek_is_geen_bewijs(sessie, monkeypatch):
    """Een titel is tekst van het model, geen data (#211): een getal dat alleen daarin staat, blijft een harde
    fout in de controle van het rapport (#175, #515), en het rapport wordt geweigerd."""
    titel = "Mbo-studenten per provincie, samen 98765"
    sessie["turns"] = [_kaartbeurt({**_KAART, "title": titel})]
    antwoord = json.loads(_ANTWOORD) | {"conclusie": "Samen zijn er 98765 mbo-studenten in deze provincies."}
    prompts: list[str] = []
    harde_problemen: list[list[str]] = []

    async def loop(messages, *, on_tool_result, check, **_):
        prompts.append(messages[0]["content"])
        # Het rapport tekent de kaart met de kolommen uit de kaartregel en een eigen titel.
        melding, figuur = create_choropleth_map(
            data_key=_KEY, location_col="PROVINCIE", value_col="AANTAL", title="Mbo-studenten per provincie"
        )
        call = ToolCall(id="k", name=TOOL_CREATE_CHOROPLETH_MAP, arguments="{}", args={"data_key": _KEY})
        await on_tool_result(call, melding, figuur)
        problemen = check(json.dumps(antwoord), [melding])
        harde_problemen.append(harde(problemen))
        return LoopResult(text=json.dumps(antwoord), problems=problemen)

    monkeypatch.setattr(report, "tool_loop", loop)
    with pytest.raises(report.RapportGeweigerd):
        asyncio.run(report.generate(sessie, _stil))

    assert "98765" not in prompts[0]
    assert any("98.765" in str(p) for p in harde_problemen[0])


def test_een_kaartaanroep_die_niets_tekende_komt_niet_in_de_prompt(sessie):
    """De beurt bewaart wat het model vroeg, ook een geweigerde aanroep; alleen een kaart met een figuur telt."""
    mislukt = {**_KAART, "value_col": "BESTAAT_NIET"}
    sessie["turns"] = [_kaartbeurt(mislukt)]
    assert sessie["turns"][0]["figures"] == []
    assert report._kaarten_in_gesprek(sessie) == {}


def test_naast_een_mislukte_aanroep_telt_de_kaart_die_wel_tekende(sessie):
    gelukt = _kaartbeurt(_KAART)
    mislukt = _kaartbeurt({**_KAART, "value_col": "BESTAAT_NIET"})
    sessie["turns"] = [{**gelukt, "tool_calls": [*gelukt["tool_calls"], *mislukt["tool_calls"]]}]
    assert report._kaarten_in_gesprek(sessie)[_KEY]["value_col"] == "AANTAL"


def test_de_kaart_van_de_rapportrun_komt_als_kaart_in_het_rapport(sessie, monkeypatch):
    meldingen: list[str] = []
    harde_problemen: list[list[str]] = []

    async def loop(messages, *, on_tool_result, check, **_):
        melding, figuur = create_choropleth_map(
            data_key=_KEY, location_col="PROVINCIE", value_col="AANTAL", title=_KAART["title"]
        )
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
