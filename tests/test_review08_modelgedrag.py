"""Review 08: wat het model met de uitkomst van een tool doet (#959, #961, #962).

- #959: bij een codeverzoek verzon het model een script met een eigen invoerbestand, terwijl de juiste snippet in het
  tool_end-event stond (achter "Bekijk code"). Nu zet de app de code van de laatste datastap zelf onder het antwoord.
- #961: de tool vond meer studies en vroeg om een keuze; het model haalde zelf drie studies op. Nu staat er een vaste
  instructie in de melding en vangt een controle het op.
- #962: een koppeling met een tweede bron liet rijen zonder match verdwijnen (inner join, dropna). Nu zeggen de
  koppelzin van de Studiekeuzedatabase, de uitkomst van `relatie` en de systeemprompt hoe het moet.

Er staat geen data van LCSK in de repo: `onderwijsbronnen.skdb.proefbestand` bouwt een export met dezelfde vorm.
"""

import asyncio
import importlib
import json
import re
from pathlib import Path

import pandas as pd
import pytest
from onderwijsbronnen import skdb
from onderwijsbronnen.skdb import proefbestand

from agent.codeverzoek import CODEKOP, codeblok, is_codeverzoek, met_code, onthoud
from agent.controles import antwoordcontrole
from agent.ongekozen import ongekozen_studies
from agent.stream import StreamResult
from data import instellingen
from tools import relaties, store, studiekeuze
from tools.schemas import TOOL_GET_STUDIEKEUZE
from tools.store import KeyMeta

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")

SYSTEM = (Path(__file__).resolve().parent.parent / "prompts" / "system.md").read_text(encoding="utf-8")


def _profiel(naam: str) -> dict | None:
    if " ".join(naam.split()).lower() in ("hogeschool utrecht", "hu"):
        return {"naam": "Hogeschool Utrecht", "sector": "hbo", "instellingscode": "25DW"}
    return None


@pytest.fixture(autouse=True)
def proefexport(monkeypatch):
    monkeypatch.setattr(skdb, "haal_op", lambda *a, **k: proefbestand.standaard())
    monkeypatch.setattr(instellingen, "instellingsprofiel", _profiel)
    studiekeuze._export.cache_clear()
    yield
    studiekeuze._export.cache_clear()


# --- #959: de code van de stap, niet een verzonnen script ---------------------------------------------------------


@pytest.mark.parametrize(
    "vraag",
    [
        "Geef de code om dit zelf na te rekenen.",
        "Hoe kan ik dit in Python reproduceren?",
        "Mag ik het script?",
        "Can you give me the code to reproduce this?",
        "Welke pandas-code hoort hierbij?",
    ],
)
def test_een_codeverzoek_wordt_herkend(vraag):
    assert is_codeverzoek(vraag)


@pytest.mark.parametrize(
    "vraag",
    [
        "Wat is de CROHO-code van ICT bij de HU?",
        "Hoeveel studenten heeft de opleiding met opleidingscode 30020?",
        "Wat is de brincode van de Hogeschool Utrecht?",
        "Hoe tevreden zijn studenten ICT bij de HU?",
        "Wat is de code van de opleiding ICT?",
    ],
)
def test_een_vraag_naar_een_code_of_gewone_vraag_is_geen_codeverzoek(vraag):
    assert not is_codeverzoek(vraag)


def test_met_code_zet_de_snippet_onder_het_antwoord_in_een_codeblok():
    snippet = "from onderwijsbronnen import skdb\nexport = skdb.lees(*skdb.haal_op())"
    session: dict = {}
    onthoud(session, {"type": "tool_end", "name": TOOL_GET_STUDIEKEUZE, "snippet": snippet})
    tekst = met_code("Hieronder staat de code.", codeblok(session))
    assert tekst.startswith("Hieronder staat de code.")
    assert f"{CODEKOP}" in tekst and f"```python\n{snippet}\n```" in tekst


def _studiekeuze_dispatch(name, args):
    assert name == TOOL_GET_STUDIEKEUZE
    return studiekeuze.get_studiekeuze(**args), None


def _beurt(monkeypatch, vraag: str, stappen: list[StreamResult], session: dict, eerder: list[dict] | None = None):
    """Eén chatbeurt met een nagebootst model; get_studiekeuze draait echt op de proefexport, met snippet."""

    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return stappen.pop(0)

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop_module, "dispatch", _studiekeuze_dispatch)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    messages = [*(eerder or []), {"role": "user", "content": vraag}]
    asyncio.run(run_module.run(messages, session, emit, asyncio.Event(), model="openai/gpt-4o"))
    return events, messages


