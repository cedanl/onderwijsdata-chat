"""Uitgangspunt en Telling staan één keer onder en boven het antwoord, uit code (#1083).

De app zet de Uitgangspunt-regel en het Telling-blok zelf bij elk antwoord. Ze gingen mee in de historie, het model
schreef ze in een vervolgantwoord over, en de app zette er de hare naast: twee keer Uitgangspunt en twee keer Telling,
de ene van het model, de andere uit code. Nu vervalt een eigen blok van het model voor dat uit code, en gaat de historie
zonder die blokken naar het model.
"""

import asyncio
import importlib
import json

import pandas as pd
import pytest

from agent.history import zonder_vaste_blokken
from agent.loop import LoopResult
from agent.stream import StreamResult
from agent.telling import met_telling, telling_blok, zonder_telling
from agent.uitgangspunt import met_uitgangspunt, uitgangspunt, zonder_uitgangspunt
from routes import chat
from tools import TOOL_GET_MAAT, store
from tools.store import KeyMeta

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")

_DEFINITIE = "Ingeschrevenen: van alle inschrijvingen op de peildatum 1 oktober worden de hoofdinschrijvingen bepaald."
_LAAD = "duo:p01hoinges:3"
_SEL = "duo:p01hoinges:3:21pd"
_UU = {"naam": "Universiteit Utrecht", "sector": "wo", "instellingscode": "21PD"}
_VRAAG = "Hoeveel studenten heeft Utrecht?"
_ANTWOORD = "Utrecht had in 2023/24 38.288 studenten."
_EIGEN_UITGANGSPUNT = "**Uitgangspunt:** Utrecht, alle studenten\nin 2023/24"
_EIGEN_TELLING = "**Telling**\n- Het model telt hier zelf: alle studenten."


@pytest.fixture(autouse=True)
def _data():
    store.clear()
    df = pd.DataFrame({"INSTELLINGSCODE_ACTUEEL": ["21PD"], "STUDIEJAAR": [2023], "AANTAL_INGESCHREVENEN": [38288]})
    store.put(
        _LAAD,
        df,
        KeyMeta(
            bron="duo",
            dataset="p01hoinges",
            resource=3,
            periodekolom="STUDIEJAAR",
            schooljaren=(2023,),
            teldefinitie=_DEFINITIE,
        ),
    )
    store.derive(_LAAD, _SEL, df, instellingen=("21PD",), schooljaren=(2023,))
    yield
    store.clear()


def _maat() -> tuple[str, str]:
    result = {
        "data_key": _SEL,
        "maat": "ingeschreven_personen_ho",
        "vorm": "alle",
        "recept": {"bron": "duo", "dataset": "p01hoinges"},
        "instelling": _UU,
        "rijen": [{"STUDIEJAAR": 2023, "AANTAL_INGESCHREVENEN": 38288}],
    }
    return TOOL_GET_MAAT, json.dumps(result)


def _met_eigen_blokken(antwoord: str = _ANTWOORD) -> str:
    """Een modeltekst die de blokken uit een eerder antwoord overnam: Uitgangspunt bovenaan, Telling eronder."""
    return f"{_EIGEN_UITGANGSPUNT}\n\n{antwoord}\n\n{_EIGEN_TELLING}"


# ── 1. Precies één blok van elk, uit code ───────────────────────────────────


def test_een_eigen_telling_blok_wijkt_voor_dat_uit_code():
    steps = [_maat()]
    tool_results = [r for _, r in steps]

    tekst = met_telling(f"{_ANTWOORD}\n\n{_EIGEN_TELLING}", tool_results)

    assert tekst.count("**Telling**") == 1
    assert "Het model telt hier zelf" not in tekst
    assert tekst == f"{_ANTWOORD}\n\n{telling_blok(tool_results, _ANTWOORD)}"


def test_een_eigen_uitgangspunt_wijkt_voor_dat_uit_code():
    steps = [_maat()]

    tekst = met_uitgangspunt(f"{_EIGEN_UITGANGSPUNT}\n\n{_ANTWOORD}", _VRAAG, steps)

    assert tekst.count("**Uitgangspunt:**") == 1
    assert "alle studenten" not in tekst
    assert tekst == f"{uitgangspunt(_VRAAG, _ANTWOORD, steps)}\n\n{_ANTWOORD}"


