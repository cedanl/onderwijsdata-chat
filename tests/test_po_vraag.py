"""Een po/so/vo-vraag zonder ho-context krijgt de scope-uitleg uit code, vóór kaart en model (#647).

Audit 20 okt (C2, C2b, C11): "groep 8" en "basisschool" gingen naar het model. Dat bood het totaal
basisonderwijs uit 85701NED aan, deed een `get_cbs_data`-ronde en stelde bij "basisschool in Utrecht"
eerst de plaatskaart. Code beslist (#191): de vaste `SCOPE_UITLEG`, zonder modelronde en zonder kaart.
"""

import asyncio
import importlib

import pytest

from agent import scopevraag as scopevraag_module
from agent import vo_school
from agent.po_vraag import po_vraag
from agent.scopevraag import scopevraag
from agent.stream import StreamResult
from agent.vaste_antwoorden import SCOPE_UITLEG
from tests.test_scopevraag import _REGISTER
from tools import instelling

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")

C2 = "Hoeveel leerlingen zitten er in groep 8?"
C2B = "Ja, geef het totaal basisonderwijs 2022/23"
C11 = "Hoeveel kinderen zitten er op de basisschool in Utrecht?"
VWO = "Hoeveel leerlingen zitten er op het vwo?"
# Wat het model na C2 aanbood (audit 20 okt): het totaal basisonderwijs uit de woonregiotabel.
_AANBOD = "Ik kan het totaal aantal leerlingen in het basisonderwijs uit CBS-tabel 85701NED voor je ophalen."


@pytest.fixture(autouse=True)
def register(monkeypatch):
    for module in (scopevraag_module, vo_school, instelling):
        monkeypatch.setattr(module, "get_all", lambda: _REGISTER)


# --- de functie ------------------------------------------------------------------------------


@pytest.mark.parametrize("vraag", [C2, C2B, C11, VWO])
def test_een_po_of_vo_vraag_krijgt_de_scope_uitleg(vraag):
    assert po_vraag(vraag) == SCOPE_UITLEG


def test_ook_na_een_vorige_po_vraag():
    assert po_vraag(C2B, vorige_vraag=C2) == SCOPE_UITLEG


@pytest.mark.parametrize(
    ("vraag", "vorige"),
    [
        # Een ho-vraag met vo-context blijft bij het model (epic #554, #597).
        ("Hoeveel hbo-eerstejaars kwamen van het vwo?", ""),
        ("Hoeveel vwo-leerlingen stromen door naar het wo?", ""),
        ("Aansluiting vo-hbo?", ""),
        ("Wat is de doorstroom van havo naar hbo?", ""),
        ("Hoeveel leerlingen met een vwo-diploma gaan naar het hoger onderwijs?", ""),
        ("Hoeveel havisten kiezen een opleiding aan een van de hogescholen na de havo?", ""),
        # De bredere guard van de vo-schooluitleg: eerstejaars, studenten, mbo, roc, universiteit, hogeschool.
        ("Hoeveel eerstejaars hadden het vwo als vooropleiding?", ""),
        ("Hoeveel mbo-studenten komen van het vmbo?", ""),
        ("Hoeveel studenten van het vwo gaan naar de UvA?", ""),
        ("Hoeveel vmbo-leerlingen gaan naar een roc?", ""),
        # Een registerinstelling zonder ho-woord: de afkorting HU (Hogeschool Utrecht).
        ("Hoeveel vwo-leerlingen kiezen voor de HU?", ""),
        # De vorige vraag van de gebruiker noemt het ho of een instelling.
        ("En hoeveel van het havo?", "Hoeveel hbo-studenten zijn er?"),
        ("En van het vwo?", "Hoeveel eerstejaars heeft de HU?"),
        ("En hoeveel van het vwo?", "Wat weet je over de HU?"),
        # Alleen het Engelse "so" of een losse "bo": geen po/so/vo-vraag.
        ("So, what can you tell me about the data?", ""),
        ("So what about bo?", ""),
        # Geen po/so/vo-woord.
        ("Hoeveel studenten heeft Utrecht?", ""),
        ("Welke opleidingen zijn er?", ""),
    ],
)
def test_ho_context_of_geen_po_woord_gaat_naar_het_model(vraag, vorige):
    assert po_vraag(vraag, vorige_vraag=vorige) is None


def test_so_naast_een_ander_po_woord_telt_wel():
    assert po_vraag("So, hoeveel leerlingen zitten er in groep 8?") == SCOPE_UITLEG


def test_het_register_laadt_alleen_als_de_goedkope_toetsen_niets_beslissen(monkeypatch):
    geladen: list[str] = []

    def laden():
        geladen.append("register")
        return _REGISTER

    monkeypatch.setattr(instelling, "get_all", laden)
    assert po_vraag("Hoeveel studenten heeft Utrecht?") is None
    assert po_vraag("Hoeveel hbo-eerstejaars kwamen van het vwo?") is None
    assert po_vraag("En hoeveel van het havo?", vorige_vraag="Hoeveel hbo-studenten zijn er?") is None
    assert geladen == []

    assert po_vraag(C2) == SCOPE_UITLEG
    assert geladen


def test_zonder_register_beslissen_de_woorden(monkeypatch):
    """Offline noemt een vraag geen registerinstelling (`instelling.noemt_instelling`): de woorden beslissen."""

    def kapot():
        raise OSError("DUO niet bereikbaar")

    monkeypatch.setattr(instelling, "get_all", kapot)
    assert po_vraag(C2) == SCOPE_UITLEG
    assert po_vraag("Hoeveel hbo-eerstejaars kwamen van het vwo?") is None


# --- de beurt: vóór de kaart en vóór het model -----------------------------------------------


class _NaarHetModel(Exception):
    pass


