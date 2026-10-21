"""Een vraag buiten mbo/hbo/wo krijgt de vaste scope-uitleg, niet de tooltaal van het model (BEV-12).

Testronde 14 okt: op "Hoeveel leerlingen zaten er in 2022 in groep 8?" zei het antwoord "De tool weigerde
mijn selectie", zonder de reden in gewone taal. Code beslist (#191): zonder geladen data en op de
scopegrens is het antwoord de vaste uitleg uit `agent/vaste_antwoorden.py`.
"""

import asyncio
import importlib
import json

import pytest

from agent.stream import StreamResult
from agent.vaste_antwoorden import SCOPE_UITLEG, scope_uitleg
from tools import scopeprofiel

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")

GROEP_8 = "Hoeveel leerlingen zaten er in 2022 in groep 8?"
TOOLTAAL = "De tool weigerde mijn selectie."
_PO_TABEL = json.dumps(scopeprofiel.buiten_scope("CBS"), ensure_ascii=False)
_REGISTER = json.dumps(scopeprofiel.buiten_scope("RIO", register=True), ensure_ascii=False)
# Wat het CBS-contract zegt als de code niet bij de sector past (tools/cbs_preflight.py).
_CONTRACT = (
    "Selectie voor 85525NED geweigerd door het CBS-contract: code hoort niet bij sector mbo. "
    "Kies codes uit get_cbs_dimension en een periode die in de tabel voorkomt."
)
# Een antwoord nadat het model een mbo/hbo/wo-bron in de catalogus vond, zonder data te laden (#563).
_UIT_CATALOGUS = "In de catalogus staat een DUO-bestand met studenten per opleiding; dat kan ik voor je ophalen."
_DATA = json.dumps({"data_key": "cbs:85525NED:ab", "rijen": [{"Perioden": "2022SJ00", "Leerlingen": 1}]})
# Na een ho-vraag laat de po-poort vóór het model (#647) een po-vraag door: dan vangt deze uitleg achteraf hem op.
_NA_HO = (
    {"role": "user", "content": "Hoeveel hbo-studenten zijn er?"},
    {"role": "assistant", "content": "Dat zoek ik voor je op."},
)


def test_uitleg_zegt_de_scope_in_gewone_taal():
    tekst = SCOPE_UITLEG.lower()
    assert "mbo, hbo en wo" in tekst
    assert "po, so en vo" in tekst and "behandelt de chat niet" in tekst
    assert "?" in SCOPE_UITLEG  # een voorbeeldvraag die wel kan
    for intern in ("de tool", "weiger", "selectie", "profiel", "catalogus"):
        assert intern not in tekst
    # Zeg niet dat de bron niet bestaat (scopeprofiel.MELDING, #355).
    assert "bestaat niet" not in tekst


def test_scopegrens_zonder_data_wordt_de_uitleg():
    assert scope_uitleg(TOOLTAAL, [_PO_TABEL], GROEP_8) == SCOPE_UITLEG
    # Ook als het model iets anders zegt: de toolstap beslist, niet de formulering.
    assert scope_uitleg("Daar heb ik geen cijfers voor.", [_PO_TABEL], "Hoeveel leerlingen?") == SCOPE_UITLEG
    # Een pure vo-vraag: "vwo" noemt geen mbo, hbo of wo.
    assert scope_uitleg("Daar heb ik geen cijfers voor.", [_PO_TABEL], "Hoeveel leerlingen zitten er in het vwo?") == (
        SCOPE_UITLEG
    )


def test_tooltaal_op_een_po_vraag_wordt_de_uitleg():
    assert scope_uitleg(TOOLTAAL, [_CONTRACT], GROEP_8) == SCOPE_UITLEG
    assert scope_uitleg("De selectie werd geweigerd.", [], "Hoeveel leerlingen zaten in het vmbo?") == SCOPE_UITLEG