def test_via_de_opmaak_van_run_staat_er_een_van_elk_en_dat_is_die_uit_code(monkeypatch):
    """De modeltekst bevat beide blokken; na `_antwoordtekst` en `_met_kopregels` staat er één van elk, uit code."""
    monkeypatch.setattr(run_module, "interpretatie_bij", lambda *a, **k: None)
    steps = [_maat()]
    result = LoopResult(text=_met_eigen_blokken(), steps=steps)
    messages = [{"role": "user", "content": _VRAAG}]

    tekst = run_module._met_kopregels(run_module._antwoordtekst(result, result.text, [], []), messages, {}, steps)

    assert tekst.count("**Uitgangspunt:**") == 1 and tekst.count("**Telling**") == 1
    assert "alle studenten" not in tekst and "Het model telt hier zelf" not in tekst
    assert tekst.startswith(uitgangspunt(_VRAAG, _ANTWOORD, steps) or "")
    assert _DEFINITIE in tekst
    assert _ANTWOORD in tekst


def test_een_vette_kop_na_het_eigen_telling_blok_blijft_staan():
    tekst = met_telling(f"{_ANTWOORD}\n\n{_EIGEN_TELLING}\n\n**Conclusie**\nHet groeit.", [_maat()[1]])

    assert "**Conclusie**\nHet groeit." in tekst
    assert tekst.count("**Telling**") == 1


def test_een_alinea_na_het_eigen_telling_blok_blijft_staan():
    """Alleen de kop met zijn regels gaat weg; wat het model daarna in een eigen alinea schrijft, is inhoud."""
    assert zonder_telling(f"{_ANTWOORD}\n\n{_EIGEN_TELLING}\n\nWil je ook de mbo-cijfers?") == (
        f"{_ANTWOORD}\n\nWil je ook de mbo-cijfers?"
    )


def test_een_telling_met_een_lege_regel_voor_de_opsomming_gaat_helemaal_weg():
    assert zonder_telling(f"{_ANTWOORD}\n\n**Telling**\n\n- een\n- twee") == _ANTWOORD


def test_het_woord_telling_in_de_lopende_tekst_blijft():
    tekst = "De **Telling** van DUO verschilt van die van CBS."
    assert zonder_telling(tekst) == tekst
    assert zonder_uitgangspunt("Het **Uitgangspunt:** blijft hier staan.") == "Het **Uitgangspunt:** blijft hier staan."


def test_zonder_blok_uit_code_blijft_het_eigen_blok_staan():
    """Gekozen gedrag (#1083): de app vervangt een eigen blok alleen als ze er zelf één plakt. Zonder data in de beurt
    geeft de code geen Telling en geen Uitgangspunt; dan is er niets dubbel en blijft de tekst van het model."""
    tekst = _met_eigen_blokken()

    assert met_telling(tekst, []) == tekst
    assert met_uitgangspunt(tekst, _VRAAG, []) == tekst


# ── 3. Zonder eigen blokken zoals voorheen ──────────────────────────────────


def test_zonder_eigen_blokken_komen_ze_er_zoals_voorheen_bij():
    steps = [_maat()]
    tool_results = [r for _, r in steps]

    assert met_telling(_ANTWOORD, tool_results) == f"{_ANTWOORD}\n\n{telling_blok(tool_results, _ANTWOORD)}"
    regel = uitgangspunt(_VRAAG, _ANTWOORD, steps)
    assert regel and met_uitgangspunt(_ANTWOORD, _VRAAG, steps) == f"{regel}\n\n{_ANTWOORD}"


# ── 2. De historie naar het model ───────────────────────────────────────────


def _opgemaakt() -> str:
    """Een antwoord zoals de app het toonde: met een interpretatiezin, Uitgangspunt, Telling en de bronkeuze."""
    return (
        "Ik ga uit van alle studenten.\n\n"
        "**Uitgangspunt:** Universiteit Utrecht (21PD) · 2023/24\n\n"
        f"{_ANTWOORD}\n\n"
        f"**Telling**\n- Ingeschrevenen hoger onderwijs: {_DEFINITIE}\n\n"
        "**Bron en definitie:** dit cijfer komt uit DUO p01hoinges."
    )


def test_de_historie_heeft_geen_uitgangspunt_en_geen_telling():
    berichten = chat._parse_history(
        [{"role": "user", "content": _VRAAG}, {"role": "assistant", "content": _opgemaakt()}]
    )

    [vraag, antwoord] = berichten
    assert vraag == {"role": "user", "content": _VRAAG}
    assert "**Uitgangspunt:**" not in antwoord["content"] and "**Telling**" not in antwoord["content"]
    assert _DEFINITIE not in antwoord["content"]
    assert antwoord["content"] == (
        f"Ik ga uit van alle studenten.\n\n{_ANTWOORD}\n\n**Bron en definitie:** dit cijfer komt uit DUO p01hoinges."
    )


