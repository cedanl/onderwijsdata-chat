"""Het rapport van een kaartvraag bevat de kaart (#648): sinds #993 (besluit 18-11) als kaart uit het gesprek die de
gebruiker koos, opnieuw gemaakt op de server; het rapportmodel tekent zelf geen kaart. De kaart komt als `choroplethmap`
in de spec, zonder harde controlefout. `kaarten_in_gesprek` (de kaarten per data_key) blijft voor het beurtbewijs."""

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from agent import report
from agent.kaarten import kaarten_in_gesprek
from agent.loop import LoopResult, ToolCall
from agent.probleem import harde
from tests.rapportfiguren import figuur_in_gesprek
from tools import store
from tools.plot import create_choropleth_map
from tools.schemas import TOOL_CREATE_CHOROPLETH_MAP, TOOL_CREATE_PLOT

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


def test_de_rapportrun_tekent_geen_kaart_of_grafiek():
    """Besluit 18-11 (#993): het rapportmodel tekent zelf geen figuren; een kaart uit het gesprek komt als vaste figuur."""
    namen = [s["function"]["name"] for s in report._REPORT_TOOLS]
    assert TOOL_CREATE_CHOROPLETH_MAP not in namen and TOOL_CREATE_PLOT not in namen


def test_de_rapportprompt_noemt_de_kaarttool_niet():
    prompt = (Path(report.__file__).parent.parent / "prompts" / "report.md").read_text()
    assert TOOL_CREATE_CHOROPLETH_MAP not in prompt and TOOL_CREATE_PLOT not in prompt


def _rapport(sessie, monkeypatch, antwoord: str = _ANTWOORD, figuren: tuple[str, ...] = ()):
    """Het rapport met een nepmodel; geeft de spec (of de fout), de systeemprompt en de harde problemen."""
    prompts: list[str] = []
    harde_problemen: list[list[str]] = []

    async def loop(messages, *, check, tools, **_):
        prompts.append(messages[0]["content"])
        assert TOOL_CREATE_CHOROPLETH_MAP not in [t["function"]["name"] for t in tools]
        problemen = check(antwoord, [])
        harde_problemen.append(harde(problemen))
        return LoopResult(text=antwoord, problems=problemen)

    monkeypatch.setattr(report, "tool_loop", loop)
    try:
        uitkomst = asyncio.run(report.generate(sessie, _stil, figuren=figuren))
    except report.RapportGeweigerd as fout:
        uitkomst = fout
    return uitkomst, prompts[0], harde_problemen[0]


def test_een_gekozen_kaart_uit_het_gesprek_komt_als_kaart_in_het_rapport(sessie, monkeypatch):
    figuur_id = figuur_in_gesprek(sessie, TOOL_CREATE_CHOROPLETH_MAP, _KAART)

    spec, prompt, harde_problemen = _rapport(sessie, monkeypatch, figuren=(figuur_id,))

    [visualisatie] = spec.visualisaties
    figuur = json.loads(visualisatie["figure_json"])
    assert [t["type"] for t in figuur["data"]] == ["choroplethmap"]
    assert sorted(figuur["data"][0]["locations"]) == sorted(_PROVINCIES)
    assert visualisatie["titel"] == "Mbo-studenten per provincie"
    assert "## Vaste figuren" in prompt and "choroplethmap" in prompt.rsplit("## Vaste figuren", 1)[1]
    assert harde_problemen == []


def test_zonder_gekozen_figuur_heeft_het_rapport_geen_kaart(sessie, monkeypatch):
    """Besluit 18-11: zonder keuze geen figuren, ook niet als het gesprek een kaart had."""
    figuur_in_gesprek(sessie, TOOL_CREATE_CHOROPLETH_MAP, _KAART)
    antwoord = json.loads(_ANTWOORD) | {"visualisaties": []}

    spec, prompt, _ = _rapport(sessie, monkeypatch, antwoord=json.dumps(antwoord))

    assert spec.visualisaties == []
    assert "de gebruiker koos geen figuren" in prompt


@pytest.mark.parametrize("argumenten", ["geen json", "[1, 2]", '{"data_key": 7}', None])
def test_een_onleesbare_kaartaanroep_wordt_overgeslagen(sessie, argumenten):
    sessie["turns"][0]["tool_calls"] = [{"name": TOOL_CREATE_CHOROPLETH_MAP, "arguments": argumenten}]
    assert kaarten_in_gesprek(sessie) == {}


def test_een_getal_uit_de_kaarttitel_van_het_gesprek_is_geen_bewijs(sessie, monkeypatch):
    """Een titel is tekst van het model, geen data (#211): een getal dat alleen daarin staat, blijft een harde
    fout in de controle van het rapport (#175, #515), en het rapport wordt geweigerd. De prompt noemt de titel wel,
    om de figuur te herkennen (#993), maar het bewijs van de figuur zijn haar waarden, zonder titel."""
    figuur_id = figuur_in_gesprek(sessie, TOOL_CREATE_CHOROPLETH_MAP, {**_KAART, "title": "Per provincie, samen 98765"})
    antwoord = json.loads(_ANTWOORD) | {"conclusie": "Samen zijn er 98765 mbo-studenten in deze provincies."}

    fout, _, harde_problemen = _rapport(sessie, monkeypatch, antwoord=json.dumps(antwoord), figuren=(figuur_id,))

    assert isinstance(fout, report.RapportGeweigerd)
    assert any("98.765" in str(p) for p in harde_problemen)


def test_een_kaart_die_het_rapportmodel_toch_aanroept_komt_niet_in_het_rapport(sessie, monkeypatch):
    """Het model heeft geen kaarttool; noemt het er toch een (de loop voert elke naam uit), dan valt de figuur weg."""

    async def loop(messages, *, on_tool_result, **_):
        melding, figuur = create_choropleth_map(
            data_key=_KEY, location_col="PROVINCIE", value_col="AANTAL", title=_KAART["title"]
        )
        call = ToolCall(id="k", name=TOOL_CREATE_CHOROPLETH_MAP, arguments=json.dumps(_KAART), args=dict(_KAART))
        await on_tool_result(call, melding, figuur)
        return LoopResult(text=json.dumps(json.loads(_ANTWOORD) | {"visualisaties": []}))

    monkeypatch.setattr(report, "tool_loop", loop)
    spec = asyncio.run(report.generate(sessie, _stil))

    assert spec.visualisaties == []


def test_een_kaartaanroep_die_niets_tekende_komt_niet_in_de_prompt(sessie):
    """De beurt bewaart wat het model vroeg, ook een geweigerde aanroep; alleen een kaart met een figuur telt."""
    mislukt = {**_KAART, "value_col": "BESTAAT_NIET"}
    sessie["turns"] = [_kaartbeurt(mislukt)]
    assert sessie["turns"][0]["figures"] == []
    assert kaarten_in_gesprek(sessie) == {}


def test_naast_een_mislukte_aanroep_telt_de_kaart_die_wel_tekende(sessie):
    gelukt = _kaartbeurt(_KAART)
    mislukt = _kaartbeurt({**_KAART, "value_col": "BESTAAT_NIET"})
    sessie["turns"] = [{**gelukt, "tool_calls": [*gelukt["tool_calls"], *mislukt["tool_calls"]]}]
    assert kaarten_in_gesprek(sessie)[_KEY]["value_col"] == "AANTAL"


async def _stil(event):
    pass
