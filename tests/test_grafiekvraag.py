"""#221: een grafiekvraag met data levert een grafiek, of het antwoord zegt waarom niet."""

import json

import pytest

from agent.grafiekvraag import gevraagde_typen, ontbrekende_grafiek

_DATA = json.dumps({"data_key": "duo_x__abc", "rows": 3})
_STAAF = "Staafgrafiek 'Eerstejaars per college' aangemaakt (3 datapunten)."
_LIJN = "Lijngrafiek 'WO-trend' aangemaakt (8 datapunten)."


@pytest.mark.parametrize(
    ("vraag", "typen"),
    [
        ("Maak een staafgrafiek van de eerstejaars per college", {"bar"}),
        ("Toon de WO-trend als lijngrafiek", {"line"}),
        ("Kun je dit in een grafiek zetten?", {"auto"}),
        ("Visualiseer de instroom per sector", {"auto"}),
        ("Maak een taartdiagram en een staafgrafiek", {"pie", "bar"}),
        ("Maak van de staafgrafiek een lijngrafiek", {"line"}),
    ],
)
def test_grafiekverzoek_en_type_uit_de_vraag(vraag, typen):
    assert gevraagde_typen(vraag) == typen


@pytest.mark.parametrize(
    "vraag",
    [
        "Hoeveel eerstejaars had de VU in 2023?",  # #85: geen verzoek, geen grafiek
        "Wat betekent de grafiek?",  # gaat over een bestaande grafiek
        "Geef de cijfers zonder grafiek",
        "Kun je die cijfers staven met een bron?",
        "Waarom daalt de lijn in de grafiek?",
    ],
)
def test_geen_grafiekverzoek(vraag):
    assert gevraagde_typen(vraag) == set()
    assert ontbrekende_grafiek(vraag, "Antwoord.", [_DATA]) == []


def test_grafiekcode_als_tekst_is_een_probleem():
    tekst = "Hier is de grafiek:\n```python\nfig = px.bar(df, x='college', y='n')\nfig.show()\n```"
    problemen = ontbrekende_grafiek("Maak een staafgrafiek van de eerstejaars per college", tekst, [_DATA])
    assert any("grafiekcode" in p for p in problemen)
    assert any("chart_type 'bar'" in p for p in problemen)


def test_placeholder_zonder_grafiek_is_een_probleem():
    """Audit 11: "Staafgrafiek …" als tekst, zonder grafiek."""
    problemen = ontbrekende_grafiek("Maak een staafgrafiek", "Staafgrafiek …\n\nDe instroom steeg.", [_DATA])
    assert len(problemen) == 1 and "staafgrafiek" in problemen[0].melding


def test_data_uit_een_eerdere_beurt_telt_mee():
    assert ontbrekende_grafiek("Zet dit in een grafiek", "De instroom steeg.", [], ["duo_x__abc"])


def test_grafiek_gemaakt_is_in_orde():
    assert ontbrekende_grafiek("Maak een staafgrafiek per college", "Zie de grafiek.", [_DATA, _STAAF]) == []
    assert ontbrekende_grafiek("Laat het in een grafiek zien", "Zie de grafiek.", [_DATA, _LIJN]) == []


def test_uitleg_waarom_geen_grafiek_is_in_orde():
    """#199-kant: één datapunt zonder staaf, of geen data: het antwoord zegt het."""
    tekst = "Er is één datapunt (2023: 1.234), daar is geen zinvolle grafiek van te maken."
    assert ontbrekende_grafiek("Maak een lijngrafiek", tekst, [_DATA, "Geen grafiek gemaakt: één datapunt."]) == []


def test_zonder_data_alleen_de_code_telt():
    assert ontbrekende_grafiek("Maak een staafgrafiek van de leerlingen per school", "Die data is er niet.", []) == []


def test_ander_type_dan_gevraagd():
    """Audit 10: lijngrafiek gevraagd, staafgrafiek gekregen."""
    problemen = ontbrekende_grafiek("Toon de WO-trend als lijngrafiek", "Zie de grafiek.", [_DATA, _STAAF])
    assert len(problemen) == 1 and "chart_type 'line'" in problemen[0]
    # Twee typen gevraagd: geen eis over welk type.
    assert ontbrekende_grafiek("Maak een taartdiagram of staafgrafiek", "Zie de grafiek.", [_DATA, _STAAF]) == []


def test_melding_noemt_geen_toolnaam():
    """De gebruiker ziet de melding; toolnamen alleen in de opdracht aan het model (#215)."""
    for p in ontbrekende_grafiek("Toon als lijngrafiek", "fig.show()", [_DATA, _STAAF]):
        assert "create_plot" not in p.melding


def test_chatpad_roept_de_controle_aan():
    """De naad: de check die run() aan de toolloop geeft, moet een ontbrekende grafiek weigeren."""
    import asyncio
    import importlib
    from types import SimpleNamespace
    from unittest.mock import patch

    run_module = importlib.import_module("agent.run")  # agent.run is ook de naam van de functie
    meegegeven = {}

    async def nep_loop(history, **kwargs):
        meegegeven.update(kwargs)
        return SimpleNamespace(aborted="tools")

    async def emit(_event):
        pass

    vraag = [{"role": "user", "content": "Maak een staafgrafiek van de eerstejaars per college"}]
    with patch.object(run_module, "tool_loop", nep_loop):
        asyncio.run(run_module.run(vraag, session={}, emit=emit))
    problemen = meegegeven["check"]("fig = px.bar(df)\nfig.show()", [_DATA])
    assert any("grafiekcode" in str(p) for p in problemen)
