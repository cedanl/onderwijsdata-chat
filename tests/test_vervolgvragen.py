"""Vervolgvragen onder een data-antwoord komen uit de catalogus, getoetst in code (#364).

Het model beslist alleen dát er vervolgvragen komen (suggest_follow_ups als laatste stap); welke,
beslist code: voorbeeldvragen van de datasets die de beurt laadde, alleen als de chat ze kan beantwoorden.
"""

import asyncio
import importlib
import json
import logging
from collections.abc import Callable

import litellm
import pandas as pd
import pytest

from agent import vervolgvragen
from agent.loop import LoopResult, ToolCall
from agent.probleem import INGEHOUDEN, Probleem, hard
from agent.stream import StreamResult
from agent.vaste_antwoorden import WEIGER_ANTWOORD
from tools import catalog, store
from tools.store import KeyMeta

run_module = importlib.import_module("agent.run")
loop_module = importlib.import_module("agent.loop")
# De echte, gecachte toets; tests die hem vervangen, mogen zijn cache niet meenemen.
_TOETS = vervolgvragen._beantwoordbaar


@pytest.fixture(autouse=True)
def _zonder_instellingsregister(monkeypatch):
    # Het register bouwt uit DUO-downloads; een vraag die een instelling noemt, zoekt anders eerst in RIO (#334).
    monkeypatch.setattr("tools.instelling.genoemde_namen", lambda vraag: set())
    _TOETS.cache_clear()
    yield
    _TOETS.cache_clear()


# --- de getoetste lijst, op een eigen catalogus ---

_GOED = "Hoeveel gediplomeerden telt het hbo per studierichting?"
_CBS = [
    {
        "_cbs_id": "90001NED",
        "leverancier": "CBS",
        "bron": "Gediplomeerden hbo naar studierichting",
        "voorbeeldvragen": [
            _GOED,
            "Hoe verschilt het aantal gediplomeerden per geslacht?",
            "Hoeveel gediplomeerden zijn er in mijn regio?",
            "Hoeveel gediplomeerden heeft onze instelling?",
            "Hoeveel gediplomeerden telt elk DIPLOMATYPE?",
            "Hoeveel gediplomeerden per soort (HBO_BACHELOR)?",
            "Welke gediplomeerden hebben een lege eindeStudieDatum?",
            "Hoeveel gediplomeerden hadden een havo-diploma?",
        ],
    },
    {
        "_cbs_id": "90002NED",
        "leverancier": "CBS",
        "bron": "Promoties wo per vakgebied",
        "voorbeeldvragen": ["Welke vakgebieden leveren de meeste promoties?"],
    },
    # Een oudere tabel over hetzelfde: search_catalog zet het archief achter de actieve tabel.
    {
        "_cbs_id": "70001ned",
        "leverancier": "CBS",
        "_archief": True,
        "bron": "Promoties (archief)",
        "voorbeeldvragen": ["Hoeveel promoties waren er per vakgebied?"],
    },
]
_RIO_DUO = [
    {
        "_ckan_id": "duo-eerstejaars",
        "leverancier": "DUO",
        "bron": "Eerstejaars ho per instelling",
        "voorbeeldvragen": [
            "Welke instellingen trekken de meeste eerstejaars?",
            "Hoeveel BO-opleidingen hebben eerstejaars?",
            "Hoe groeit het aantal eerstejaars in het voortgezet onderwijs?",
        ],
    },
    {
        "_rio_resource": "aangeboden-opleidingen",
        "leverancier": "RIO",
        "bron": "Aangeboden opleidingen (RIO)",
        "voorbeeldvragen": [
            "Welke instellingen bieden een opleiding verpleegkunde aan?",
            "Hoeveel opleidingen verpleegkunde worden er aangeboden?",
        ],
    },
    # Wel in het profiel, maar niet op te halen: geen datatool, of alleen een PDF.
    {"_ckan_id": "sbb-kwalificaties", "leverancier": "SBB", "voorbeeldvragen": ["Welke kwalificaties zijn erkend?"]},
    {
        "_ckan_id": "duo-changelog",
        "leverancier": "DUO",
        "_resources": [{"naam": "changelog", "format": "PDF"}],
        "voorbeeldvragen": ["Wat veranderde er in de changelog?"],
    },
]
# Buiten het profiel: staat in de volledige inventaris, niet in de lijst waar de chat mee werkt.
_BUITEN_PROFIEL = {
    "_ckan_id": "po-leerlingen",
    "leverancier": "DUO",
    "bron": "Leerlingen basisscholen",
    "voorbeeldvragen": ["Welke instellingen hebben de meeste leerlingen?"],
}


