"""De zoekpoort voor vo-context beslist op de vraag van de gebruiker, niet op de zoekterm van het model (#597).

run() zet de vraag van de beurt voor de tools; een tool draait in een thread (asyncio.to_thread) en erft hem.
"""

import asyncio
import importlib
from unittest.mock import patch

from agent.loop import LoopResult
from tools import ho_markers

run_module = importlib.import_module("agent.run")  # agent.run is ook de naam van de functie


def _poort_tijdens_de_loop(messages, session=None, zoekterm="vwo leerlingen hbo"):
    """Wat de poort in een tool van deze beurt zegt over `zoekterm`, en op welke tekst hij besliste."""
    gezien: dict = {}

    async def nep_loop(history, **kwargs):
        gezien["poort"] = await asyncio.to_thread(ho_markers.ho_poort, zoekterm)
        gezien["vraag"] = ho_markers._beurtvraag.get()
        return LoopResult(aborted="stream", text="Klaar.")

    async def emit(ev):
        pass

    with (
        patch.object(run_module, "tool_loop", nep_loop),
        patch.object(run_module, "scopevraag", lambda *a, **k: None),
        patch.object(run_module, "vo_schoolvraag", lambda *a, **k: None),
    ):
        asyncio.run(run_module.run(messages, session=session or {}, emit=emit))
    return gezien


def test_een_vo_vraag_houdt_de_poort_dicht_ook_als_het_model_hbo_zoekt():
    gezien = _poort_tijdens_de_loop([{"role": "user", "content": "Hoeveel leerlingen zitten er op het vwo?"}])

    assert gezien == {"poort": False, "vraag": "Hoeveel leerlingen zitten er op het vwo?"}


def test_een_ho_vraag_opent_de_poort_ook_als_het_model_het_ho_weglaat():
    vraag = "Hoeveel vwo-leerlingen stromen door naar het wo?"
    assert _poort_tijdens_de_loop([{"role": "user", "content": vraag}], zoekterm="doorstroom vwo")["poort"] is True


def test_een_keuze_op_een_verduidelijkingsvraag_telt_met_de_vraag_die_ze_afbakent():
    """Een keuze als "2023/24" noemt zelf niets; de vraag ervoor noemt het hbo."""
    messages = [
        {"role": "user", "content": "Aansluiting vo-hbo?"},
        {"role": "assistant", "content": "Welke maat bedoel je bij 'Aansluiting vo-hbo'?"},
        {"role": "user", "content": "2023/24"},
    ]

    gezien = _poort_tijdens_de_loop(messages, session={"clarify_rondes": 1}, zoekterm="doorstroom vwo")

    assert gezien == {"poort": True, "vraag": "Aansluiting vo-hbo? 2023/24"}


def test_een_nieuwe_vraag_neemt_de_vorige_niet_mee():
    """Zonder verduidelijkingsronde telt alleen de laatste vraag: een eerdere ho-vraag opent de poort niet."""
    messages = [
        {"role": "user", "content": "Hoeveel hbo-studenten zijn er?"},
        {"role": "assistant", "content": "Er zijn 500.000 hbo-studenten."},
        {"role": "user", "content": "En hoeveel leerlingen op het vwo?"},
    ]

    assert _poort_tijdens_de_loop(messages)["poort"] is False


def test_na_de_beurt_is_er_geen_beurtvraag_meer():
    _poort_tijdens_de_loop([{"role": "user", "content": "Hoeveel hbo-studenten zijn er?"}])

    assert ho_markers._beurtvraag.get() is None