@pytest.mark.parametrize(
    ("tekst", "results", "vraag"),
    [
        # Data geladen: het antwoord van het model blijft, ook naast een po-tabel.
        ("Het waren er 1.", [_PO_TABEL, _DATA], GROEP_8),
        # Een RIO-register zonder sectorfilter is geen po/so/vo-vraag.
        ("Dat register haal ik niet op.", [_REGISTER], "Welke onderwijslocaties heeft ROC Midden Nederland?"),
        # Tooltaal op een mbo-vraag: geen scopegrens, dus geen scope-uitleg.
        (TOOLTAAL, [_CONTRACT], "Hoeveel mbo-studenten waren er in 2022?"),
        # Een ho-vraag met vo-context valt niet buiten de scope (epic #554).
        (TOOLTAAL, [_CONTRACT], "Hoeveel hbo-eerstejaars kwamen van het vwo?"),
        # Een po-vraag zonder tooltaal en zonder scopegrens: het model zei het al zelf.
        ("Daar heb ik geen data over gevonden.", [], GROEP_8),
        # Eerst een po/so/vo-tabel, daarna een mbo/hbo/wo-bron uit de catalogus: de vraag noemt de scope (#563).
        *(
            (_UIT_CATALOGUS, [_PO_TABEL], vraag)
            for vraag in (
                "Hoeveel mbo-studenten waren er in 2022?",
                "Hoeveel hbo-eerstejaars kwamen van het vwo?",
                "Hoeveel wo-studenten waren er in 2022?",
                "Hoeveel ho-studenten waren er in 2022?",
                "Hoeveel studenten in het hoger onderwijs?",
                "Hoeveel studenten heeft de Hogeschool Utrecht?",
                "Hoeveel studenten heeft de Universiteit Leiden?",
                "Hoeveel studenten heeft het ROC Midden Nederland?",
            )
        ),
    ],
)
def test_andere_beurten_houden_hun_antwoord(tekst, results, vraag):
    assert scope_uitleg(tekst, results, vraag) is None


def _run(monkeypatch, vraag: str, tool_result: str, teksten: list[str], eerder: tuple[dict, ...] = ()):
    steps = [
        StreamResult(text="", tool_calls=[{"id": "c", "name": "get_cbs_data", "arguments": '{"dataset_id": "x"}'}]),
        *(StreamResult(text=t, tool_calls=[]) for t in teksten),
    ]

    async def fake_completion(*args, **kwargs):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return steps.pop(0)

    async def fake_execute_tool(call, emit, recept_van=None):
        return tool_result, None

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop_module, "_execute_tool", fake_execute_tool)
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    text = asyncio.run(
        run_module.run([*eerder, {"role": "user", "content": vraag}], {}, emit, asyncio.Event(), model="openai/gpt-4o")
    )
    assert len(steps) < 1 + len(teksten), "de beurt bereikte het model niet"  # deze tests gaan over de uitleg achteraf
    return text, events


@pytest.mark.parametrize("tool_result", [_PO_TABEL, _CONTRACT])
def test_groep_8_krijgt_de_vaste_uitleg_in_de_chat(monkeypatch, tool_result):
    text, events = _run(monkeypatch, GROEP_8, tool_result, [TOOLTAAL] * 3, eerder=_NA_HO)

    assert text == SCOPE_UITLEG
    end = events[-1]
    assert end["type"] == "message_end" and end["content"] == SCOPE_UITLEG
    assert end["bronnen"] == [] and "vervolgvragen" not in end
    assert end["vast"] is True  # geen "Antwoord van <model>" onder een tekst uit code (#565)
    for intern in ("de tool", "weigerde", "selectie"):
        assert intern not in end["content"].lower()


def test_een_getal_uit_het_geheugen_houdt_de_uitleg_niet_tegen(monkeypatch):
    """Het model noemde zonder data een getal: de uitleg rust niet op die tekst, dus wordt ze niet ingehouden."""
    text, events = _run(
        monkeypatch, GROEP_8, _PO_TABEL, ["In 2022 zaten er 183.000 leerlingen in groep 8."] * 3, eerder=_NA_HO
    )
    assert text == SCOPE_UITLEG
    assert events[-1]["content"] == SCOPE_UITLEG and "controle" not in events[-1]


def test_mbo_vraag_met_tooltaal_houdt_het_antwoord_van_het_model(monkeypatch):
    text, _ = _run(monkeypatch, "Hoeveel mbo-studenten waren er in 2022?", _CONTRACT, [TOOLTAAL] * 3)
    assert text != SCOPE_UITLEG


def test_mbo_vraag_na_een_scopegrens_houdt_het_antwoord_van_het_model(monkeypatch):
    """Een tool legde een po/so/vo-tabel buiten de scope, het model vond een mbo-bron: geen scope-uitleg (#563)."""
    vraag = "Hoeveel mbo-studenten waren er in 2022?"
    text, events = _run(monkeypatch, vraag, _PO_TABEL, [_UIT_CATALOGUS] * 3)

    assert text == _UIT_CATALOGUS
    end = events[-1]
    assert end["type"] == "message_end" and end["content"] != SCOPE_UITLEG
