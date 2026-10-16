"""Verduidelijking als slots-controle in code (#348): dezelfde vage vraag, altijd dezelfde eerste stap.

Audit 12: "Hoeveel studenten heeft Utrecht?" gaf de ene run negentien toolaanroepen zonder antwoord
en de andere een goede verduidelijking. Hier beslist code, vóór het model, met opties uit het
register en de catalogus.
"""

import asyncio
import importlib
from unittest.mock import patch

import pytest

from agent import scopevraag as module
from agent.scopevraag import Kaart, maatvraag, plaatsvraag, scopevraag
from tools import instelling, scopeprofiel

_REGISTER = [
    {"naam": "Hogeschool Utrecht", "type": "hbo", "aliassen": ["HU"]},
    {"naam": "Universiteit Utrecht", "type": "wo", "aliassen": ["UU"]},
    {"naam": "ROC Midden Nederland", "type": "mbo", "aliassen": []},
    {"naam": "Universiteit Twente", "type": "wo", "aliassen": ["UT"]},
    {"naam": "ROC van Twente", "type": "mbo", "aliassen": []},
    {"naam": "Rijksuniversiteit Groningen", "type": "wo", "aliassen": ["RUG"]},
    {"naam": "Hanzehogeschool Groningen", "type": "hbo", "aliassen": ["Hanze"]},
    {"naam": "Aeres Hogeschool", "type": "hbo", "aliassen": []},
    {"naam": "Christelijke Hogeschool Ede", "type": "hbo", "aliassen": ["CHE"]},
    # Merk- en soortwoorden vooraan zijn geen plaats, ook al staan ze in meer namen.
    {"naam": "Aeres MBO", "type": "mbo", "aliassen": []},
    {"naam": "Theologische Universiteit Utrecht", "type": "wo", "aliassen": []},
    {"naam": "Grafisch Lyceum Utrecht", "type": "mbo", "aliassen": []},
    {"naam": "Grafisch Lyceum Rotterdam", "type": "mbo", "aliassen": []},
]
_WOON_UTRECHT = "Studenten die in Utrecht wonen (gemeente of provincie)"


@pytest.fixture(autouse=True)
def register(monkeypatch):
    monkeypatch.setattr(module, "get_all", lambda: _REGISTER)
    monkeypatch.setattr(instelling, "get_all", lambda: _REGISTER)


# --- scope: plaats of instelling ---------------------------------------------------------


def test_een_telling_bij_een_plaats_vraagt_instelling_of_woonplaats():
    kaart = plaatsvraag("Hoeveel studenten heeft Utrecht?")
    assert kaart is not None and kaart.slot == "scope"
    assert "Utrecht" in kaart.vraag
    assert [o["label"] for o in kaart.opties] == ["Universiteit Utrecht", "Hogeschool Utrecht", _WOON_UTRECHT]


@pytest.mark.parametrize(
    "vraag", ["Hoeveel studenten heeft Utrecht?", "hoeveel studenten heeft utrecht", "Aantal studenten Utrecht 2024/25"]
)
def test_dezelfde_vraag_in_elke_spelling_geeft_dezelfde_kaart(vraag):
    assert scopevraag(vraag) == scopevraag("Hoeveel studenten heeft Utrecht?")


@pytest.mark.parametrize(
    "vraag",
    [
        "Hoeveel studenten heeft de Hogeschool Utrecht?",
        "Hoeveel studenten heeft de HU?",
        "Hoeveel studenten heeft Universiteit Utrecht in 2024/25?",
    ],
)
def test_een_genoemde_instelling_krijgt_geen_scopevraag(vraag):
    assert plaatsvraag(vraag) is None


@pytest.mark.parametrize("profiel", ["Hogeschool Utrecht", "HU", " hogeschool  utrecht "])
def test_het_profiel_bepaalt_de_instelling(profiel):
    assert plaatsvraag("Hoeveel studenten heeft Utrecht?", {"instelling": profiel}) is None


def test_een_profiel_van_elders_beslist_niet():
    kaart = plaatsvraag("Hoeveel studenten heeft Utrecht?", {"instelling": "Aeres Hogeschool"})
    assert kaart is not None


@pytest.mark.parametrize(
    "vraag",
    [
        "Wat is de hoofdstad van Utrecht?",  # geen telling
        "Hoeveel studenten hebben Utrecht en Groningen?",  # twee gebieden: een vergelijking
        "Hoeveel studenten heeft Nederland?",  # generiek woord, geen plaats
        "Hoeveel studenten hebben de hogescholen?",
        "Hoeveel studenten heeft Ede?",  # maar één instelling: geen keuze tussen instellingen
        "Hoeveel hbo-studenten zijn er landelijk?",
    ],
)
def test_zonder_open_scope_geen_kaart(vraag):
    assert plaatsvraag(vraag) is None


