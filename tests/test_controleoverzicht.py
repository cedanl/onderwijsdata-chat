"""Het veld `controles` op message_end: wat de antwoordcontrole bij een data-antwoord deed (#1260).

Bevroren data: één query_data-stap met 5.943 eerstejaars (zoals tests/test_chat_grounding.py); het model wordt
nagespeeld. Het veld komt uit code: welke controle draaide, hoeveel getallen zijn getoetst, of jaar en instelling zijn
nagelopen en hoe vaak het antwoord is ingetrokken. Wat het model over zijn eigen controle zegt, verandert niets.
"""

import asyncio
import importlib
import json
import re
from pathlib import Path

import pandas as pd
import pytest

from agent import controleoverzicht
from agent.controles import antwoordcontrole
from agent.stream import StreamResult
from tools import store
from tools.store import KeyMeta

pytestmark = pytest.mark.usefixtures("zonder_scopekaart")

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")

_KEY = "duo:p02:a"
_QUERY = {"id": "q", "name": "query_data", "arguments": json.dumps({"data_key": "duo:p02"})}
_ROWS = json.dumps({"data_key": _KEY, "rijen": [{"AANTAL": 5943}]})
_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _bron():
    store.clear()
    store.put(_KEY, pd.DataFrame({"AANTAL": [5943]}), KeyMeta(bron="duo", dataset="p02hoinges", resource=0))
    yield
    store.clear()


def _chat(monkeypatch, steps: list[StreamResult]) -> list[dict]:
    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return steps.pop(0)

    async def fake_execute_tool(call, emit, recept_van=None):
        return _ROWS, None

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop_module, "_execute_tool", fake_execute_tool)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    asyncio.run(
        run_module.run(
            [{"role": "user", "content": "Hoeveel eerstejaars?"}], {}, emit, asyncio.Event(), "openai/gpt-4o"
        )
    )
    return events


def _einde(events: list[dict]) -> dict:
    return next(e for e in events if e["type"] == "message_end")


def test_een_data_antwoord_draagt_per_controle_of_ze_draaide_en_de_tellingen(monkeypatch):
    einde = _einde(
        _chat(
            monkeypatch,
            [
                StreamResult(text="", tool_calls=[_QUERY]),
                StreamResult(text="In totaal 5.943 eerstejaars.", tool_calls=[]),
            ],
        )
    )
    assert einde["bronnen"], "geen data-antwoord: de test meet niets"
    controles = einde["controles"]
    assert controles["getallen"] == 1
    assert controles["ingetrokken"] == 0 and controles["gecorrigeerd"] == 0
    per = controles["per_controle"]
    assert per["ongedekte_getallen"] == {"gedraaid": True, "uitkomst": "ok"}
    assert all(per[naam]["gedraaid"] for naam in controleoverzicht.JAAR_EN_INSTELLING)
    assert controles["jaar_en_instelling"] is True
    assert controles["niet_gedraaid"] == 0


def test_een_ingetrokken_antwoord_telt_de_correctie(monkeypatch):
    events = _chat(
        monkeypatch,
        [
            StreamResult(text="", tool_calls=[_QUERY]),
            StreamResult(text="In totaal 6.340 eerstejaars.", tool_calls=[]),
            StreamResult(text="In totaal 5.943 eerstejaars.", tool_calls=[]),
        ],
    )
    assert any(e["type"] == "message_cancel" for e in events)
    assert _einde(events)["controles"]["ingetrokken"] == 1


def test_wat_het_model_over_zijn_controle_zegt_verandert_het_veld_niet(monkeypatch):
    einde = _einde(
        _chat(
            monkeypatch,
            [
                StreamResult(text="", tool_calls=[_QUERY]),
                StreamResult(text="Alle getallen gecontroleerd en geverifieerd: er zijn eerstejaars.", tool_calls=[]),
            ],
        )
    )
    assert einde["controles"]["getallen"] == 0
    assert einde["controles"]["ingetrokken"] == 0


def test_een_antwoord_zonder_data_heeft_geen_controles(monkeypatch):
    einde = _einde(_chat(monkeypatch, [StreamResult(text="Hallo, waarmee kan ik helpen?", tool_calls=[])]))
    assert einde["bronnen"] == []
    assert "controles" not in einde


def test_een_controle_die_niet_kon_draaien_telt_als_niet_gedraaid():
    overzicht = controleoverzicht.overzicht(
        {"ongedekte_getallen": "ok", "ontbrekende_schooljaren": "niet gecontroleerd"}, "12.345 studenten", [], 0, 0
    )
    assert overzicht["per_controle"]["ontbrekende_schooljaren"]["gedraaid"] is False
    assert overzicht["niet_gedraaid"] == 1
    assert overzicht["jaar_en_instelling"] is False
    assert overzicht["getallen"] == 1


def test_het_verslag_houdt_de_uitkomst_van_de_laatste_controle():
    verslag: dict[str, str] = {}
    check = antwoordcontrole("Hoeveel?", [], [], [], [], verslag=verslag)
    check("In totaal 6.340 eerstejaars.", [_ROWS])
    assert verslag["ongedekte_getallen"] == "hard"
    check("In totaal 5.943 eerstejaars.", [_ROWS])
    assert verslag["ongedekte_getallen"] == "ok"


def test_de_vaste_zin_niet_gecontroleerd_staat_zo_in_de_docs():
    """De regel onder het antwoord en "Wat dit niet dekt" in de architectuurdocs zeggen hetzelfde (#1260)."""
    js = (_ROOT / "frontend" / "src" / "controleRegel.js").read_text(encoding="utf-8")
    match = re.search(r"export const NIET_GECONTROLEERD =\s*'([^']+)'", js)
    assert match, "NIET_GECONTROLEERD niet gevonden in controleRegel.js"
    docs = (_ROOT / "docs" / "anti-hallucination-architecture.md").read_text(encoding="utf-8")
    sectie = docs.split("## Wat dit niet dekt", 1)[1].split("\n## ", 1)[0]
    assert match.group(1) in sectie
