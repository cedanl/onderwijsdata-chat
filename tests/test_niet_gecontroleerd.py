"""Een controle die zelf faalt, is niet hetzelfde als akkoord (#419, CH-12).

`veilig` crasht niet (#392), maar meldt zichtbaar dat het antwoord op dat punt niet
gecontroleerd is: een zacht probleem, zonder herkansing (het model kan het niet herstellen).
"""

import asyncio
import importlib

from agent import loop as loop_module
from agent.probleem import hard, harde, herstelbare, meldingen, veilig
from agent.stream import StreamResult


def _kapot(*_):
    raise ValueError("zip() argument 3 is shorter than arguments 1-2")


def _akkoord(*_):
    return []


def test_akkoord_is_leeg():
    assert veilig(_akkoord, "tekst") == []


def test_een_falende_controle_geeft_een_zichtbaar_niet_gecontroleerd_probleem(caplog):
    with caplog.at_level("ERROR"):
        [probleem] = veilig(_kapot, "tekst")
    assert probleem.niet_gecontroleerd
    assert "niet gecontroleerd" in probleem.melding
    assert "Interne fout" in caplog.text and "_kapot" in caplog.text
    # De gebruiker ziet het fout-ID uit de log, zodat het terug te vinden is.
    fout_id = caplog.records[-1].args[0]
    assert fout_id in probleem.melding


def test_niet_gecontroleerd_blijft_zacht_ook_onder_hard():
    """Een mislukte harde controle houdt het antwoord niet in: er is niets fout bevonden."""
    problemen = hard(veilig(_kapot, "tekst"))
    assert problemen and harde(problemen) == []
    assert problemen[0].niet_gecontroleerd


def test_herstelbare_laat_niet_gecontroleerd_weg():
    [stuk] = veilig(_kapot)
    assert herstelbare([stuk, "6.340 staat niet in de data."]) == ["6.340 staat niet in de data."]


def test_de_gebruiker_ziet_de_melding_zonder_opdracht_aan_het_model():
    [stuk] = veilig(_kapot)
    assert meldingen([stuk]) == [stuk.melding] and stuk == stuk.melding


# ── Toolloop: geen herkansing voor wat het model niet kan herstellen ─────────


def _loop(monkeypatch, teksten: list[str], check, seen: list | None = None):
    steps = [StreamResult(text=t, tool_calls=[]) for t in teksten]

    async def fake_completion(*args, **kwargs):
        if seen is not None:
            seen.append(list(kwargs["messages"]))
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return steps.pop(0)

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)

    async def emit(event):
        pass

    return asyncio.run(
        loop_module.tool_loop(
            [{"role": "user", "content": "vraag"}],
            model="openai/gpt-4o",
            tools=[],
            emit=emit,
            max_iterations=5,
            max_result_chars=1000,
            check=check,
            correction=lambda problems: "Herstel: " + "; ".join(problems),
        )
    )


def test_alleen_niet_gecontroleerd_geeft_geen_herkansing_maar_wel_het_probleem(monkeypatch):
    seen: list = []
    result = _loop(monkeypatch, ["Antwoord"], lambda text, tool_results: veilig(_kapot), seen)

    assert len(seen) == 1, "geen herkansingsronde"
    assert result.text == "Antwoord"
    [probleem] = result.problems
    assert probleem.niet_gecontroleerd


def test_herkansing_krijgt_alleen_wat_het_model_kan_herstellen(monkeypatch):
    seen: list = []

    def check(text, tool_results):
        return [*veilig(_kapot), *(["12.345 staat niet in de data"] if "12.345" in text else [])]

    result = _loop(monkeypatch, ["Fout 12.345", "Goed"], check, seen)

    assert seen[-1][-1] == {"role": "user", "content": "Herstel: 12.345 staat niet in de data"}
    [probleem] = result.problems
    assert probleem.niet_gecontroleerd


# ── Chat en rapport: de status is zichtbaar, het antwoord blijft ─────────────


def _chat(monkeypatch, steps: list[StreamResult]):
    run_module = importlib.import_module("agent.run")

    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return steps.pop(0)

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    text = asyncio.run(
        run_module.run([{"role": "user", "content": "Hoeveel?"}], {}, emit, asyncio.Event(), model="openai/gpt-4o")
    )
    return text, events


def test_chat_met_een_falende_harde_controle_toont_het_antwoord_als_niet_gecontroleerd(monkeypatch):
    monkeypatch.setattr(importlib.import_module("agent.run"), "verkeerd_gebonden", _kapot)
    text, events = _chat(monkeypatch, [StreamResult(text="Er is geen data.", tool_calls=[])])

    assert text == "Er is geen data."
    assert "message_cancel" not in [e["type"] for e in events]
    [melding] = events[-1]["controle"]
    assert "niet gecontroleerd" in melding


def test_chat_met_falende_citaties_crasht_niet_en_stuurt_geen_citaties(monkeypatch):
    monkeypatch.setattr(importlib.import_module("agent.run"), "citaties", _kapot)
    text, events = _chat(monkeypatch, [StreamResult(text="Er is geen data.", tool_calls=[])])

    assert text == "Er is geen data."
    assert "citaties" not in events[-1]


def test_rapport_met_een_falende_controle_meldt_niet_gecontroleerd(monkeypatch):
    from agent.report import ReportSpec
    from agent.report_checks import report_problems

    monkeypatch.setattr("agent.report_checks.verkeerde_kenmerken", _kapot)
    problemen = report_problems(ReportSpec(conclusie="Er is geen data.", beantwoordt=["aantal"]), [], [])

    [stuk] = [p for p in problemen if getattr(p, "niet_gecontroleerd", False)]
    assert stuk not in harde(problemen)