@pytest.fixture
def eigen_catalogus(monkeypatch):
    monkeypatch.setattr(catalog, "_cbs", lambda: _CBS)
    monkeypatch.setattr(catalog, "_rio_duo", lambda: _RIO_DUO)
    monkeypatch.setattr(catalog, "_rio_duo_alles", lambda: [*_RIO_DUO, _BUITEN_PROFIEL])


def test_een_gewone_vraag_over_de_eigen_dataset_blijft(eigen_catalogus):
    assert vervolgvragen.beantwoordbare_vragen()["90001NED"] == (
        _GOED,
        "Hoe verschilt het aantal gediplomeerden per geslacht?",
    )


@pytest.mark.parametrize(
    "vraag",
    ["Hoeveel gediplomeerden zijn er in mijn regio?", "Hoeveel gediplomeerden heeft onze instelling?"],
)
def test_een_vraag_in_de_eerste_persoon_valt_af(eigen_catalogus, vraag):
    assert vraag not in vervolgvragen.beantwoordbare_vragen()["90001NED"]


@pytest.mark.parametrize(
    "vraag",
    [
        "Hoeveel gediplomeerden telt elk DIPLOMATYPE?",
        "Hoeveel gediplomeerden per soort (HBO_BACHELOR)?",
        "Welke gediplomeerden hebben een lege eindeStudieDatum?",
    ],
)
def test_een_vraag_met_een_ruwe_veldnaam_valt_af(eigen_catalogus, vraag):
    assert vraag not in vervolgvragen.beantwoordbare_vragen()["90001NED"]


def test_een_vraag_over_po_so_of_vo_valt_af(eigen_catalogus):
    vragen = vervolgvragen.beantwoordbare_vragen()
    assert "Hoeveel gediplomeerden hadden een havo-diploma?" not in vragen["90001NED"]
    assert vragen["duo-eerstejaars"] == ("Welke instellingen trekken de meeste eerstejaars?",)


def test_een_aantal_uit_een_rio_register_valt_af(eigen_catalogus):
    # get_rio_data levert één pagina en geen totaal (#170).
    assert vervolgvragen.beantwoordbare_vragen()["aangeboden-opleidingen"] == (
        "Welke instellingen bieden een opleiding verpleegkunde aan?",
    )


def test_een_vraag_die_haar_dataset_niet_terugvindt_valt_af(eigen_catalogus):
    vraag = "Hoeveel promoties waren er per vakgebied?"
    treffers = [t.get("_cbs_id") for t in json.loads(catalog.search_catalog(vraag))]
    assert "90002NED" in treffers and "70001ned" not in treffers

    assert "70001ned" not in vervolgvragen.beantwoordbare_vragen()


def test_alleen_datasets_die_de_chat_kan_ophalen(eigen_catalogus):
    datasets = vervolgvragen.beantwoordbare_vragen()
    assert {"sbb-kwalificaties", "duo-changelog", "po-leerlingen"}.isdisjoint(datasets)
    assert not catalog.opvraagbaar("sbb-kwalificaties")
    assert not catalog.opvraagbaar("duo-changelog")
    assert not catalog.opvraagbaar("po-leerlingen")
    assert catalog.opvraagbaar("duo-eerstejaars")


def test_toetsen_laat_geen_zoekregels_in_het_log(eigen_catalogus, caplog):
    with caplog.at_level(logging.DEBUG, logger="tools.catalog"):
        vervolgvragen.beantwoordbare_vragen()
        assert not [r for r in caplog.records if r.name == "tools.catalog"]

        catalog.search_catalog("promoties vakgebied")  # een zoekactie van het model logt wel
    assert any(r.message.startswith("search_catalog ") for r in caplog.records)


# --- de keuze voor één beurt ---


def _laad(key: str, dataset: str, bron: str = "duo") -> str:
    store.put(key, pd.DataFrame({"AANTAL": [1]}), KeyMeta(bron=bron, dataset=dataset))
    return json.dumps({"data_key": key})


@pytest.fixture
def vaste_lijst(monkeypatch):
    lijst = {
        "duo-a": ("A1?", "A2?", "A3?"),
        "duo-b": ("B1?", "B2?"),
    }
    monkeypatch.setattr(vervolgvragen, "_beantwoordbaar", lambda dataset_id: lijst.get(dataset_id, ()))
    return lijst


