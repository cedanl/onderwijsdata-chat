"""Verklaringen alleen op verzoek, en dan in een blok "Niet uit de data" (#1036).

Seminarfeedback: elk antwoord met data eindigde met een **Mogelijke verklaring**, en een oorzaak zonder bron stuurt
de lezer. Code beslist of de gebruiker om een verklaring vroeg (`tools.verklaring_markers`). Zonder verzoek is een
vermoeden een controleprobleem (de bestaande herkansing haalt het weg); met verzoek hoort het als toetsbare vraag in
het blok "Niet uit de data", hooguit drie, elk met een bron uit de catalogus of "hiervoor is geen bron in deze app".
"""

import asyncio
import importlib
import json
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

from agent import report
from agent.beweringen import onbeschikbaar_zonder_zoekpad, ongedekte_oorzaak, verklaringsblok
from agent.loop import LoopResult
from agent.report import ReportSpec
from agent.report_checks import report_problems
from agent.stream import StreamResult
from tools import store
from tools.store import KeyMeta

run_module = importlib.import_module("agent.run")  # agent.run is ook de naam van de functie
loop_module = importlib.import_module("agent.loop")

_KEY = "duo:p02:a"
_DATA = [json.dumps({"data_key": _KEY, "rijen": [{"AANTAL": 5943}]})]
_WAAROM = "Waarom daalt de instroom in de lerarenopleidingen?"
_HOEVEEL = "Hoeveel eerstejaars hbo zijn er per jaar sinds 2020?"

_FEIT = "De instroom daalde naar 5.943 eerstejaars."
_BLOK_DRIE = (
    "### Niet uit de data\n"
    "1. Hangt de daling samen met minder 18-jarigen? Te toetsen met 37296ned.\n"
    "2. Speelt het lerarentekort mee in de keuze voor de opleiding? Hiervoor is geen bron in deze app.\n"
    "3. Hangt de daling samen met de instroom in het mbo? Te toetsen met 85354NED."
)
_VIERDE = "\n4. Kiezen studenten vaker voor een universitaire opleiding? Hiervoor is geen bron in deze app."
_HYPOTHESE = (
    "Een mogelijke verklaring is de krimp van de groep jongeren; dat is met deze gegevens niet vast te stellen."
)


# ── Controle zonder verzoek (criterium 5) ────────────────────────────────────


@pytest.mark.parametrize(
    "vermoeden",
    [
        _HYPOTHESE,
        "Mogelijke oorzaken zijn de krimp en de arbeidsmarkt, maar dat is niet vast te stellen met deze gegevens.",
        "Dit zou kunnen samenhangen met de arbeidsmarkt; dat is een vermoeden.",
        "Dit zou kunnen komen doordat jongeren later kiezen.",
        "Het is denkbaar dat jongeren later kiezen.",
        "**Mogelijke verklaring:** de data laat de oorzaak niet zien.",
    ],
)
def test_zonder_verzoek_is_een_vermoeden_een_probleem_ook_met_voorbehoud(vermoeden):
    problemen = ongedekte_oorzaak(f"{_FEIT}\n\n{vermoeden}", _DATA, verklaring_gevraagd=False)

    assert len(problemen) == 1
    assert "niet om vroeg" in problemen[0]


def test_zonder_verzoek_is_het_blok_een_probleem():
    problemen = ongedekte_oorzaak(f"{_FEIT}\n\n{_BLOK_DRIE}", _DATA, verklaring_gevraagd=False)

    assert len(problemen) == 1
    assert "Niet uit de data" in problemen[0] and "vroeg niet om een verklaring" in problemen[0]


def test_zonder_verzoek_blijft_een_antwoord_met_alleen_data_schoon():
    assert ongedekte_oorzaak(f"{_FEIT}\n\nWat valt op: de daling is het grootst in 2023.", _DATA, False) == []


