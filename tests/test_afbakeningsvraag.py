"""Een kale telling krijgt een afbakeningskaart, en een vraag kan tot drie kaarten achter elkaar krijgen.

"Hoeveel studenten?" noemt geen instelling, sector of gebied: het model koos dan stilzwijgend een
afbakening. Code vraagt nu eerst waarvoor het aantal is (slot `afbakening`, agent/scopevraag.py). Een
slot dat al gevraagd is, komt niet terug, en de beurt leest de vraag samen met de gekozen opties, zodat
een tweede open slot een tweede kaart krijgt (hoogstens `MAX_CLARIFY_RONDES`).
"""

import asyncio
import importlib
from unittest.mock import patch

import pytest

from agent import scopevraag as module
from agent.scopevraag import Kaart, afbakeningsvraag, scopevraag
from tools import instelling

_REGISTER = [
    {"naam": "Hogeschool Utrecht", "type": "hbo", "aliassen": ["HU"]},
    {"naam": "Universiteit Utrecht", "type": "wo", "aliassen": ["UU"]},
    {"naam": "Rijksuniversiteit Groningen", "type": "wo", "aliassen": ["RUG"]},
]


@pytest.fixture(autouse=True)
def register(monkeypatch):
    monkeypatch.setattr(module, "get_all", lambda: _REGISTER)
    monkeypatch.setattr(instelling, "get_all", lambda: _REGISTER)


@pytest.mark.parametrize(
    "vraag",
    [
        "Hoeveel studenten?",
        "hoeveel studenten zijn er",
        "Hoeveel studenten zijn er in 2023?",
        "Wat is het aantal studenten?",
        "Hoeveel leerlingen volgen informatica?",
    ],
)
def test_een_kale_telling_vraagt_waarvoor_het_aantal_is(vraag):
    kaart = afbakeningsvraag(vraag)
    assert kaart is not None and kaart.slot == "afbakening"
    assert [o["label"] for o in kaart.opties] == [
        "Landelijk: mbo, hbo en wo samen",
        "Per sector: mbo, hbo en wo naast elkaar",
    ]
    assert kaart.opties[0]["aanbevolen"] is True
    assert "Anders formuleren" in kaart.vraag  # een instelling of regio noem je daar


@pytest.mark.parametrize(
    "vraag",
    [
        "Hoeveel studenten heeft de RUG?",  # instelling
        "Hoeveel studenten heeft de HU?",
        "Hoeveel hbo-studenten zijn er?",  # sector
        "Hoeveel studenten volgen een mbo-opleiding?",
        "Hoeveel ingeschrevenen had het hoger onderwijs in 2023/24?",  # ho is hbo en wo samen
        "Hoeveel studenten volgen wetenschappelijk onderwijs?",
        "Hoeveel leerlingen zaten er in 2022 in groep 8?",  # po: de poort ervoor laat hem na een ho-vraag door
        "Hoeveel leerlingen zitten er op de basisschool?",
        "Hoeveel studenten zijn er landelijk?",
        "Hoeveel studenten zijn er in Nederland?",
        "Hoeveel studenten zijn er per provincie?",
        "Hoeveel studenten volgen Informatica?",  # een eigennaam midden in de zin
        "Hoeveel studenten wonen in Zwolle?",
        "Wat kost het collegegeld?",  # geen telling van personen
        "Hoeveel kost een opleiding?",
        "Welke datasets zijn er over studenten?",
        "studentenwelzijn",
    ],
)
def test_een_vraag_met_afbakening_of_zonder_telling_krijgt_geen_afbakeningskaart(vraag):
    assert afbakeningsvraag(vraag) is None


def test_het_profiel_bepaalt_de_afbakening():
    assert afbakeningsvraag("Hoeveel studenten?", {"instelling": "Hogeschool Utrecht"}) is None
    assert afbakeningsvraag("Hoeveel studenten?", {"domein": "mbo"}) is None
    assert afbakeningsvraag("Hoeveel studenten?", {"domein": "iets anders"}) is not None


def _slot(kaart: Kaart | None) -> str:
    assert kaart is not None
    return kaart.slot


def test_scopevraag_vraagt_de_afbakening_na_scope_maat_en_fase():
    assert _slot(scopevraag("Hoeveel studenten?")) == "afbakening"
    assert _slot(scopevraag("Hoeveel studenten heeft Utrecht?")) == "scope"