def _modeldubbel(monkeypatch, aanroepen: list[str], *, stoppen: bool = False) -> None:
    """Een model dat het po-totaal aanbiedt (eerst `get_cbs_data` op 85701NED); telt elke aanroep.

    Met `stoppen` breekt de eerste modelaanroep de beurt af: zo is te zien dat de vraag het model bereikte.
    """
    steps = [
        StreamResult(
            text="", tool_calls=[{"id": "c", "name": "get_cbs_data", "arguments": '{"dataset_id": "85701NED"}'}]
        ),
        *(StreamResult(text=_AANBOD, tool_calls=[]) for _ in range(3)),
    ]

    async def completion(*args, **kwargs):
        aanroepen.append("model")
        if stoppen:
            raise _NaarHetModel
        return object()

    async def accumulate(stream, stop_event=None, emit=None):
        aanroepen.append("stream")
        return steps.pop(0)

    async def execute_tool(call, emit, recept_van=None):
        aanroepen.append(f"tool:{call.name}")
        return '{"data_key": "cbs:85701NED:x", "rijen": []}', None

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", accumulate)
    monkeypatch.setattr(loop_module, "_execute_tool", execute_tool)


def _beurt(messages: list[dict], session: dict | None = None) -> tuple[str, list[dict]]:
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    session = {"chat_settings": {}, "clarify_rondes": 0} if session is None else session
    tekst = asyncio.run(run_module.run(messages, session, emit, asyncio.Event(), model="openai/gpt-4o"))
    return tekst, events


def _vraag(tekst: str) -> dict:
    return {"role": "user", "content": tekst}


_GESPREKKEN = {
    "C2": [_vraag(C2)],
    "C2b": [_vraag(C2), {"role": "assistant", "content": _AANBOD}, _vraag(C2B)],
    "C11": [_vraag(C11)],
}


@pytest.mark.parametrize("gesprek", sorted(_GESPREKKEN))
def test_de_issuevragen_krijgen_de_uitleg_zonder_model_en_zonder_tool(monkeypatch, gesprek):
    aanroepen: list[str] = []
    _modeldubbel(monkeypatch, aanroepen)

    tekst, events = _beurt(list(_GESPREKKEN[gesprek]))

    assert aanroepen == []  # geen modelronde, geen get_cbs_data
    assert tekst == SCOPE_UITLEG
    assert [e["type"] for e in events] == ["message_start", "message_end"]
    # vast: de tekst komt uit code, dus geen "Antwoord van <model>" eronder (#565); geen bronnen.
    assert events[-1] == {"type": "message_end", "content": SCOPE_UITLEG, "actions": [], "bronnen": [], "vast": True}
    for aanbod in ("ophalen", "85701", "totaal aantal"):
        assert aanbod not in tekst


def test_de_uitleg_komt_voor_de_plaatskaart(monkeypatch):
    """C11: zonder de poort gaf "basisschool in Utrecht" de plaatskaart; een ho-telling bij Utrecht houdt hem."""
    assert scopevraag(C11) is not None  # de kaart die de poort voor is

    tekst, events = _beurt([_vraag(C11)])
    assert tekst == SCOPE_UITLEG
    assert "clarification" not in [e["type"] for e in events]

    tekst, events = _beurt([_vraag("Hoeveel studenten heeft Utrecht?")])
    assert tekst == ""
    assert [e["type"] for e in events] == ["clarification"]
    assert [o["label"] for o in events[0]["opties"]][:2] == ["Universiteit Utrecht", "Hogeschool Utrecht"]


@pytest.mark.usefixtures("zonder_scopekaart")
@pytest.mark.parametrize(
    "gesprek",
    [
        [_vraag("Hoeveel hbo-eerstejaars kwamen van het vwo?")],
        [_vraag("Hoeveel vwo-leerlingen stromen door naar het wo?")],
        [_vraag("Aansluiting vo-hbo?")],
        [_vraag("Wat is de doorstroom van havo naar hbo?")],
        [_vraag("Hoeveel eerstejaars hadden het vwo als vooropleiding?")],
        [_vraag("Hoeveel mbo-studenten komen van het vmbo?")],
        [_vraag("Hoeveel studenten van het vwo gaan naar de UvA?")],
        [
            _vraag("Hoeveel hbo-studenten zijn er?"),
            {"role": "assistant", "content": "Dat zoek ik op."},
            _vraag("En hoeveel van het havo?"),
        ],
        [_vraag("So, what can you tell me about the data?")],
    ],
)
def test_een_vraag_met_ho_context_bereikt_het_model(monkeypatch, gesprek):
    aanroepen: list[str] = []
    _modeldubbel(monkeypatch, aanroepen, stoppen=True)

    with pytest.raises(_NaarHetModel):
        _beurt(list(gesprek))
    assert aanroepen == ["model"]


@pytest.mark.usefixtures("zonder_scopekaart")
def test_een_keuze_op_een_kaart_gaat_naar_het_model(monkeypatch):
    """Na een verduidelijkingskaart is het bericht een keuze, geen nieuwe vraag: de poort beslist niet."""
    gesprek = [
        _vraag("Hoeveel leerlingen?"),
        {"role": "assistant", "content": "Welke leerlingen bedoel je?"},
        _vraag("Leerlingen in groep 8"),
    ]
    aanroepen: list[str] = []
    _modeldubbel(monkeypatch, aanroepen, stoppen=True)

    with pytest.raises(_NaarHetModel):
        _beurt(list(gesprek), {"chat_settings": {}, "clarify_rondes": 1})
    assert aanroepen == ["model"]

    # Dezelfde tekst als nieuwe vraag krijgt de uitleg.
    aanroepen.clear()
    assert _beurt(list(gesprek))[0] == SCOPE_UITLEG
    assert aanroepen == []