def test_zonder_data_zwijgt_de_controle_ook_zonder_verzoek():
    assert ongedekte_oorzaak(_HYPOTHESE, [], verklaring_gevraagd=False) == []


# ── Controle met verzoek (criterium 6) ───────────────────────────────────────


def test_met_verzoek_is_een_blok_met_drie_vragen_eerlijk():
    assert ongedekte_oorzaak(f"{_FEIT}\n\n{_BLOK_DRIE}", _DATA, verklaring_gevraagd=True) == []


def test_een_blok_met_een_vetgedrukte_kop_telt_ook():
    blok = _BLOK_DRIE.replace("### Niet uit de data", "**Niet uit de data**")

    assert ongedekte_oorzaak(f"{_FEIT}\n\n{blok}", _DATA, verklaring_gevraagd=True) == []
    assert verklaringsblok(f"{_FEIT}\n\n{blok}")[1].strip().startswith("1. Hangt")


def test_het_blok_loopt_tot_de_volgende_kop():
    tekst = f"{_FEIT}\n\n{_BLOK_DRIE}\n\n**Bronnen**\n- DUO p02"
    buiten, blok = verklaringsblok(tekst)

    assert "Bronnen" in buiten and "Bronnen" not in blok
    assert "Hangt de daling" in blok and "Hangt de daling" not in buiten


def test_met_verzoek_is_een_vierde_vraag_een_probleem():
    [probleem] = ongedekte_oorzaak(f"{_FEIT}\n\n{_BLOK_DRIE}{_VIERDE}", _DATA, verklaring_gevraagd=True)

    assert "4 vragen" in probleem and "hooguit 3" in probleem


def test_met_verzoek_is_een_gestelde_oorzaak_in_het_blok_een_probleem():
    blok = _BLOK_DRIE + "\nDe daling komt doordat het lerarentekort studenten afschrikt."

    [probleem] = ongedekte_oorzaak(f"{_FEIT}\n\n{blok}", _DATA, verklaring_gevraagd=True)

    assert "als feit" in probleem


def test_met_verzoek_en_blok_is_een_vermoeden_buiten_het_blok_een_probleem():
    [probleem] = ongedekte_oorzaak(f"{_FEIT}\n\n{_HYPOTHESE}\n\n{_BLOK_DRIE}", _DATA, verklaring_gevraagd=True)

    assert "buiten het blok" in probleem


def test_met_verzoek_blijft_een_oorzaak_zonder_voorbehoud_een_probleem():
    tekst = f"{_FEIT} Dit komt doordat het lerarentekort studenten afschrikt.\n\n{_BLOK_DRIE}"

    [probleem] = ongedekte_oorzaak(tekst, _DATA, verklaring_gevraagd=True)

    assert "niet uit de opgehaalde data volgt" in probleem


def test_de_standaard_is_met_verzoek_zoals_het_rapport_toetst():
    """Criterium 8: zonder blok blijft de regel van het voorbehoud, voor `report_checks` en de oude tests."""
    assert ongedekte_oorzaak(f"{_FEIT}\n\n{_HYPOTHESE}", _DATA) == []
    assert len(ongedekte_oorzaak(f"{_FEIT}\n\n{_BLOK_DRIE}{_VIERDE}", _DATA)) == 1


# ── De blokkop is geen "niet beschikbaar" (criterium 7) ──────────────────────


_NUL_RIJEN = json.dumps({"rijen": [], "suggesties": {"OPLEIDING": ["Pabo"]}})


def test_de_blokkop_geeft_geen_probleem_bij_niet_beschikbaar():
    tekst = f"{_FEIT}\n\n{_BLOK_DRIE}"

    assert onbeschikbaar_zonder_zoekpad(_WAAROM, tekst, [*_DATA, _NUL_RIJEN]) == []
    # Dezelfde woorden als bewering, niet als kop, blijven wel getoetst.
    assert len(onbeschikbaar_zonder_zoekpad(_WAAROM, "Dat staat niet in de data.", [*_DATA, _NUL_RIJEN])) == 1