_HU_ICT = json.dumps({"weergave": "opleidingen", "instelling": "Hogeschool Utrecht", "opleiding": "30020"})
_VERZONNEN = (
    "Hieronder een script.\n\n```python\nimport pandas as pd\n"
    'df = pd.read_csv("studiekeuzedatabase_26_6.csv")\nprint(df)\n```'
)


def _slot(events: list[dict]) -> dict:
    return next(e for e in reversed(events) if e["type"] == "message_end")


def test_een_codeverzoek_krijgt_de_snippet_van_de_stap_in_dezelfde_beurt(monkeypatch):
    """08-B9: het model haalt de data opnieuw op; onder het antwoord staat de snippet van die stap, letterlijk."""
    stappen = [
        StreamResult(text="", tool_calls=[{"id": "s1", "name": TOOL_GET_STUDIEKEUZE, "arguments": _HU_ICT}]),
        StreamResult(text="De code van de stap staat hieronder.", tool_calls=[]),
    ]
    events, _ = _beurt(monkeypatch, "Geef de code om dit zelf na te rekenen.", stappen, {})
    snippet = next(e["snippet"] for e in events if e["type"] == "tool_end")
    inhoud = _slot(events)["content"]
    assert "skdb.lees(*skdb.haal_op())" in snippet
    assert f"```python\n{snippet}\n```" in inhoud


def test_een_codeverzoek_in_een_volgende_beurt_krijgt_de_snippet_van_de_vorige(monkeypatch):
    """Haalt het model niets opnieuw op, dan is de laatste datastap die van de vorige beurt."""
    session: dict = {}
    eerste = [
        StreamResult(text="", tool_calls=[{"id": "s1", "name": TOOL_GET_STUDIEKEUZE, "arguments": _HU_ICT}]),
        StreamResult(text="ICT bij de HU krijgt een oordeel van 3,61.", tool_calls=[]),
    ]
    events, messages = _beurt(monkeypatch, "Hoe tevreden zijn studenten ICT bij de HU?", eerste, session)
    snippet = next(e["snippet"] for e in events if e["type"] == "tool_end")
    assert CODEKOP not in _slot(events)["content"]  # geen codeverzoek: geen codeblok

    eerder = [*messages, {"role": "assistant", "content": _slot(events)["content"]}]
    events, _ = _beurt(
        monkeypatch,
        "Geef de code om dit zelf na te rekenen.",
        [StreamResult(text=_VERZONNEN, tool_calls=[])],
        session,
        eerder,
    )
    inhoud = _slot(events)["content"]
    assert f"```python\n{snippet}\n```" in inhoud
    assert inhoud.index(CODEKOP) > inhoud.index("Hieronder een script.")


def test_de_systeemprompt_verbiedt_een_verzonnen_script_bij_een_codeverzoek():
    assert "Codeverzoek" in SYSTEM
    regel = next(r for r in SYSTEM.splitlines() if "Codeverzoek" in r)
    assert "Bekijk code" in regel and "verzin" in regel.lower()


# --- #961: meer studies, eerst de keuze ----------------------------------------------------------------------------


def test_de_keuzemelding_zegt_dat_het_model_moet_vragen_en_wachten():
    melding = studiekeuze.get_studiekeuze(weergave="studie", opleiding="Psychologie")
    assert melding.startswith("Meer studies passen")
    assert studiekeuze.KIES_EERST in melding
    assert "clarify_scope" in studiekeuze.KIES_EERST and "niet" in studiekeuze.KIES_EERST


def test_ook_bij_meer_instellingen_eerst_de_keuze():
    assert studiekeuze.KIES_EERST in studiekeuze.get_studiekeuze(instelling="Hogeschool")


def _studieuitkomst(code: int) -> str:
    return json.dumps(
        {
            "dataset": studiekeuze.DATASET,
            "weergave": "studie",
            "selectie": {"weergave": "studie", "opleiding": str(code)},
            "rijen": [{"studiecode": code}],
        }
    )


