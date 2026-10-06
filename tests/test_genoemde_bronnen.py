"""#334: een dataset-ID uit de vraag wordt in code opgelost, vóór elke zoekactie."""

from unittest.mock import patch

from agent.genoemde_bronnen import genoemde_bronnen
from agent.models import build_system

_CBS = [{"_cbs_id": "85525NED", "bron": "Gediplomeerden hoger onderwijs"}]
_RIO_DUO = [
    {"leverancier": "DUO", "_ckan_id": "mbo-studenten-per-instelling", "bron": "Studenten per mbo-instelling"},
    {"leverancier": "UWV", "_ckan_id": "uwv-open-match-data", "bron": "UWV Open Match Data"},
    {"leverancier": "RIO", "_rio_resource": "erkenningen", "bron": "Erkenningen"},
]


def _catalogus():
    return patch("tools.catalog._cbs", return_value=_CBS), patch("tools.catalog._rio_duo", return_value=_RIO_DUO)


def test_genoemd_id_krijgt_bron_en_datatool():
    cbs, rio_duo = _catalogus()
    with cbs, rio_duo:
        tekst = genoemde_bronnen("Hoeveel studenten bij ROC Midden Nederland in mbo-studenten-per-instelling?")
    assert "mbo-studenten-per-instelling: Studenten per mbo-instelling (DUO)" in tekst
    assert "get_duo_data('mbo-studenten-per-instelling')" in tekst
    assert "zoek ze niet opnieuw" in tekst


def test_cbs_id_en_bron_zonder_datatool():
    cbs, rio_duo = _catalogus()
    with cbs, rio_duo:
        tekst = genoemde_bronnen("Vergelijk 85525NED met uwv-open-match-data")
    assert "get_cbs_data('85525NED')" in tekst
    assert (
        "uwv-open-match-data: UWV Open Match Data (UWV). Staat in de catalogus, maar is in de chat niet op te vragen."
        in tekst
    )


def test_gewoon_woord_of_onbekend_id_geeft_niets():
    cbs, rio_duo = _catalogus()
    with cbs, rio_duo:
        assert genoemde_bronnen("Hoeveel erkenningen heeft Aeres?") == ""
        assert genoemde_bronnen("Wat zit er in p99-bestaat-niet?") == ""


def test_beurtcontext_komt_na_het_gecachete_systeemdeel():
    (system,) = build_system({}, beurt="De vraag noemt X.")
    vast, beurt = system["content"]
    assert "cache_control" in vast
    assert beurt == {"type": "text", "text": "De vraag noemt X."}
    assert len(build_system({})[0]["content"]) == 1


def test_run_geeft_de_genoemde_bronnen_mee_aan_de_toolloop():
    """De naad: de context moet in het systeembericht van de echte beurt staan."""
    import asyncio
    import importlib
    from types import SimpleNamespace

    run_module = importlib.import_module("agent.run")  # agent.run is ook de naam van de functie

    meegegeven = {}

    async def nep_loop(history, **kwargs):
        meegegeven.update(kwargs)
        return SimpleNamespace(aborted="tools")

    async def emit(_event):
        pass

    cbs, rio_duo = _catalogus()
    vraag = [{"role": "user", "content": "Cijfers uit mbo-studenten-per-instelling voor ROC Midden Nederland"}]
    with cbs, rio_duo, patch.object(run_module, "tool_loop", nep_loop):
        asyncio.run(run_module.run(vraag, session={}, emit=emit))
    beurt = meegegeven["system"][0]["content"][-1]["text"]
    assert "get_duo_data('mbo-studenten-per-instelling')" in beurt