def test_de_datasets_van_een_beurt_komen_uit_de_laadkey_van_elke_stap():
    laad = _laad("duo:duo-a:0", "duo-a")
    store.put("q1", pd.DataFrame({"AANTAL": [1]}), KeyMeta(bron="duo", dataset="duo-a", afgeleid_van="duo:duo-a:0"))
    steps = [
        ("search_catalog", '[{"_ckan_id": "duo-b"}]'),
        ("get_duo_data", laad),
        ("query_data", json.dumps({"data_key": "q1"})),
        ("get_cbs_data", _laad("cbs:90001NED", "90001NED", "cbs")),
    ]

    assert vervolgvragen.datasets_van(steps) == ["duo-a", "90001NED"]


def test_kies_om_en_om_per_dataset_en_hoogstens_drie(vaste_lijst):
    steps = [("get_duo_data", _laad("duo:duo-a:0", "duo-a")), ("get_duo_data", _laad("duo:duo-b:0", "duo-b"))]

    assert vervolgvragen.kies(steps, "Iets anders?", []) == ["A1?", "B1?", "A2?"]


def test_kies_niet_de_gestelde_vraag_en_niet_wat_al_aangeboden_is(vaste_lijst):
    steps = [("get_duo_data", _laad("duo:duo-a:0", "duo-a"))]

    assert vervolgvragen.kies(steps, "  a1? ", ["A2?"]) == ["A3?"]


def test_kies_zonder_geladen_dataset_niets(vaste_lijst):
    assert vervolgvragen.kies([("search_catalog", '[{"_ckan_id": "duo-a"}]')], "Vraag?", []) == []


# --- de beurt: run() met een nagebootst model ---

_VRAAG = "Hoeveel eerstejaars had het hbo in 2024?"
_VETTED = {
    "p02ho1ejrs": (
        "Welke instellingen trekken de meeste eerstejaars?",
        "hoeveel eerstejaars had het  HBO in 2024?",  # de gestelde vraag, anders gespeld
        "Hoe verdelen eerstejaars zich over de provincies?",
        "Wat is de M/V-verhouding bij eerstejaars?",
    )
}
_SUGGEST = {"id": "s", "name": "suggest_follow_ups", "arguments": "{}"}
_LAAD = {"id": "l", "name": "get_duo_data", "arguments": '{"dataset_id": "p02ho1ejrs"}'}


_GELADEN = json.dumps({"data_key": "duo:p02ho1ejrs:0"})


def _beurt(monkeypatch, steps, *, session=None, problemen=(), toolresultaat=_GELADEN):
    """Eén beurt met een nagebootst model; een tool geeft standaard een geladen DUO-key terug."""
    store.put("duo:p02ho1ejrs:0", pd.DataFrame({"AANTAL": [1]}), KeyMeta(bron="duo", dataset="p02ho1ejrs"))
    steps = list(steps)

    async def fake_completion(*a, **k):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return steps.pop(0)

    async def fake_execute(call, emit):
        return toolresultaat, None

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop_module, "_execute_tool", fake_execute)
    monkeypatch.setattr(run_module, "scopevraag", lambda vraag, settings: None)
    monkeypatch.setattr(run_module, "_antwoordcontrole", lambda *a: lambda text, results: list(problemen))
    monkeypatch.setattr(vervolgvragen, "_beantwoordbaar", lambda dataset_id: _VETTED.get(dataset_id, ()))
    session = {} if session is None else session
    events: list[dict] = []

    async def emit(event):
        events.append(event)

    text = asyncio.run(
        run_module.run([{"role": "user", "content": _VRAAG}], session, emit, asyncio.Event(), model="openai/gpt-4o")
    )
    return text, events, session


def _slot(events) -> dict:
    return [e for e in events if e["type"] == "message_end"][-1]


def _antwoord_met_afsluiting(tekst="Het hbo had veel eerstejaars."):
    return [StreamResult(text="", tool_calls=[_LAAD]), StreamResult(text=tekst, tool_calls=[_SUGGEST])]