def test_de_eigen_sector_uit_het_profiel_staat_voorop():
    kaart = plaatsvraag("Hoeveel studenten telt Twente?", {"domein": "mbo"})
    assert kaart is not None
    assert [o["label"] for o in kaart.opties][:2] == ["ROC van Twente", "Universiteit Twente"]
    zonder = plaatsvraag("Hoeveel studenten telt Twente?")
    assert zonder is not None
    assert [o["label"] for o in zonder.opties][:2] == ["Universiteit Twente", "ROC van Twente"]


def test_per_sector_de_hoofdinstelling_met_de_kortste_naam():
    """'Universiteit Utrecht' vóór 'Theologische Universiteit Utrecht'; hbo naast wo, niet twee keer wo."""
    kaart = plaatsvraag("Hoeveel studenten heeft Utrecht?")
    assert kaart is not None
    assert [o["label"] for o in kaart.opties][:2] == ["Universiteit Utrecht", "Hogeschool Utrecht"]


@pytest.mark.parametrize("vraag", ["Hoeveel studenten heeft Aeres?", "Hoeveel studenten heeft het Grafisch?"])
def test_een_merk_of_soortwoord_vooraan_is_geen_plaats(vraag):
    assert plaatsvraag(vraag) is None


def test_de_sector_in_de_vraag_beperkt_de_instellingen():
    kaart = plaatsvraag("Hoeveel hbo-studenten telt Utrecht?")
    assert kaart is not None
    assert [o["label"] for o in kaart.opties] == ["Hogeschool Utrecht", _WOON_UTRECHT]
    # Geen mbo-instelling draagt de naam Groningen: dan is Groningen een gebied, geen keuze.
    assert plaatsvraag("Hoeveel mbo-studenten zijn er in Groningen?") is None


def test_zonder_register_geen_scopevraag(monkeypatch):
    def offline():
        raise OSError("geen DUO-download")

    monkeypatch.setattr(module, "get_all", offline)
    monkeypatch.setattr(instelling, "get_all", offline)
    assert plaatsvraag("Hoeveel studenten heeft Utrecht?") is None


# --- maat: een thema zonder maat -----------------------------------------------------------

_CATALOGUS = [
    {"_cbs_id": "11111NED", "bron": "Studenten; welzijn en studiedruk", "tags": ["welzijn"], "samenvatting": "Kort."},
    {
        "_cbs_id": "22222NED",
        "bron": "Welzijn van studenten; regio",
        "tags": ["welzijn", "studenten"],
        "samenvatting": "x" * 200,
    },
    {"_cbs_id": "33333NED", "bron": "Arbeidsmarkt; vacatures", "tags": ["arbeidsmarkt"]},
    # Raakt maar één term: de kaart uit code eist dat elke term raakt (de tool laat in een volzin één volstaan).
    {"_cbs_id": "44444NED", "bron": "Thuiswonende studenten", "tags": ["studenten"]},
]


def _met_catalogus(records):
    return patch("tools.catalog._cbs", return_value=records), patch("tools.catalog._rio_duo", return_value=[])


def test_een_thema_zonder_maat_vraagt_de_maat_uit_de_catalogus():
    a, b = _met_catalogus(_CATALOGUS)
    with a, b:
        kaart = maatvraag("Welzijn van studenten?")
    assert kaart is not None and kaart.slot == "maat"
    assert kaart.vraag == "Welke maat bedoel je bij 'Welzijn van studenten'?"
    per_label = {o["label"]: o for o in kaart.opties}
    # De volgorde is die van de catalogusranking; welke records meedoen, is de eis.
    assert set(per_label) == {"Studenten; welzijn en studiedruk", "Welzijn van studenten; regio"}
    assert per_label["Studenten; welzijn en studiedruk"]["beschrijving"] == "Kort."
    assert (
        "beschrijving" not in per_label["Welzijn van studenten; regio"]
    )  # een lange samenvatting hoort niet op een knop