def test_een_studie_die_de_gebruiker_niet_koos_geeft_een_probleem():
    """08-B5: na de keuzemelding haalde het model 56604, 34507 en 60260 zelf op."""
    melding = studiekeuze.get_studiekeuze(weergave="studie", opleiding="Psychologie")
    codes = [int(c) for c in re.findall(r"studiecode (\d{5})", melding)][:2]
    stappen = [melding, *(_studieuitkomst(c) for c in codes)]
    (probleem,) = ongekozen_studies("Wat verdienen afgestudeerden Psychologie?", stappen)
    assert all(str(c) in probleem for c in codes)
    assert "clarify_scope" in probleem


def test_een_studie_die_de_vraag_noemt_is_gekozen():
    melding = studiekeuze.get_studiekeuze(weergave="studie", opleiding="Psychologie")
    code = re.findall(r"studiecode (\d{5})", melding)[0]
    stappen = [melding, _studieuitkomst(int(code))]
    assert ongekozen_studies(f"Wat verdienen afgestudeerden van studiecode {code}?", stappen) == []


def test_zonder_keuzemelding_geen_probleem():
    assert ongekozen_studies("Wat verdienen afgestudeerden Psychologie?", [_studieuitkomst(56604)]) == []


def test_de_controle_hoort_bij_de_antwoordcontrole():
    melding = studiekeuze.get_studiekeuze(weergave="studie", opleiding="Psychologie")
    code = int(re.findall(r"studiecode (\d{5})", melding)[0])
    check = antwoordcontrole("Wat verdienen afgestudeerden Psychologie?", [], [], [], [])
    problemen = check("Psychologen verdienen goed.", [melding, _studieuitkomst(code)])
    assert any(str(code) in p and "clarify_scope" in p for p in problemen)


def test_de_systeemprompt_zegt_eerst_kiezen_bij_meer_studies():
    regel = next(r for r in SYSTEM.splitlines() if "Meer studies" in r)
    assert "clarify_scope" in regel and "Geen gok" in regel


# --- #962: koppelen zonder rijen te verliezen ---------------------------------------------------------------------


def test_de_koppelzin_zegt_eerst_relatie_dan_left_join_zonder_nul_of_dropna():
    zin = studiekeuze.KOPPELEN
    assert zin.index("relatie") < zin.index('how="left"')
    assert "leeg" in zin and "nooit 0" in zin and "dropna" in zin


def test_relatie_met_koppelkandidaten_geeft_de_koppelregel(monkeypatch):
    monkeypatch.setattr(instellingen, "get_all", lambda: [{"instellingscode": "25DW"}, {"instellingscode": "21PD"}])
    skdb_df = pd.DataFrame({"brin": ["25DW", "30GB", "21PD"], "croho": [30020, 30020, 56604]})
    duo_df = pd.DataFrame({"INSTELLINGSCODE_ACTUEEL": ["25DW"], "OPLEIDINGSCODE_ACTUEEL": [30020], "AANTAL": [2324]})
    store.put("skdb:opleidingen:proef962", skdb_df, KeyMeta(bron="skdb", dataset="skdb:studiekeuzedatabase"))
    store.put("duo:p01hoinges:0:proef962", duo_df, KeyMeta(bron="duo", dataset="duo:p01hoinges"))
    uit = json.loads(relaties.relatie("skdb:opleidingen:proef962", "duo:p01hoinges:0:proef962"))
    assert uit["koppelingen"] and uit["koppelregel"] == relaties.KOPPELREGEL
    assert 'how="left"' in relaties.KOPPELREGEL and "nooit 0" in relaties.KOPPELREGEL


def test_relatie_zonder_tweede_tabel_of_zonder_kandidaat_geeft_geen_koppelregel():
    store.put(
        "skdb:opleidingen:proef962b", pd.DataFrame({"x": [1]}), KeyMeta(bron="skdb", dataset="skdb:studiekeuzedatabase")
    )
    store.put("duo:p01hoinges:0:proef962b", pd.DataFrame({"y": [1]}), KeyMeta(bron="duo", dataset="duo:p01hoinges"))
    assert "koppelregel" not in json.loads(relaties.relatie("skdb:opleidingen:proef962b"))
    assert "koppelregel" not in json.loads(relaties.relatie("skdb:opleidingen:proef962b", "duo:p01hoinges:0:proef962b"))


def test_de_systeemprompt_zegt_hoe_te_koppelen():
    regel = next(r for r in SYSTEM.splitlines() if r.startswith("- **Koppelen**"))
    assert 'how="left"' in regel and "nooit 0" in regel and "dropna" in regel
    assert regel.index("relatie") < regel.index('how="left"')