def test_een_data_antwoord_met_afsluiting_krijgt_vervolgvragen(monkeypatch):
    text, events, session = _beurt(monkeypatch, _antwoord_met_afsluiting())

    vragen = _slot(events)["vervolgvragen"]
    assert text.startswith("Het hbo had veel eerstejaars.")
    assert 1 <= len(vragen) <= 3
    assert set(vragen) <= set(_VETTED["p02ho1ejrs"])
    assert all(" ".join(v.split()).casefold() != _VRAAG.casefold() for v in vragen)
    assert session["vervolgvragen_getoond"] == vragen
    # De afsluitende aanroep is geen stap van de beurt.
    assert [c["name"] for c in session["_last_turn_tool_calls"]] == ["get_duo_data"]


def test_wat_dit_gesprek_al_aanbood_komt_niet_terug(monkeypatch):
    session = {"vervolgvragen_getoond": ["Welke instellingen trekken de meeste eerstejaars?"]}

    _, events, _ = _beurt(monkeypatch, _antwoord_met_afsluiting(), session=session)

    assert _slot(events)["vervolgvragen"] == [
        "Hoe verdelen eerstejaars zich over de provincies?",
        "Wat is de M/V-verhouding bij eerstejaars?",
    ]
    _, events, _ = _beurt(monkeypatch, _antwoord_met_afsluiting(), session=session)
    assert "vervolgvragen" not in _slot(events)


def test_zonder_afsluiting_geen_vervolgvragen(monkeypatch):
    steps = [
        StreamResult(text="", tool_calls=[_LAAD]),
        StreamResult(text="Het hbo had veel eerstejaars.", tool_calls=[]),
    ]

    _, events, _ = _beurt(monkeypatch, steps)

    assert "vervolgvragen" not in _slot(events)


def test_zonder_geladen_dataset_geen_vervolgvragen(monkeypatch):
    zoek = {"id": "z", "name": "search_catalog", "arguments": '{"query": "eerstejaars hbo"}'}
    steps = [StreamResult(text="", tool_calls=[zoek]), StreamResult(text="Daar vond ik niets.", tool_calls=[_SUGGEST])]

    _, events, _ = _beurt(monkeypatch, steps, toolresultaat="no_match: Geen resultaten gevonden.")

    assert "vervolgvragen" not in _slot(events)


def test_een_getal_zonder_datatools_blijft_de_weigering(monkeypatch):
    # De afsluitende aanroep telt niet als datastap: zonder data geen antwoord met een getal (#403).
    steps = [StreamResult(text="Het hbo had 12.345 eerstejaars.", tool_calls=[_SUGGEST])]

    text, events, session = _beurt(monkeypatch, steps)

    assert text == WEIGER_ANTWOORD
    assert "vervolgvragen" not in _slot(events)
    assert session["_last_turn_tool_calls"] == []


def test_een_weigering_krijgt_geen_vervolgvragen(monkeypatch):
    steps = [StreamResult(text="Ik kan geen antwoord geven.", tool_calls=[_SUGGEST])]

    text, events, _ = _beurt(monkeypatch, steps)

    assert text == WEIGER_ANTWOORD
    assert "vervolgvragen" not in _slot(events)


def test_een_ingehouden_antwoord_krijgt_geen_vervolgvragen(monkeypatch):
    steps = [*_antwoord_met_afsluiting("Fout."), StreamResult(text="Nog steeds fout.", tool_calls=[_SUGGEST])]

    text, events, _ = _beurt(monkeypatch, steps, problemen=hard([Probleem("12.345 staat niet in de data.")]))

    assert text == INGEHOUDEN
    assert "vervolgvragen" not in _slot(events)


def test_na_een_verduidelijkingsvraag_geen_vervolgvragen(monkeypatch):
    clarify = {"id": "c", "name": "clarify_scope", "arguments": '{"vraag": "Welk jaar?", "opties": ["2023", "2024"]}'}

    _, events, _ = _beurt(monkeypatch, [StreamResult(text="", tool_calls=[clarify])])

    assert any(e["type"] == "clarification" for e in events)
    assert not any("vervolgvragen" in e for e in events)


