"""Een instellingswissel midden in een gesprek is geen fout in een eerder antwoord (#543, BEV-01).

Na de wissel van Hogeschool Utrecht naar HAN in hetzelfde gesprek "corrigeerde" het model een
juist antwoord over HU. De code zegt het model in één vaste regel dat de wissel er was; een
nieuw gesprek na de wissel (D2b) krijgt die regel niet, want daar is geen eerder antwoord.
"""

import asyncio
import importlib
from types import SimpleNamespace
from unittest.mock import patch

from agent.instellingswissel import eerdere_instellingen, wisselcontext
from routes import chat

run_module = importlib.import_module("agent.run")  # agent.run is ook de naam van de functie


def test_wissel_noemt_de_vorige_en_de_nieuwe_instelling():
    regel = wisselcontext("HAN", ["Hogeschool Utrecht"])

    assert regel.startswith("Instellingswissel:")
    assert "Eerdere antwoorden gingen over **Hogeschool Utrecht** en waren daarvoor juist" in regel
    assert "noem ze niet onjuist" in regel
    assert "Beantwoord deze en volgende vragen voor **HAN**" in regel


def test_zonder_wissel_geen_regel():
    assert wisselcontext("HAN", []) == ""
    assert wisselcontext("HAN", ["HAN"]) == ""
    assert wisselcontext(" HAN ", ["HAN"]) == ""
    assert wisselcontext("", []) == ""
    assert wisselcontext(None, []) == ""


def test_terug_naar_een_eerdere_instelling_noemt_alleen_de_andere():
    regel = wisselcontext("Hogeschool Utrecht", ["Hogeschool Utrecht", "HAN"])

    assert "over **HAN** en waren" in regel
    assert "voor **Hogeschool Utrecht**" in regel


def test_meer_vorige_instellingen_worden_opgesomd():
    regel = wisselcontext("RUG", ["Hogeschool Utrecht", "HAN"])

    assert "over **Hogeschool Utrecht** en **HAN** en waren" in regel


def test_profiel_zonder_instelling_na_een_wissel():
    regel = wisselcontext("", ["Hogeschool Utrecht"])

    assert "over **Hogeschool Utrecht**" in regel
    assert "geen instelling" in regel
    assert "Beantwoord deze" not in regel


def test_eerdere_instellingen_elk_een_keer_en_zonder_lege():
    turns = [
        {"question": "a", "instelling": "Hogeschool Utrecht"},
        {"question": "b"},
        {"question": "c", "instelling": ""},
        {"question": "d", "instelling": " Hogeschool  Utrecht "},
        {"question": "e", "instelling": "HAN"},
    ]

    assert eerdere_instellingen(turns) == ["Hogeschool Utrecht", "HAN"]


# ─── De naad met de beurt en de chatroute ────────────────────────────────────


def _beurtcontext_van(session: dict) -> str:
    """De systeemtekst van deze beurt zoals de toolloop hem krijgt; leeg als er geen is."""
    meegegeven: dict = {}

    async def nep_loop(history, **kwargs):
        meegegeven.update(kwargs)
        return SimpleNamespace(aborted="tools")

    async def emit(_event):
        pass

    vraag = [{"role": "user", "content": "En hoeveel studenten hebben wij in 2024/25?"}]
    # Het profiel laadt de DUO-instellingenlijst: niet in deze test.
    with patch("prompts.instellingsprofiel", return_value=None), patch.object(run_module, "tool_loop", nep_loop):
        asyncio.run(run_module.run(vraag, session=session, emit=emit))
    content = meegegeven["system"][0]["content"]
    return content[-1]["text"] if len(content) > 1 else ""


def test_run_geeft_de_wissel_mee_aan_het_model():
    session = {
        "chat_settings": {"instelling": "HAN"},
        "turns": [
            {
                "question": "Hoeveel studenten hebben wij in 2023/24?",
                "answer": "36.206",
                "instelling": "Hogeschool Utrecht",
            }
        ],
    }

    beurt = _beurtcontext_van(session)

    assert "Instellingswissel" in beurt
    assert "**Hogeschool Utrecht**" in beurt
    assert "**HAN**" in beurt


def test_nieuw_gesprek_na_de_wissel_krijgt_geen_wisselregel():
    """D2b: in een nieuw gesprek is er geen eerder antwoord om te 'corrigeren'."""
    assert "Instellingswissel" not in _beurtcontext_van({"chat_settings": {"instelling": "HAN"}, "turns": []})


def test_zonder_wissel_geen_wisselregel():
    session = {"chat_settings": {"instelling": "HAN"}, "turns": [{"question": "a", "instelling": "HAN"}]}

    assert "Instellingswissel" not in _beurtcontext_van(session)


def test_elke_beantwoorde_beurt_onthoudt_de_instelling_van_dat_moment(monkeypatch):
    """De chatroute legt per beurt vast waarop 'wij' sloeg; een reset begint schoon."""

    async def nep_run(messages, session, emit, stop_event, model=None):
        return "36.206 studenten."

    async def emit(_event):
        pass

    monkeypatch.setattr(chat, "agent_run", nep_run)
    session = chat._new_session()
    session["chat_settings"] = {"instelling": "Hogeschool Utrecht"}
    asyncio.run(chat._process_message("Hoeveel studenten hebben wij in 2023/24?", session, emit, None))
    session["chat_settings"] = {"instelling": "HAN"}
    asyncio.run(chat._process_message("En hoeveel studenten hebben wij in 2024/25?", session, emit, None))

    assert [t["instelling"] for t in session["turns"]] == ["Hogeschool Utrecht", "HAN"]
    assert eerdere_instellingen(session["turns"]) == ["Hogeschool Utrecht", "HAN"]

    chat._reset_session(session)

    assert session["turns"] == [] and session["chat_settings"] == {"instelling": "HAN"}