def test_een_vo_contextoptie_op_de_maatkaart_draagt_het_etiket():
    """Elke plek die een HO_CONTEXT-bron noemt, zegt dat het vo-context voor ho is (#597, punt 4)."""
    records = [
        {"id": "85422NED", "titel": "Hbo en wo; vooropleiding eerstejaars", "samenvatting": None},
        {
            "id": "85566NED",
            "titel": "Vo; doorstroom en uitstroom",
            "samenvatting": None,
            "context": scopeprofiel.HO_CONTEXT_ETIKET,
        },
    ]
    with patch("tools.catalog.kandidaten", return_value=records):
        kaart = maatvraag("Aansluiting vo-hbo?")

    assert kaart is not None
    assert [o["label"] for o in kaart.opties] == [
        "Hbo en wo; vooropleiding eerstejaars",
        "Vo; doorstroom en uitstroom, vo-context voor ho",
    ]


def test_minder_dan_twee_records_is_geen_kaart():
    a, b = _met_catalogus(_CATALOGUS[:1])
    with a, b:
        assert maatvraag("welzijn van studenten") is None


@pytest.mark.parametrize("vraag", ["Hoeveel studenten heeft de HU?", "instroom hbo", "studentenwelzijn 2024"])
def test_een_vraag_met_maat_of_getal_krijgt_geen_maatkaart(vraag):
    a, b = _met_catalogus(_CATALOGUS)
    with a, b:
        assert maatvraag(vraag) is None


def test_scopevraag_kiest_eerst_de_scope_en_dan_de_maat():
    a, b = _met_catalogus(_CATALOGUS)
    with a, b:
        scope, maat = scopevraag("Hoeveel studenten heeft Utrecht?"), scopevraag("welzijn van studenten")
        assert scope is not None and scope.slot == "scope"
        assert maat is not None and maat.slot == "maat"
        assert scopevraag("Hoeveel studenten heeft de HU?") is None


# --- de beurt: de kaart komt vóór het model ---------------------------------------------------


def _beurt(vraag: str, session: dict) -> tuple[str, list[dict], list[dict]]:
    run_module = importlib.import_module("agent.run")
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    async def geen_model(*args, **kwargs):
        raise AssertionError("het model is aangeroepen")

    messages = [{"role": "user", "content": vraag}]
    with (
        patch.object(run_module, "tool_loop", geen_model),
        patch.object(run_module, "build_system", lambda *a, **k: []),
    ):
        tekst = asyncio.run(run_module.run(messages, session, emit))
    return tekst, events, messages


def test_de_beurt_stelt_de_kaart_zonder_het_model():
    session = {"chat_settings": {}, "clarify_rondes": 0}
    tekst, events, messages = _beurt("Hoeveel studenten heeft Utrecht?", session)
    assert tekst == ""
    assert [e["type"] for e in events] == ["clarification"]
    assert [o["label"] for o in events[0]["opties"]] == ["Universiteit Utrecht", "Hogeschool Utrecht", _WOON_UTRECHT]
    assert session["_clarified"] is True
    assert messages[-1] == {"role": "assistant", "content": events[0]["vraag"]}


def test_een_vaag_kort_thema_krijgt_de_maatkaart_zonder_het_model():
    """De maatkaart in de beurt, op een vaste catalogus: niet afhankelijk van de gepinde riodata."""
    session = {"chat_settings": {}, "clarify_rondes": 0}
    a, b = _met_catalogus(_CATALOGUS)
    with a, b:
        tekst, events, messages = _beurt("welzijn van studenten", session)
    assert tekst == ""
    assert [e["type"] for e in events] == ["clarification"]
    assert events[0]["vraag"] == "Welke maat bedoel je bij 'welzijn van studenten'?"
    assert {o["label"] for o in events[0]["opties"]} == {
        "Studenten; welzijn en studiedruk",
        "Welzijn van studenten; regio",
    }
    assert session["_clarified"] is True
    assert messages[-1] == {"role": "assistant", "content": events[0]["vraag"]}


def test_na_een_beantwoorde_kaart_vraagt_code_niets_meer():
    session = {"chat_settings": {}, "clarify_rondes": 1}
    with (
        patch.object(module, "scopevraag", side_effect=AssertionError("tweede kaart")),
        pytest.raises(AssertionError, match="het model is aangeroepen"),
    ):
        _beurt("Hoeveel studenten heeft Utrecht?", session)


def test_de_kaart_is_een_kaart_zoals_de_tool_hem_geeft():
    kaart = Kaart("scope", "Over welke 'Utrecht' gaat je vraag?", [{"label": "a"}, {"label": "b"}])
    assert 2 <= len(kaart.opties) <= 3 and all("label" in o for o in kaart.opties)
