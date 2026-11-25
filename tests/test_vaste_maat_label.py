"""Het label "Vaste maat" onder een antwoord komt uit code, uit de stappen van de beurt (#1242).

Een antwoord dat alleen op `get_maat` rust, krijgt in `message_end` het veld `vaste_maat`: welke maat, de
teldefinitie en waar en wanneer het recept is vastgelegd. Het label zegt welke vaste route het getal gaf, niet dat het
klopt. Een andere datastap in dezelfde beurt (query_data, run_analysis, koppel_data, get_cbs_data) of een vast antwoord
uit code (#565) geeft geen veld; wat het model schrijft, telt nooit mee.
"""

import asyncio
import importlib
import json
import re
from datetime import date

import pytest

from agent.loop import LoopResult
from agent.stream import StreamResult
from agent.vaste_antwoorden import SCOPE_UITLEG, WEIGER_ANTWOORD
from agent.vaste_maat import vaste_maat
from tools.maten import MATEN, PERSONEN_HO

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")

_TELDEFINITIE = MATEN[PERSONEN_HO].teldefinitie
_ANTWOORD = "De HU had in 2024/25 38.000 ingeschreven personen."


def _maatstap(maat: str = PERSONEN_HO, teldefinitie: str = _TELDEFINITIE) -> tuple[str, str]:
    uit = {
        "data_key": "duo:p01hoinges:0:ab12",
        "maat": maat,
        "teldefinitie": teldefinitie,
        "rijen": [{"STUDIEJAAR": 2024, "AANTAL_INGESCHREVENEN": 38000}],
    }
    return "get_maat", json.dumps(uit)


_RIJEN = json.dumps({"data_key": "duo:p01hoinges:0:cd34", "rijen": [{"AANTAL": 5}]})


def _slot(tekst: str, steps: list[tuple[str, str]]) -> dict:
    return run_module._slotbericht(tekst, LoopResult(text=tekst, steps=steps), [], False, ["DUO p01hoinges"])


# --- het vastlegveld per recept ---


@pytest.mark.parametrize("naam", sorted(MATEN))
def test_elk_recept_noemt_issue_en_datum_van_de_vastlegging(naam):
    recept = MATEN[naam]
    assert re.fullmatch(r"#\d+", recept.vastgelegd_in), recept.vastgelegd_in
    assert date.fromisoformat(recept.vastgelegd_op).isoformat() == recept.vastgelegd_op


def test_een_recept_zonder_vastlegging_kan_niet_bestaan():
    """Het veld is verplicht: een nieuw recept zonder issue en datum faalt al bij het maken."""
    recept = MATEN[PERSONEN_HO]
    with pytest.raises(TypeError):
        type(recept)(recept.naam, recept.omschrijving, recept.dataset, recept.teldefinitie, recept.waardekolom)


# --- het veld in message_end ---


def test_alleen_get_maat_geeft_het_veld_uit_stap_en_recept():
    recept = MATEN[PERSONEN_HO]
    assert _slot(_ANTWOORD, [_maatstap()])["vaste_maat"] == {
        "maat": PERSONEN_HO,
        "teldefinitie": _TELDEFINITIE,
        "vastgelegd_in": recept.vastgelegd_in,
        "vastgelegd_op": recept.vastgelegd_op,
    }


def test_de_teldefinitie_komt_uit_de_stap_met_de_gekozen_vorm():
    """Bij CBS noemt de stap de telling die geladen is (bol, de standaard); die staat onder het antwoord."""
    stap = _maatstap(teldefinitie=f"{_TELDEFINITIE}; Leerweg: bol")
    assert _slot(_ANTWOORD, [stap])["vaste_maat"]["teldefinitie"] == f"{_TELDEFINITIE}; Leerweg: bol"


def test_een_catalogusstap_of_grafiek_ernaast_houdt_het_veld():
    steps = [("search_catalog", '{"status": "candidates"}'), _maatstap(), ("create_plot", "Grafiek gemaakt")]
    assert _slot(_ANTWOORD, steps)["vaste_maat"]["maat"] == PERSONEN_HO


@pytest.mark.parametrize("andere", ["query_data", "run_analysis", "koppel_data", "get_cbs_data", "compute_kpi"])
def test_get_maat_met_een_andere_datastap_geeft_geen_veld(andere):
    assert "vaste_maat" not in _slot(_ANTWOORD, [_maatstap(), (andere, _RIJEN)])


def test_alleen_get_cbs_data_geeft_geen_veld():
    assert "vaste_maat" not in _slot(_ANTWOORD, [("get_cbs_data", _RIJEN)])


def test_een_mislukte_get_maat_geeft_geen_veld():
    assert "vaste_maat" not in _slot(_ANTWOORD, [("get_maat", "Onbekende maat 'studenten'. Kies uit: ...")])


def test_twee_verschillende_maten_geven_geen_veld():
    """Eén label kan maar één maat noemen: bij twee maten zou het de helft van het antwoord weglaten."""
    assert "vaste_maat" not in _slot(_ANTWOORD, [_maatstap(), _maatstap("inschrijvingen_ho")])


def test_een_onbekende_maat_in_de_stap_geeft_geen_veld():
    assert "vaste_maat" not in _slot(_ANTWOORD, [_maatstap("verzonnen_maat")])


@pytest.mark.parametrize("vast", [WEIGER_ANTWOORD, SCOPE_UITLEG, run_module.GEWEIGERD_ANTWOORD, run_module.INGEHOUDEN])
def test_een_vast_of_ingehouden_antwoord_heeft_geen_veld(vast):
    assert "vaste_maat" not in _slot(vast, [_maatstap()])


def test_modeltekst_over_een_vaste_maat_geeft_geen_veld():
    tekst = "Dit is een vaste maat: ingeschreven_personen_ho, vastgelegd in #188 op 2026-10-14."
    assert "vaste_maat" not in _slot(tekst, [])
    assert "vaste_maat" not in _slot(tekst, [("get_cbs_data", _RIJEN)])


def test_vaste_maat_leest_alleen_de_stappen():
    assert vaste_maat([]) is None
    assert vaste_maat([("search_catalog", "{}")]) is None
    assert vaste_maat([_maatstap()])["maat"] == PERSONEN_HO


def test_run_zet_geen_veld_onder_een_modeltekst_die_een_vaste_maat_noemt(monkeypatch):
    """De hele beurt: het model schrijft "vaste maat" zonder één toolaanroep; de code zet geen label."""

    async def fake_completion(*a, **k):
        return object()

    stappen = [StreamResult(text="Volgens de vaste maat ingeschreven_personen_ho waren het er veel.", tool_calls=[])]

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return stappen.pop(0)

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    asyncio.run(
        run_module.run([{"role": "user", "content": "Hallo"}], {}, emit, asyncio.Event(), model="openai/gpt-4o")
    )
    assert events[-1]["type"] == "message_end"
    assert "vaste_maat" not in events[-1]