def test_een_gebruikersbericht_met_die_koppen_blijft_zoals_het_is():
    """Alleen antwoorden: wat de gebruiker typte, gaat ongewijzigd naar het model."""
    vraag = f"Klopt dit?\n\n{_EIGEN_TELLING}"
    assert chat._parse_history([{"role": "user", "content": vraag}]) == [{"role": "user", "content": vraag}]


def test_een_weggehaald_blok_telt_niet_mee_voor_de_tekencap(monkeypatch):
    """Het antwoord past zonder zijn blokken binnen de cap; met de blokken erbij viel de vraag ervoor af."""
    kaal = zonder_vaste_blokken({"role": "assistant", "content": _opgemaakt()})["content"]
    monkeypatch.setattr(chat, "HISTORY_MAX_CHARS", len(_VRAAG) + len(kaal))
    assert len(_VRAAG) + len(_opgemaakt()) > chat.HISTORY_MAX_CHARS

    berichten = chat._parse_history(
        [{"role": "user", "content": _VRAAG}, {"role": "assistant", "content": _opgemaakt()}]
    )

    assert berichten == [{"role": "user", "content": _VRAAG}, {"role": "assistant", "content": kaal}]


def test_een_bericht_dat_alleen_een_blok_is_blijft_staan():
    """Een lege assistentbeurt geeft providers een 400: zo'n bericht blijft dan liever zoals het was."""
    bericht = {"role": "assistant", "content": _EIGEN_TELLING}
    assert zonder_vaste_blokken(bericht) is bericht


def _model(monkeypatch, antwoord: str) -> list[list[dict]]:
    """Een model zonder toolaanroep dat `antwoord` geeft; geeft de berichten terug die het per ronde kreeg."""
    gezien: list[list[dict]] = []

    async def fake_completion(*args, **kwargs):
        gezien.append([dict(m) for m in kwargs["messages"]])
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return StreamResult(text=antwoord, tool_calls=[])

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(run_module, "scopevraag", lambda vraag, settings, eerder=(): None)
    return gezien


async def _niets(event: dict) -> None:
    return None


def test_een_vervolgronde_stuurt_het_vorige_antwoord_zonder_blokken(monkeypatch):
    """Na heropenen: de berichten van de vervolgronde naar het model hebben de blokken uit code niet."""
    gezien = _model(monkeypatch, "Dat is 3% meer dan het jaar ervoor.")
    sessie = chat._new_session(username="alice")
    chat._open_conversation(
        sessie, [{"role": "user", "content": _VRAAG}, {"role": "assistant", "content": _opgemaakt()}]
    )

    asyncio.run(chat._process_message("En in 2022/23?", sessie, _niets, "openai/gpt-4o"))

    [eerdere] = [m for m in gezien[0] if m["role"] == "assistant"]
    assert "**Uitgangspunt:**" not in eerdere["content"] and "**Telling**" not in eerdere["content"]
    assert _ANTWOORD in eerdere["content"]


def test_in_een_levend_gesprek_gaat_het_antwoord_zonder_blokken_de_historie_in(monkeypatch):
    """Het antwoord van de beurt houdt zijn blokken (de gebruiker zag ze, de beurt bewaart ze); de historie niet."""
    sessie = chat._new_session(username="alice")

    async def nep_run(messages, session, emit, stop_event, model=None):
        return _opgemaakt()

    monkeypatch.setattr(chat, "agent_run", nep_run)
    asyncio.run(chat._process_message(_VRAAG, sessie, _niets, None))

    assert sessie["turns"][-1]["answer"] == _opgemaakt()
    laatste = sessie["messages"][-1]
    assert laatste["role"] == "assistant"
    assert "**Uitgangspunt:**" not in laatste["content"] and "**Telling**" not in laatste["content"]


def test_run_haalt_de_blokken_ook_uit_een_historie_die_ze_nog_heeft(monkeypatch):
    """Een gesprek dat niet via `_parse_history` binnenkwam (een sessie van vóór #1083): `run` haalt ze zelf weg."""
    gezien = _model(monkeypatch, "Dat is 3% meer.")
    messages = [
        {"role": "user", "content": _VRAAG},
        {"role": "assistant", "content": _opgemaakt()},
        {"role": "user", "content": "En in 2022/23?"},
    ]

    asyncio.run(run_module.run(messages, {}, _niets, asyncio.Event(), model="openai/gpt-4o"))

    [eerdere] = [m for m in gezien[0] if m["role"] == "assistant"]
    assert "**Telling**" not in eerdere["content"] and "**Uitgangspunt:**" not in eerdere["content"]
    # De sessie zelf houdt wat er stond: alleen wat naar het model gaat, verandert.
    assert messages[1]["content"] == _opgemaakt()