def _gesprek(monkeypatch, rondes: list) -> tuple[Callable[[str], str], list[dict], dict]:
    """Beurten met de echte antwoordcontrole; een uitzondering in `rondes` is een modelaanroep die faalt."""
    store.put("duo:p02ho1ejrs:0", pd.DataFrame({"AANTAL": [1]}), KeyMeta(bron="duo", dataset="p02ho1ejrs"))

    async def fake_completion(*a, **k):
        if isinstance(rondes[0], Exception):
            raise rondes.pop(0)
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        return rondes.pop(0)

    async def fake_execute(call, emit):
        return _GELADEN, None

    async def emit(event):
        pass

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop_module, "_execute_tool", fake_execute)
    monkeypatch.setattr(run_module, "scopevraag", lambda vraag, settings: None)
    monkeypatch.setattr(vervolgvragen, "_beantwoordbaar", lambda dataset_id: _VETTED.get(dataset_id, ()))
    messages: list[dict] = []
    session: dict = {}

    def beurt(vraag: str) -> str:
        messages.append({"role": "user", "content": vraag})
        return asyncio.run(run_module.run(messages, session, emit, asyncio.Event(), model="openai/gpt-4o"))

    return beurt, messages, session


def test_een_ingetrokken_afgesloten_antwoord_blijft_niet_achter_na_een_modelfout(monkeypatch):
    # De controle trekt een afgesloten antwoord met een verzonnen getal in; dan faalt de correctieronde.
    # De stappen die af zijn, blijven voor een nieuwe poging (#431), het ingetrokken antwoord niet: anders
    # telt het daar als iets wat de assistent al zei en komt het getal ongetoetst door.
    verzonnen = "Het hbo had 98765 eerstejaars."
    beurt, messages, _ = _gesprek(
        monkeypatch,
        [
            StreamResult(text="", tool_calls=[_LAAD]),
            StreamResult(text=verzonnen, tool_calls=[_SUGGEST]),
            litellm.RateLimitError("te veel", llm_provider="openai", model="m"),
            # De nieuwe poging: het model herhaalt het getal zonder data, ook na de correctie.
            StreamResult(text="Het waren er 98765.", tool_calls=[]),
            StreamResult(text="Het waren er 98765.", tool_calls=[]),
        ],
    )

    with pytest.raises(litellm.RateLimitError):
        beurt("Hoeveel eerstejaars had het hbo?")
    assert not [m for m in messages if m["role"] == "assistant" and "98765" in str(m.get("content"))]
    assert [m["role"] for m in messages] == ["user", "assistant", "tool"]

    assert "98765" not in beurt("Hoeveel waren het er precies?")


def _afgesloten(**velden) -> LoopResult:
    return LoopResult(afgesloten=ToolCall("s", "suggest_follow_ups", "{}", {}), **velden)


@pytest.mark.parametrize(
    ("result", "tekst"),
    [
        (_afgesloten(), WEIGER_ANTWOORD),
        (_afgesloten(), INGEHOUDEN),
        (_afgesloten(), run_module.LEEG_ANTWOORD),
        (_afgesloten(wrapped_up=True), "Deelantwoord."),
        (LoopResult(), "Een antwoord zonder afsluiting."),
    ],
    ids=["weigering", "ingehouden", "leeg", "deelantwoord", "zonder-afsluiting"],
)
def test_geen_vervolgvragen_buiten_een_gewoon_afgesloten_antwoord(monkeypatch, result, tekst):
    def niet_kiezen(*a):
        raise AssertionError("kies() hoort hier niet te lopen")

    monkeypatch.setattr(vervolgvragen, "kies", niet_kiezen)

    assert asyncio.run(run_module._vervolgvragen(result, tekst, _VRAAG, {})) == []


def test_een_fout_bij_het_kiezen_kost_het_antwoord_niet(monkeypatch):
    def kapot(*a):
        raise RuntimeError("catalogus weg")

    monkeypatch.setattr(vervolgvragen, "kies", kapot)

    assert asyncio.run(run_module._vervolgvragen(_afgesloten(), "Een antwoord.", _VRAAG, {})) == []


# --- de echte catalogus ---


def test_elke_vervolgvraag_uit_de_catalogus_is_beantwoordbaar():
    """Elke getoetste (dataset, vraag): binnen het profiel, op te halen en vindbaar met search_catalog."""
    lijst = vervolgvragen.beantwoordbare_vragen()

    assert lijst, "geen enkele beantwoordbare vervolgvraag: de toets is dan leeg"
    for dataset_id, vragen in lijst.items():
        assert catalog.scope_blokkade(dataset_id) is None, dataset_id
        assert catalog.opvraagbaar(dataset_id), dataset_id
        for vraag in vragen:
            treffers = json.loads(catalog.search_catalog(vraag))
            assert dataset_id in [t.get("_cbs_id") or t.get("_ckan_id") or t.get("_rio_resource") for t in treffers]