# ── De beurtcontext (criterium 3) ────────────────────────────────────────────


def _beurtcontext(messages: list[dict], session: dict | None = None) -> str:
    """De beurtcontext zoals de toolloop hem krijgt."""
    meegegeven: dict = {}

    async def nep_loop(history, **kwargs):
        meegegeven.update(kwargs)
        return SimpleNamespace(aborted="tools")

    async def emit(_event):
        pass

    with (
        patch("prompts.instellingsprofiel", return_value=None),
        patch.object(run_module, "tool_loop", nep_loop),
        patch.object(run_module, "scopevraag", lambda *a, **k: None),
    ):
        asyncio.run(run_module.run(messages, session=session or {}, emit=emit))
    return meegegeven["system"][0]["content"][-1]["text"]


def test_een_waaromvraag_krijgt_de_opdracht_voor_het_blok():
    beurt = _beurtcontext([{"role": "user", "content": _WAAROM}])

    assert "Verklaring gevraagd" in beurt
    assert "### Niet uit de data" in beurt and "hooguit 3" in beurt
    assert "hiervoor is geen bron in deze app" in beurt


def test_een_datavraag_krijgt_de_opdracht_om_geen_oorzaken_te_geven():
    beurt = _beurtcontext([{"role": "user", "content": _HOEVEEL}])

    assert "Geen verklaring gevraagd" in beurt
    assert "Verklaring gevraagd." not in beurt


def test_een_keuze_op_een_kaart_houdt_het_verzoek():
    """Criterium 2: het antwoord op een verduidelijkingskaart laat het verzoek niet vallen."""
    messages = [
        {"role": "user", "content": _WAAROM},
        {"role": "assistant", "content": "Welke periode?"},
        {"role": "user", "content": "Laatste 5 jaar"},
    ]
    session = {"clarify_rondes": 1, "clarify_code_opties": ["Laatste 5 jaar"]}

    assert run_module._verklaring_gevraagd(messages, session)
    assert "Verklaring gevraagd" in _beurtcontext(messages, session)


def test_een_label_uit_code_maakt_geen_verzoek():
    messages = [
        {"role": "user", "content": _HOEVEEL},
        {"role": "assistant", "content": "Welke afbakening?"},
        {"role": "user", "content": "Waarom deze keuze"},
    ]

    assert not run_module._verklaring_gevraagd(
        messages, {"clarify_rondes": 1, "clarify_code_opties": ["Waarom deze keuze"]}
    )


def test_een_elliptische_vervolgvraag_houdt_het_verzoek_van_de_vorige_beurt():
    messages = [
        {"role": "user", "content": "Waarom daalt de instroom?"},
        {"role": "assistant", "content": "De instroom daalde."},
        {"role": "user", "content": "En voor wo?"},
    ]

    assert run_module._verklaring_gevraagd(messages, {})
    assert not run_module._verklaring_gevraagd([*messages[:2], {"role": "user", "content": _HOEVEEL}], {})


# ── De beurt met een nagebootst model (criteria 5 en 6) ──────────────────────

_QUERY = {"id": "q", "name": "query_data", "arguments": '{"data_key": "duo:p02"}'}


def _chat(monkeypatch, vraag: str, teksten: list[str]):
    steps = [StreamResult(text="", tool_calls=[_QUERY]), *(StreamResult(text=t, tool_calls=[]) for t in teksten)]
    gezien: list[list[dict]] = []

    async def fake_completion(*args, **kwargs):
        gezien.append(list(kwargs["messages"]))
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return steps.pop(0)

    async def fake_execute_tool(call, emit, recept_van=None):
        return _DATA[0], None

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop_module, "_execute_tool", fake_execute_tool)
    monkeypatch.setattr(run_module, "scopevraag", lambda *a, **k: None)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    text = asyncio.run(
        run_module.run([{"role": "user", "content": vraag}], {}, emit, asyncio.Event(), model="openai/gpt-4o")
    )
    return text, events, gezien


