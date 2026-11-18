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
from data.arbeidsmarkt import SECTOR_INDELING, load_sector_indeling
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


# Live-audit L-02 (#1021): wie zelf een dataset noemt, koos de data al; de kaart "Landelijk of per sector?" past niet.
_DATASETVRAGEN = [
    "Hoeveel studenten staan er in de dataset 'studentenwelzijn_2025'?",
    "Zoek in de catalogus naar het aantal studenten in studentenwelzijn_2025",
    "Hoeveel studenten staan er in dataset 85421NED?",
    "Hoeveel studenten staan er in 80040ned?",  # een CBS-ID in kleine letters
    "Hoeveel studenten staan er in p01hoinges?",  # een DUO-ID
    "Hoeveel studenten staan er in cbs:85423NED?",  # met bronvoorvoegsel
    "Hoeveel studenten staan er in wi-2021?",  # een ID uit de catalogus met een streepje
    "Hoeveel studenten staan er in abc12345?",  # een onbekend ID
    "Hoeveel studenten staan er in de Datasets?",
]


@pytest.mark.parametrize("vraag", _DATASETVRAGEN)
def test_een_vraag_met_een_dataset_krijgt_geen_afbakeningskaart(vraag):
    assert afbakeningsvraag(vraag) is None


@pytest.mark.parametrize("vraag", _DATASETVRAGEN)
def test_een_vraag_met_een_dataset_krijgt_geen_kaart_van_welk_slot_ook(vraag):
    assert scopevraag(vraag) is None


@pytest.mark.parametrize(
    "vraag",
    [
        "Hoeveel studenten zijn er in 2023?",  # een jaartal is geen ID
        "Hoeveel studenten zijn er in 2023/24?",
        "Hoeveel studenten zijn er?",
        "Hoeveel 2e-jaars studenten zijn er?",  # letters en een cijfer, maar geen ID-vorm en niet in de catalogus
    ],
)
def test_een_jaartal_of_telling_zonder_dataset_houdt_de_afbakeningskaart(vraag):
    assert _slot(scopevraag(vraag)) == "afbakening"


def test_een_gewoon_woord_dat_een_rio_id_is_houdt_de_kaart():
    assert _slot(scopevraag("Hoeveel studenten hebben erkenningen?")) == "afbakening"


def test_de_andere_slots_blijven_zonder_dataset():
    assert _slot(scopevraag("Hoeveel studenten heeft Utrecht?")) == "scope"
    assert _slot(scopevraag("Hoeveel studenten?")) == "afbakening"


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


def _beurt(messages: list[dict], session: dict, events: list[dict] | None = None) -> tuple[str, list[dict]]:
    """Een beurt zonder model; `events` krijgt de events ook als het model toch wordt aangeroepen."""
    run_module = importlib.import_module("agent.run")
    events = [] if events is None else events

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


# --- #1049: de kaart alleen als een van haar opties de vraag afbakent -----------------------------

_WAAROM_TECHNIEK = "Hoe komt het dat het aantal eerstejaars in de techniek daalt?"


def test_een_waarom_vraag_over_een_studierichting_krijgt_geen_afbakeningskaart():
    assert afbakeningsvraag(_WAAROM_TECHNIEK) is None
    kaart = scopevraag(_WAAROM_TECHNIEK)
    assert kaart is None or kaart.slot != "afbakening"


@pytest.mark.parametrize(
    "vraag",
    [
        "Hoeveel eerstejaars techniek zijn er?",
        "Hoeveel eerstejaars in technische opleidingen zijn er?",
        "Hoeveel studenten economie?",  # een ho-onderdeel
        "Hoeveel studenten gezondheidszorg zijn er?",
        "Hoeveel deelnemers zorg en welzijn?",  # een mbo-sector
        "Hoeveel studenten ICT zijn er?",  # korte vormen
        "Hoeveel studenten volgen een opleiding in de zorg?",
        "Hoeveel studenten groen zijn er?",
        "Hoeveel studenten onderwijs zijn er?",
    ],
)
def test_een_studierichting_telt_als_afbakening(vraag):
    assert afbakeningsvraag(vraag) is None


def test_elke_sector_uit_de_indeling_telt_als_afbakening():
    """De domeinen komen uit `_indelingen` in data/sector_cluster_mapping.json, geschreven zoals een gebruiker dat doet."""
    namen = sorted(SECTOR_INDELING)
    assert {"TECHNIEK", "ECONOMIE", "Zorg en welzijn", "Techniek en procesindustrie"} <= set(namen)
    for naam in namen:
        vraag = f"Hoeveel studenten {naam.replace('_', ' ').lower()}?"
        assert afbakeningsvraag(vraag) is None, vraag


@pytest.mark.parametrize(
    ("waarom", "telling"),
    [
        ("Waarom daalt het aantal studenten?", "Daalt het aantal studenten?"),
        ("Wat is de oorzaak van het dalende aantal eerstejaars?", "Wat is het dalende aantal eerstejaars?"),
        ("Hoe kan het dat het aantal studenten daalt?", "Hoeveel studenten zijn er?"),
        ("Wat is de verklaring voor het aantal studenten?", "Wat is het aantal studenten?"),
    ],
)
def test_een_waarom_vraag_krijgt_geen_afbakeningskaart_een_telling_wel(waarom, telling):
    assert afbakeningsvraag(waarom) is None
    assert _slot(afbakeningsvraag(telling)) == "afbakening"


def test_zonder_leesbare_indeling_blijven_de_korte_vormen(monkeypatch, tmp_path):
    kapot = tmp_path / "kapot.json"
    kapot.write_text("{geen json")
    for pad in (tmp_path / "weg.json", kapot):
        assert load_sector_indeling(pad) == {}
        monkeypatch.setattr(module, "_DOMEIN", module._domeinpatroon(load_sector_indeling(pad)))
        assert _slot(afbakeningsvraag("Hoeveel studenten?")) == "afbakening"
        assert afbakeningsvraag("Hoeveel studenten techniek?") is None
        assert afbakeningsvraag("Hoeveel studenten ICT?") is None


def test_de_beurt_stuurt_een_waarom_vraag_zonder_kaart_naar_het_model():
    session: dict = {"chat_settings": {}, "clarify_rondes": 0}
    events: list[dict] = []
    with pytest.raises(AssertionError, match="het model is aangeroepen"):
        _beurt([{"role": "user", "content": _WAAROM_TECHNIEK}], session, events)
    assert [e for e in events if e["type"] == "clarification"] == []  # het event noemt geen slot: geen enkele kaart
    assert "afbakening" not in session.get("clarify_slots", [])
