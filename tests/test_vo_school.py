"""Een vo-schoolnaam krijgt de scope-uitleg uit code, vóór elke kaart en zonder model (#549, #355).

"Hoeveel leerlingen heeft het Erasmus Gymnasium in Rotterdam?" kreeg de kaart "Over welke 'Rotterdam'
gaat je vraag?" met de Erasmus Universiteit als optie: een stille herinterpretatie van een vo-vraag.
"""

import asyncio
import importlib
from unittest.mock import patch

import pytest

from agent import scopevraag as scopevraag_module
from agent import vo_school
from agent.vaste_antwoorden import VO_ANTWOORD
from agent.vo_school import vo_schoolvraag
from tests.test_scopevraag import _REGISTER
from tools import instelling

run_module = importlib.import_module("agent.run")

_REGISTER_ROTTERDAM = [
    *_REGISTER,
    {"naam": "Erasmus Universiteit Rotterdam", "type": "wo", "aliassen": ["EUR"]},
    {"naam": "Hogeschool Rotterdam", "type": "hbo", "aliassen": []},
    {"naam": "Deltion College", "type": "mbo", "aliassen": ["Deltion"]},
    {"naam": "Alfa-college", "type": "mbo", "aliassen": ["Alfa"]},
    {"naam": "Koning Willem I College", "type": "mbo", "aliassen": []},
]


def _met_register(monkeypatch, register):
    for module in (vo_school, scopevraag_module, instelling):
        monkeypatch.setattr(module, "get_all", lambda: register)


@pytest.fixture(autouse=True)
def register(monkeypatch):
    _met_register(monkeypatch, _REGISTER_ROTTERDAM)


@pytest.mark.parametrize(
    "vraag",
    [
        "Hoeveel leerlingen heeft het Erasmus Gymnasium in Rotterdam?",
        "Hoeveel leerlingen heeft het Erasmiaans Gymnasium?",
        "Hoeveel leerlingen heeft het Barlaeus Gymnasium Amsterdam?",
        "Hoeveel leerlingen heeft het Christelijk Lyceum Zeist?",
        "erasmus gymnasium rotterdam leerlingen aantal",
        "HOEVEEL LEERLINGEN HEEFT HET ERASMUS GYMNASIUM?",
        "Hoeveel leerlingen heeft het Erasmus gymnasium?",
        "Hoeveel leerlingen heeft het Gymnasium Haganum?",
        "Hoeveel leerlingen heeft Het Amsterdams Lyceum?",
        "Hoeveel leerlingen telt het Montessori Lyceum?",
        "Hoeveel leerlingen heeft het Stedelijk Gymnasium Leiden in 2024?",
        "Hoeveel leerlingen heeft de Openbare Scholengemeenschap Bijlmer?",
        "Hoeveel leerlingen heeft het Erasmus-Gymnasium?",
        "Hoeveel leerlingen heeft het Mendel College?",
    ],
)
def test_een_vo_schoolnaam_krijgt_het_vaste_vo_antwoord(vraag):
    assert vo_schoolvraag(vraag) == VO_ANTWOORD


@pytest.mark.parametrize(
    "vraag",
    [
        "Hoeveel studenten heeft de Erasmus Universiteit Rotterdam?",
        "Hoeveel studenten heeft Hogeschool Rotterdam?",
        "Hoeveel studenten heeft Grafisch Lyceum Rotterdam?",  # mbo, staat in het register
        "Hoeveel studenten heeft Grafisch Lyceum Utrecht?",
        "Hoeveel studenten heeft Deltion College?",
        "Hoeveel studenten heeft deltion college?",
        "Hoeveel studenten heeft het Alfa College?",  # register: "Alfa-college"
        "Hoeveel studenten heeft het Koning Willem I College?",
        "Hoeveel studenten heeft Rotterdam?",
        # Een vo-woord als vooropleiding, zonder schoolnaam (epic #554).
        "Hoeveel eerstejaars kwamen van het vwo of gymnasium?",
        "Hoeveel eerstejaars kwamen van het VWO of Gymnasium?",
        "Gymnasium of atheneum: hoeveel eerstejaars kwamen daarvandaan?",
        "Hoeveel wo-studenten hebben vooropleiding gymnasium?",
        "Vooropleiding gymnasium: hoeveel hbo-studenten?",
        "hoeveel studenten met een categoriaal gymnasium als vooropleiding",
        "Hoeveel studenten van het Erasmus Gymnasium gaan naar de universiteit?",  # ho-vraag met vo-context
        "Hoeveel studenten heeft het University College Utrecht?",
        "Wat zegt het College van Bestuur?",
        "Hoeveel studenten heeft de HU?",
    ],
)
def test_mbo_hbo_wo_vragen_krijgen_geen_vo_antwoord(vraag):
    assert vo_schoolvraag(vraag) is None