def test_een_ongevraagde_verklaring_gaat_eruit_in_de_herkansing(monkeypatch, caplog):
    with caplog.at_level("INFO", logger="agent.run"):
        text, events, gezien = _chat(monkeypatch, _HOEVEEL, [f"{_FEIT}\n\n{_HYPOTHESE}", _FEIT])

    assert text == _FEIT
    assert "message_cancel" in [e["type"] for e in events]
    herkansing = gezien[-1][-1]["content"]
    assert "niet om vroeg" in herkansing
    assert "HERKANSING  controles=['ongedekte_oorzaak']" in caplog.text
    assert "controle" not in events[-1]


def test_een_gevraagde_verklaring_in_het_blok_komt_door_de_controle(monkeypatch):
    antwoord = f"{_FEIT}\n\n{_BLOK_DRIE}"

    text, events, _ = _chat(monkeypatch, _WAAROM, [antwoord])

    assert text == antwoord
    assert "message_cancel" not in [e["type"] for e in events]
    assert "controle" not in events[-1]


@pytest.mark.parametrize(
    "blok",
    [_BLOK_DRIE + _VIERDE, _BLOK_DRIE + "\nDe daling komt doordat het lerarentekort studenten afschrikt."],
)
def test_een_gevraagde_verklaring_met_een_gestelde_oorzaak_of_vier_vragen_wordt_gemeld(monkeypatch, blok):
    _, events, gezien = _chat(monkeypatch, _WAAROM, [f"{_FEIT}\n\n{blok}", f"{_FEIT}\n\n{_BLOK_DRIE}"])

    assert "message_cancel" in [e["type"] for e in events]
    assert "Niet uit de data" in gezien[-1][-1]["content"]


# ── Het rapport (criterium 9) ────────────────────────────────────────────────


@pytest.fixture
def rapportsessie():
    store.clear()
    store.put(_KEY, pd.DataFrame({"STUDIEJAAR": [2024], "AANTAL": [5943]}), KeyMeta("duo", "p02ho1ejrs", resource=5))
    sessie = {
        "data_keys": [_KEY],
        "messages": [
            {"role": "user", "content": _WAAROM},
            {"role": "assistant", "content": f"{_FEIT}\n\n{_BLOK_DRIE}"},
        ],
        "data_vraag": {_KEY: 1},
    }
    yield sessie
    store.clear()


def test_de_rapportprompt_bevat_geen_antwoordtekst_uit_de_chat(rapportsessie, monkeypatch):
    """Een blok "Niet uit de data" uit de chat kan zo geen bevinding van het rapport worden."""
    gezien: dict = {}

    async def loop(messages, **_):
        gezien["prompt"] = messages[0]["content"]
        return LoopResult(text=json.dumps({"beantwoordt": ["x"], "beantwoordt_niet": ["y"], "conclusie": "z"}))

    async def stil(_event):
        pass

    monkeypatch.setattr(report, "tool_loop", loop)
    asyncio.run(report.generate(rapportsessie, stil))

    assert _WAAROM in gezien["prompt"]
    assert "Niet uit de data" not in gezien["prompt"]
    assert "lerarentekort" not in gezien["prompt"] and "18-jarigen" not in gezien["prompt"]


def test_een_hypothese_uit_het_blok_als_bewering_in_het_rapport_is_een_probleem():
    beurt = [json.dumps({"data_key": _KEY, "rijen": [{"STUDIEJAAR": 2024, "AANTAL": 5943}]})]
    spec = ReportSpec(
        title="Instroom lerarenopleidingen",
        onderzoeksvraag=_WAAROM,
        beantwoordt=["Instroom 2024"],
        conclusie=f"{_FEIT} De daling hangt samen met het lerarentekort.",
    )

    assert [p for p in report_problems(spec, [], beurt) if "oorzaak" in str(p)]
