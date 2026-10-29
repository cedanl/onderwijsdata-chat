"""Het rapport ziet de bijsturing uit het gesprek (#733).

Na "Ik wil het alleen zien voor universitaire bachelor's. Geen verwante opleidingen" maakte de chat een wo-selectie,
maar het rapport tekende de wo+hbo-analyse van de eerste vraag: het rapportmodel kreeg alleen die eerste vraag en alle
datasets, zonder te weten welke selectie bij welke vraag hoorde. Nu staan de vragen in de prompt, en per dataset bij
welke vraag hij ontstond. Alleen in de prompt: wat de gebruiker zei is geen bewijs (#211).
"""

import asyncio
import json

import pandas as pd
import pytest

from agent import report
from agent.loop import LoopResult
from agent.session_data import gebruikersvragen, record_data_key
from tools import store
from tools.store import KeyMeta

_VRAAG_1 = "Hoe is de trend van instroom in B Computing Science, B Informatica en B Computer Science?"
_VRAAG_2 = "Ik wil het alleen zien voor universitaire bachelor's. Geen verwante opleidingen"
_BREED = "duo:p02ho1ejrs:5:breed"
_WO = "duo:p02ho1ejrs:5:wo"


def _vraag(sessie: dict, tekst: str) -> None:
    sessie.setdefault("messages", []).append({"role": "user", "content": tekst})


def _antwoord(sessie: dict, tekst: str = "Zie de tabel.") -> None:
    sessie["messages"].append({"role": "assistant", "content": tekst})


def test_een_key_onthoudt_bij_welke_vraag_hij_ontstond():
    sessie: dict = {}
    _vraag(sessie, _VRAAG_1)
    record_data_key(sessie, json.dumps({"data_key": _BREED}))
    _antwoord(sessie)
    _vraag(sessie, _VRAAG_2)
    record_data_key(sessie, json.dumps({"data_key": _WO}))
    # Dezelfde key later nog eens: hij ontstond bij de eerste.
    record_data_key(sessie, json.dumps({"data_key": _BREED}))

    assert sessie["data_vraag"] == {_BREED: 1, _WO: 2}
    assert gebruikersvragen(sessie) == [_VRAAG_1, _VRAAG_2]


def test_zonder_vraag_geen_vraagnummer():
    sessie: dict = {"messages": [{"role": "assistant", "content": "Welkom"}, {"role": "user", "content": "  "}]}
    record_data_key(sessie, json.dumps({"data_key": _BREED}))

    assert "data_vraag" not in sessie and sessie["data_keys"] == [_BREED]


@pytest.fixture
def sessie():
    for key in (_BREED, _WO):
        store.put(
            key,
            pd.DataFrame({"OPLEIDING": ["B Informatica (wo)"], "AANTAL": [345]}),
            KeyMeta("duo", "p02ho1ejrs", resource=5),
        )
    s: dict = {"data_keys": [_BREED, _WO]}
    _vraag(s, _VRAAG_1)
    _antwoord(s)
    _vraag(s, _VRAAG_2 + "\n\nEn graag   per jaar.")
    s["data_vraag"] = {_BREED: 1, _WO: 2}
    return s


def _prompt_en_problemen(sessie, monkeypatch, conclusie: str = "De instroom daalt."):
    gezien: dict = {}

    async def loop(messages, *, check, **_):
        gezien["prompt"] = messages[0]["content"]
        tekst = json.dumps({"beantwoordt": ["x"], "beantwoordt_niet": ["y"], "conclusie": conclusie})
        gezien["problemen"] = check(tekst, [])
        return LoopResult(text=tekst)

    async def stil(_event):
        pass

    monkeypatch.setattr(report, "tool_loop", loop)
    asyncio.run(report.generate(sessie, stil))
    return gezien


def test_de_prompt_noemt_de_vragen_en_per_dataset_de_vraag_waarbij_hij_ontstond(sessie, monkeypatch):
    prompt = _prompt_en_problemen(sessie, monkeypatch)["prompt"]

    assert "## Vragen van de gebruiker in dit gesprek" in prompt
    assert f"1. {_VRAAG_1}" in prompt
    # Op één regel, zoals de rest van de prompt.
    assert f"2. {_VRAAG_2} En graag per jaar." in prompt
    assert f"### {_BREED}\n- Rijen: 1\n- Ontstaan bij vraag: 1\n" in prompt
    assert f"### {_WO}\n- Rijen: 1\n- Ontstaan bij vraag: 2\n" in prompt


def test_een_heropend_gesprek_zonder_vraagnummers_noemt_wel_de_vragen(sessie, monkeypatch):
    del sessie["data_vraag"]

    prompt = _prompt_en_problemen(sessie, monkeypatch)["prompt"]

    assert f"1. {_VRAAG_1}" in prompt
    assert "- Ontstaan bij vraag:" not in prompt


def test_een_lange_vraag_wordt_ingekort(sessie, monkeypatch):
    sessie["messages"][-1]["content"] = "woord " * 400

    prompt = _prompt_en_problemen(sessie, monkeypatch)["prompt"]
    sectie = prompt.split("## Vragen van de gebruiker in dit gesprek", 1)[1]
    regel = next(r for r in sectie.splitlines() if r.startswith("2. "))

    assert len(regel) <= report._MAX_VRAAG_TEKENS + 3 and regel.endswith("…")


def test_een_getal_uit_een_vraag_van_de_gebruiker_is_geen_bewijs(sessie, monkeypatch):
    sessie["messages"][-1]["content"] = "Klopt het dat er 54321 eerstejaars waren?"

    problemen = _prompt_en_problemen(sessie, monkeypatch, "Er waren 54.321 eerstejaars.")["problemen"]

    assert any("54.321" in p for p in map(str, problemen))


def test_de_rapportprompt_zegt_dat_een_latere_bijsturing_voorgaat():
    werkwijze = report._PROMPT_PATH.read_text()

    assert "dan gaat die bijsturing voor" in werkwijze
    assert '"Ontstaan bij vraag"' in werkwijze