def test_een_slot_dat_al_gevraagd_is_komt_niet_terug():
    assert scopevraag("Hoeveel studenten?", None, eerder={"afbakening"}) is None
    assert scopevraag("Hoeveel studenten heeft Utrecht?", None, eerder={"scope"}) is None
    # Een ander open slot mag nog wel.
    assert _slot(scopevraag("Hoeveel studenten heeft Utrecht?", None, eerder={"afbakening"})) == "scope"


def test_de_gekozen_afbakening_sluit_het_slot_ook_zonder_geheugen():
    for keuze in ("Landelijk: mbo, hbo en wo samen", "Per sector: mbo, hbo en wo naast elkaar"):
        assert afbakeningsvraag(f"Hoeveel studenten? {keuze}") is None


def test_de_kaart_heeft_twee_of_drie_opties_met_een_label():
    kaart = afbakeningsvraag("Hoeveel studenten?")
    assert isinstance(kaart, Kaart) and 2 <= len(kaart.opties) <= 3 and all("label" in o for o in kaart.opties)


# --- de beurt: meerdere kaarten achter elkaar ---------------------------------------------------


def _beurt(messages: list[dict], session: dict) -> tuple[str, list[dict]]:
    run_module = importlib.import_module("agent.run")
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    async def geen_model(*args, **kwargs):
        raise AssertionError("het model is aangeroepen")

    with (
        patch.object(run_module, "tool_loop", geen_model),
        patch.object(run_module, "build_system", lambda *a, **k: []),
    ):
        tekst = asyncio.run(run_module.run(messages, session, emit))
    return tekst, events


def test_de_beurt_stelt_de_afbakeningskaart_zonder_het_model():
    session = {"chat_settings": {}, "clarify_rondes": 0}
    messages = [{"role": "user", "content": "Hoeveel studenten?"}]
    tekst, events = _beurt(messages, session)
    assert tekst == ""
    assert [e["type"] for e in events] == ["clarification"]
    assert session["clarify_slots"] == ["afbakening"]
    assert messages[-1] == {"role": "assistant", "content": events[0]["vraag"]}


def test_na_de_gekozen_afbakening_gaat_de_vraag_naar_het_model():
    session = {"chat_settings": {}, "clarify_rondes": 1, "clarify_slots": ["afbakening"]}
    messages = [
        {"role": "user", "content": "Hoeveel studenten?"},
        {"role": "assistant", "content": "Waarvoor wil je het aantal?"},
        {"role": "user", "content": "Landelijk: mbo, hbo en wo samen"},
    ]
    with pytest.raises(AssertionError, match="het model is aangeroepen"):
        _beurt(messages, session)


def test_een_tweede_open_slot_krijgt_een_tweede_kaart():
    """De vraag wordt samen met de keuze gelezen: na de fasekeuze is de plaats nog open."""
    session = {"chat_settings": {}, "clarify_rondes": 1, "clarify_slots": ["fase"]}
    messages = [
        {"role": "user", "content": "Hoeveel studenten heeft Utrecht?"},
        {"role": "assistant", "content": "Welke instroom bedoel je?"},
        {"role": "user", "content": "Ook masters: landelijk per hbo en wo (CBS 85422NED)"},
    ]
    _, events = _beurt(messages, session)
    assert [e["type"] for e in events] == ["clarification"]
    assert "Utrecht" in events[0]["vraag"]
    assert session["clarify_slots"] == ["fase", "scope"]


def test_hetzelfde_slot_wordt_niet_twee_keer_gevraagd():
    session = {"chat_settings": {}, "clarify_rondes": 1, "clarify_slots": ["scope"]}
    messages = [
        {"role": "user", "content": "Hoeveel studenten heeft Utrecht?"},
        {"role": "assistant", "content": "Over welke 'Utrecht' gaat je vraag?"},
        {"role": "user", "content": "Studenten die in Utrecht wonen (gemeente of provincie)"},
    ]
    with pytest.raises(AssertionError, match="het model is aangeroepen"):
        _beurt(messages, session)


def test_na_drie_rondes_vraagt_code_niets_meer():
    session = {"chat_settings": {}, "clarify_rondes": 3, "clarify_slots": []}
    messages = [{"role": "user", "content": "Hoeveel studenten?"}]
    with pytest.raises(AssertionError, match="het model is aangeroepen"):
        _beurt(messages, session)