def test_de_registerspelling_van_een_mbo_naam_telt_ook():
    """In het echte register heet het Grafisch Lyceum Rotterdam "Grafisch Lyceum R'dam": de vraag noemt die naam
    dan niet letterlijk, maar "Grafisch Lyceum" is een registernaam en geen vo-school."""
    register = [{"naam": "Grafisch Lyceum R'dam", "type": "mbo", "aliassen": ["GLR"]}]
    with patch.object(vo_school, "get_all", lambda: register), patch.object(instelling, "get_all", lambda: register):
        assert vo_schoolvraag("Hoeveel studenten heeft Grafisch Lyceum Rotterdam?") is None
        assert vo_schoolvraag("Hoeveel leerlingen heeft het Erasmus Gymnasium?") == VO_ANTWOORD


def test_zonder_register_beslist_code_niet(monkeypatch):
    """Offline is een mbo-naam niet uit te sluiten: dan gaat de vraag naar model en scopepoort, zoals vroeger."""
    _met_register(monkeypatch, [])
    assert vo_schoolvraag("Hoeveel leerlingen heeft het Erasmus Gymnasium?") is None


def test_een_register_dat_niet_laadt_beslist_ook_niet(monkeypatch):
    def kapot():
        raise OSError("DUO onbereikbaar")

    _met_register(monkeypatch, [])
    monkeypatch.setattr(vo_school, "get_all", kapot)
    assert vo_schoolvraag("Hoeveel leerlingen heeft het Erasmus Gymnasium?") is None


def test_zonder_vo_schoolnaam_laadt_het_register_niet(monkeypatch):
    def niet_laden():
        raise AssertionError("register geladen")

    monkeypatch.setattr(vo_school, "get_all", niet_laden)
    monkeypatch.setattr(instelling, "get_all", niet_laden)
    assert vo_schoolvraag("Hoeveel studenten heeft Hogeschool Utrecht?") is None


def test_het_vo_antwoord_noemt_de_scope_zonder_cijfers_en_met_voorbeelden():
    assert "mbo, hbo en wo" in VO_ANTWOORD
    assert "voortgezet onderwijs" in VO_ANTWOORD
    assert not any(c.isdigit() for c in VO_ANTWOORD)
    assert "bestaat niet" not in VO_ANTWOORD
    assert VO_ANTWOORD.count("?") >= 2


# --- de beurt: vóór de kaart en vóór het model ---------------------------------------------


class _NaarHetModel(Exception):
    pass


def _beurt(vraag: str, events: list[dict] | None = None) -> tuple[str, list[dict]]:
    events = [] if events is None else events

    async def emit(event):
        events.append(event)

    async def model(*args, **kwargs):
        raise _NaarHetModel

    messages = [{"role": "user", "content": vraag}]
    session = {"chat_settings": {}, "clarify_rondes": 0}
    with (
        patch.object(run_module, "tool_loop", model),
        patch.object(run_module, "build_system", lambda *a, **k: []),
    ):
        tekst = asyncio.run(run_module.run(messages, session, emit))
    return tekst, events


def _vo_antwoord_zonder_model(tekst: str, events: list[dict]) -> None:
    assert tekst == VO_ANTWOORD
    assert [e["type"] for e in events] == ["message_start", "message_end"]
    assert events[-1] == {"type": "message_end", "content": VO_ANTWOORD, "actions": [], "bronnen": []}


def test_de_vo_vraag_komt_voor_de_scopevraag_en_het_model():
    with patch.object(run_module, "scopevraag", side_effect=AssertionError("scopevraag aangeroepen")):
        tekst, events = _beurt("Hoeveel leerlingen heeft het Erasmus Gymnasium in Rotterdam?")
    _vo_antwoord_zonder_model(tekst, events)


def test_met_de_echte_scopevraag_wint_het_vo_antwoord_van_de_plaatskaart():
    _vo_antwoord_zonder_model(*_beurt("Hoeveel leerlingen heeft het Erasmus Gymnasium in Rotterdam?"))


def test_een_plaats_krijgt_nog_steeds_de_kaart():
    tekst, events = _beurt("Hoeveel studenten heeft Rotterdam?")
    assert tekst == ""
    assert [e["type"] for e in events] == ["clarification"]
    assert "Rotterdam" in events[0]["vraag"]


def test_een_genoemde_universiteit_gaat_naar_het_model():
    events: list[dict] = []
    with pytest.raises(_NaarHetModel):
        _beurt("Hoeveel studenten heeft de Erasmus Universiteit Rotterdam?", events)
    assert events == []
