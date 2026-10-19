"""Vervolgvragen onder een data-antwoord komen uit de catalogus, getoetst in code (#364).

Code biedt ze aan onder elk gewoon antwoord met data, zonder keuze van het model (#539): voorbeeldvragen
van de datasets die de beurt laadde, alleen als de chat ze kan beantwoorden.
"""

import asyncio
import importlib
import json
import logging
import re

import pandas as pd
import pytest

from agent import vervolgvragen
from agent.budget import DEELANTWOORD
from agent.loop import LoopResult
from agent.probleem import INGEHOUDEN, Probleem, hard
from agent.scopevraag import Kaart
from agent.stream import StreamResult
from agent.vaste_antwoorden import WEIGER_ANTWOORD
from tools import catalog, scopeprofiel, store
from tools.ho_markers import noemt_ho
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
            "Hoeveel hbo-gediplomeerden hadden een havo-diploma?",
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


@pytest.mark.parametrize(
    "vraag",
    [
        "Sinds wanneer is de opleiding met code C0001 erkend?",  # een code
        "Welke gediplomeerden hebben geen studie_richting?",  # een veldnaam in kleine letters
        "Hoe verhouden de opleidingsfasen zich tot de erkenningen via de sub-resource?",  # een API-term
    ],
)
def test_een_vraag_met_een_code_of_technische_term_valt_af(vraag):
    assert not vervolgvragen._leesbaar(vraag)


@pytest.mark.parametrize(
    "vraag",
    ["Hoe verhoudt dit zich tot andere jaren of regio's?", "Welke uitschieters zijn er te zien in de data?"],
)
def test_een_sjabloonvraag_die_naar_het_antwoord_wijst_valt_af(vraag):
    # Als knop, los van het antwoord erboven, zegt "dit" of "de data" niets.
    assert not vervolgvragen._leesbaar(vraag)


def test_een_vraag_die_een_dataset_bij_zijn_id_noemt_valt_af(eigen_catalogus):
    assert not vervolgvragen._leesbaar("Welke instellingen staan in aangeboden-opleidingen?")
    assert not vervolgvragen._leesbaar("Welke cijfers staan in 90001NED?")
    assert vervolgvragen._leesbaar("Welke instellingen bieden een opleiding verpleegkunde aan?")


def test_een_dataset_id_dat_een_gewoon_woord_is_telt_niet():
    # In de echte catalogus is "opleidingen" een RIO-register: dat woord mag in een vraag staan.
    vraag = "Welke opleidingen zijn ooit opgeheven?"
    assert "opleidingen" in catalog.genoemde_datasets(vraag)

    assert vervolgvragen._leesbaar(vraag)


def test_een_vraag_over_po_so_of_vo_valt_af(eigen_catalogus):
    vragen = vervolgvragen.beantwoordbare_vragen()
    assert "Hoeveel hbo-gediplomeerden hadden een havo-diploma?" not in vragen["90001NED"]
    assert vragen["duo-eerstejaars"] == ("Welke instellingen trekken de meeste eerstejaars?",)


# Een vo-contextrecord (epic #554) laat een vraag over vo toe als ze ook hoger onderwijs noemt (#558).
_HO_VRAAG = "Verschilt de doorstroom van HAVO naar hbo naar herkomst?"  # hbo is de ho-marker; havo niet (#597)
_ZONDER_HO = "Hoeveel VO-leerlingen stromen door naar een hoger niveau?"


def _contextrecord(dataset_id: str) -> dict:
    """Een synthetisch catalogusrecord met dit ID: CBS als het ID er zo uitziet, anders DUO."""
    cbs = re.fullmatch(r"\d+NED", dataset_id, re.IGNORECASE)
    return {
        "_cbs_id" if cbs else "_ckan_id": dataset_id,
        "leverancier": "CBS" if cbs else "DUO",
        "bron": "Slagingspercentage vo naar herkomst en doorstroom",
        "voorbeeldvragen": [_HO_VRAAG, _ZONDER_HO],
    }


@pytest.fixture(params=sorted(scopeprofiel.HO_CONTEXT))
def contextcatalogus(request, monkeypatch) -> str:
    """De eigen catalogus plus één vo-contextrecord; geeft zijn ID."""
    record = _contextrecord(request.param)
    cbs = "_cbs_id" in record
    monkeypatch.setattr(catalog, "_cbs", lambda: [*_CBS, record] if cbs else _CBS)
    monkeypatch.setattr(catalog, "_rio_duo", lambda: _RIO_DUO if cbs else [*_RIO_DUO, record])
    monkeypatch.setattr(catalog, "_rio_duo_alles", lambda: [*catalog._rio_duo(), _BUITEN_PROFIEL])
    return request.param


def test_een_contextrecord_houdt_een_vo_vraag_die_ho_noemt(contextcatalogus):
    assert scopeprofiel.is_ho_context(contextcatalogus)
    assert scopeprofiel.PO_SO_VO.search(_HO_VRAAG) and noemt_ho(_HO_VRAAG)

    assert vervolgvragen.beantwoordbare_vragen()[contextcatalogus] == (_HO_VRAAG,)


def test_een_contextrecord_laat_een_vo_vraag_zonder_ho_marker_vallen(contextcatalogus):
    assert scopeprofiel.PO_SO_VO.search(_ZONDER_HO) and not noemt_ho(_ZONDER_HO)

    assert not vervolgvragen._leesbaar(_ZONDER_HO, contextcatalogus)
    assert _ZONDER_HO not in vervolgvragen.beantwoordbare_vragen().get(contextcatalogus, ())


def test_een_contextrecord_maakt_een_andere_vraag_niet_leesbaar(contextcatalogus):
    # Eerste persoon en veldnamen vallen ook bij een contextrecord af.
    assert not vervolgvragen._leesbaar("Wat is het slagingspercentage voor VWO in mijn regio?", contextcatalogus)
    assert not vervolgvragen._leesbaar("Hoeveel havo-leerlingen per ONDERWIJSNIVEAU?", contextcatalogus)


def test_buiten_de_contextrecords_blijft_een_vo_vraag_met_ho_marker_vallen(contextcatalogus):
    vraag = "Hoeveel hbo-gediplomeerden hadden een havo-diploma?"
    assert noemt_ho(vraag) and not scopeprofiel.is_ho_context("90001NED")

    assert not vervolgvragen._leesbaar(vraag)
    assert not vervolgvragen._leesbaar(vraag, "90001NED")
    assert vraag not in vervolgvragen.beantwoordbare_vragen()["90001NED"]


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


# --- uit de vraagcontext (#615): zelfde maat, ander schooljaar, ontwikkeling; dan pas de dataset ---

_JAREN = (2019, 2020, 2021, 2022, 2023, 2024)
_META = KeyMeta(bron="cbs", dataset="85354NED", schooljaren=_JAREN, kolomtitels={"MboStudenten_1": "Mbo studenten"})


def _cite(
    selectie="Geslacht: Vrouwen · Niveau: Totaal · Perioden: 2021/'22", maat="MboStudenten_1", eenheid="Aantal", **extra
):
    return {
        "getal": "248.930",
        "vastgesteld": True,
        "maat": maat,
        "eenheid": eenheid,
        "selectie": selectie,
        "data_key": "cbs:85354NED:x",
        **extra,
    }


def test_contextvragen_zelfde_maat_en_selectie_nieuwste_jaar_en_ontwikkeling():
    assert vervolgvragen.kandidaten_uit_context([_cite()], lambda key: _META) == [
        "Hoeveel mbo studenten (vrouwen) waren er in 2024/25?",
        "Hoe ontwikkelde het aantal mbo studenten (vrouwen) zich van 2019/20 tot en met 2024/25?",
    ]


def test_contextvragen_zonder_selectie_en_bij_een_percentage():
    cite = _cite(selectie="Perioden: 2024/'25", maat="AandeelVrouwen_2", eenheid="%")
    meta = KeyMeta(bron="cbs", dataset="x", schooljaren=_JAREN, kolomtitels={"AandeelVrouwen_2": "Aandeel vrouwen"})
    assert vervolgvragen.kandidaten_uit_context([cite], lambda key: meta) == [
        "Hoe hoog was aandeel vrouwen in 2023/24?",
        "Hoe ontwikkelde aandeel vrouwen zich van 2019/20 tot en met 2024/25?",
    ]


def test_contextvragen_slaan_een_jaar_over_dat_het_antwoord_al_noemt_en_een_reeks_die_er_al_staat():
    alle = " · ".join(f"Perioden: {j}/'{(j + 1) % 100:02d}" for j in _JAREN)
    assert vervolgvragen.kandidaten_uit_context([_cite(selectie=alle)], lambda key: _META) == []
    twee = KeyMeta(bron="cbs", dataset="x", schooljaren=(2023, 2024), kolomtitels={"MboStudenten_1": "Mbo studenten"})
    assert vervolgvragen.kandidaten_uit_context([_cite(selectie="Perioden: 2023/'24")], lambda key: twee) == [
        "Hoeveel mbo studenten waren er in 2024/25?",
    ]


@pytest.mark.parametrize(
    ("cites", "meta"),
    [
        pytest.param(
            [_cite(maat="AANTAL")],
            KeyMeta(bron="duo", dataset="p", schooljaren=_JAREN),
            id="maat zonder leesbare titel",
        ),
        pytest.param(
            [_cite()],
            KeyMeta(bron="cbs", dataset="x", schooljaren=(2024,), kolomtitels={"MboStudenten_1": "Mbo studenten"}),
            id="één schooljaar",
        ),
        pytest.param([_cite()], None, id="bron niet meer in de store"),
        pytest.param([_cite(vastgesteld=False)], _META, id="getal zonder herkomst"),
        pytest.param([], _META, id="geen citaties"),
    ],
)
def test_zonder_bruikbare_context_geen_contextvragen(cites, meta):
    assert vervolgvragen.kandidaten_uit_context(cites, lambda key: meta) == []


def test_kies_zet_de_contextvragen_voor_de_datasetvraag(vaste_lijst, monkeypatch):
    monkeypatch.setattr(
        vervolgvragen, "uit_vraagcontext", lambda steps, tekst: ["Context 1?", "Context 2?"] if tekst else []
    )
    steps = [("get_duo_data", _laad("duo:duo-a:0", "duo-a"))]
    assert vervolgvragen.kies(steps, "Vraag?", [], tekst="Antwoord.") == ["Context 1?", "Context 2?", "A1?"]
    # Zonder tekst (of zonder context): alles uit de dataset, zoals voorheen.
    assert vervolgvragen.kies(steps, "Vraag?", []) == ["A1?", "A2?", "A3?"]
    # Wat al aangeboden is, ook niet als contextvraag.
    assert vervolgvragen.kies(steps, "Vraag?", ["context 1?"], tekst="Antwoord.") == ["Context 2?", "A1?", "A2?"]


def test_contextvragen_uit_een_echt_antwoord_via_de_citaties():
    store.put("cbs:85354NED:c7", pd.DataFrame({"Perioden": ["2021SJ00"], "MboStudenten_1": [248930]}), _META)
    stap = json.dumps(
        {
            "data_key": "cbs:85354NED:c7",
            "totaal_rijen": 1,
            "preview": [{"Perioden": "2021SJ00", "MboStudenten_1": 248930}],
        }
    )
    vragen = vervolgvragen.uit_vraagcontext(
        [("get_cbs_data", stap)], "Er waren 248.930 vrouwelijke mbo-studenten in 2021/22."
    )
    assert vragen and all("mbo studenten" in v for v in vragen)


# --- de beurt: run() met een nagebootst model ---

_VRAAG = "Hoeveel eerstejaars had het hbo in 2024?"
_VETTED = {
    "p02ho1ejrs": (
        "Welke instellingen trekken de meeste eerstejaars?",
        "hoeveel eerstejaars had het  HBO in 2024?",  # de gestelde vraag, anders gespeld
        "Hoe verdelen eerstejaars zich over de provincies?",
        "Wat is de M/V-verhouding bij eerstejaars?",
    ),
    "85353NED": ("Hoeveel studenten volgen een wo-master?", "Hoe verdeelt het hbo zich over de studierichtingen?"),
    "p01hoinges": ("Welke hogescholen hebben de meeste studenten?",),
}
_LAAD = {"id": "l", "name": "get_duo_data", "arguments": '{"dataset_id": "p02ho1ejrs"}'}
_QUERY = {"id": "q", "name": "query_data", "arguments": '{"data_key": "duo:p02ho1ejrs:0", "group_by": ["JAAR"]}'}
_PLOT = {"id": "p", "name": "create_plot", "arguments": '{"data_key": "query:trend", "x": "JAAR", "y": "AANTAL"}'}
_LAAD_CBS = {"id": "c", "name": "get_cbs_data", "arguments": '{"dataset_id": "85353NED"}'}
_MAAT = {"id": "m", "name": "get_maat", "arguments": '{"maat": "ingeschreven_personen_ho"}'}
_ZOEK = {"id": "z", "name": "search_catalog", "arguments": '{"query": "eerstejaars hbo"}'}
_CLARIFY = {"id": "v", "name": "clarify_scope", "arguments": '{"vraag": "Welk jaar?", "opties": ["2023", "2024"]}'}

_GELADEN = json.dumps({"data_key": "duo:p02ho1ejrs:0"})
# Wat elke nagebootste tool teruggeeft; create_plot geeft tekst zonder data_key, zoals de echte.
_RESULTATEN = {
    "get_duo_data": _GELADEN,
    "query_data": json.dumps({"data_key": "query:trend", "rijen": 5}),
    "create_plot": "Lijngrafiek 'Eerstejaars hbo' aangemaakt (5 datapunten).",
    "get_cbs_data": json.dumps({"data_key": "cbs:85353NED"}),
    "get_maat": json.dumps({"data_key": "maat:p01hoinges", "rijen": 3, "recept": {"maat": "ingeschreven_personen_ho"}}),
}


def _zet(key: str, dataset: str, bron: str = "duo", afgeleid_van: str | None = None) -> None:
    store.put(key, pd.DataFrame({"AANTAL": [1]}), KeyMeta(bron=bron, dataset=dataset, afgeleid_van=afgeleid_van))


def _beurt(monkeypatch, steps, *, session=None, problemen=(), toolresultaat=None, kaart=None, max_iteraties=None):
    """Eén beurt met een nagebootst model.

    Een tool geeft `toolresultaat` terug als dat er is, anders zijn resultaat uit _RESULTATEN. Een stap
    mag een functie zijn: die krijgt het stopsignaal en geeft de modelronde."""
    _zet("duo:p02ho1ejrs:0", "p02ho1ejrs")
    _zet("query:trend", "p02ho1ejrs", afgeleid_van="duo:p02ho1ejrs:0")
    _zet("cbs:85353NED", "85353NED", "cbs")
    _zet("duo:p01hoinges:0", "p01hoinges")
    _zet("maat:p01hoinges", "p01hoinges", afgeleid_van="duo:p01hoinges:0")
    steps = list(steps)

    async def fake_completion(*a, **k):
        return object()

    async def fake_accumulate(stream, stop_event=None, emit=None):
        stap = steps.pop(0)
        return stap(stop_event) if callable(stap) else stap

    async def fake_execute(call, emit, recept_van=None):
        return (_RESULTATEN[call.name] if toolresultaat is None else toolresultaat), None

    monkeypatch.setattr(loop_module, "acompletion_with_backoff", fake_completion)
    monkeypatch.setattr(loop_module, "accumulate_stream", fake_accumulate)
    monkeypatch.setattr(loop_module, "_execute_tool", fake_execute)
    monkeypatch.setattr(run_module, "scopevraag", lambda vraag, settings: kaart)
    monkeypatch.setattr(run_module, "_antwoordcontrole", lambda *a: lambda text, results: list(problemen))
    monkeypatch.setattr(vervolgvragen, "_beantwoordbaar", lambda dataset_id: _VETTED.get(dataset_id, ()))
    if max_iteraties is not None:
        monkeypatch.setattr(run_module, "MAX_TOOL_ITERATIONS", max_iteraties)
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


def _antwoord(*rondes: dict, tekst: str = "Het hbo had veel eerstejaars.") -> list[StreamResult]:
    """Het model roept per ronde één tool aan en antwoordt daarna met gewone tekst, zonder tool."""
    return [*(StreamResult(text="", tool_calls=[r]) for r in rondes), StreamResult(text=tekst, tool_calls=[])]


def _vorm(vraag: str) -> str:
    return " ".join(vraag.split()).casefold()


def _aanbod_uit_de_lijst(vragen: list[str], dataset_id: str) -> None:
    """Eén tot drie getoetste vragen van de dataset, en niet de vraag die de gebruiker net stelde."""
    assert 1 <= len(vragen) <= 3
    assert set(vragen) <= set(_VETTED[dataset_id])
    assert _vorm(_VRAAG) not in map(_vorm, vragen)


@pytest.fixture
def kies_aanroepen(monkeypatch) -> list[tuple]:
    """Elke aanroep van kies. Een stub die een fout gooit bewijst niets: _vervolgvragen slikt fouten in."""
    aanroepen: list[tuple] = []
    echte_kies = vervolgvragen.kies

    def kies(*args, **kwargs):
        aanroepen.append(args)
        return echte_kies(*args, **kwargs)

    monkeypatch.setattr(vervolgvragen, "kies", kies)
    return aanroepen


def test_een_data_antwoord_krijgt_vervolgvragen_zonder_dat_het_model_een_tool_kiest(monkeypatch, kies_aanroepen):
    # Het model laadt data en antwoordt met gewone tekst: code biedt de vervolgvragen aan (#539).
    text, events, session = _beurt(monkeypatch, _antwoord(_LAAD))

    vragen = _slot(events)["vervolgvragen"]
    assert text.startswith("Het hbo had veel eerstejaars.")
    assert len(kies_aanroepen) == 1
    _aanbod_uit_de_lijst(vragen, "p02ho1ejrs")
    assert session["vervolgvragen_getoond"] == vragen
    assert [c["name"] for c in session["_last_turn_tool_calls"]] == ["get_duo_data"]


@pytest.mark.parametrize(
    ("rondes", "dataset_id"),
    [((_LAAD, _QUERY, _PLOT), "p02ho1ejrs"), ((_LAAD_CBS,), "85353NED"), ((_MAAT,), "p01hoinges")],
    ids=["trend-en-grafiek", "cbs", "get_maat"],
)
def test_ook_na_een_grafiek_een_cbs_tabel_of_een_vaste_maat(monkeypatch, rondes, dataset_id):
    _, events, _ = _beurt(monkeypatch, _antwoord(*rondes))

    _aanbod_uit_de_lijst(_slot(events)["vervolgvragen"], dataset_id)


def test_wat_dit_gesprek_al_aanbood_komt_niet_terug(monkeypatch):
    session = {"vervolgvragen_getoond": ["Welke instellingen trekken de meeste eerstejaars?"]}

    _, events, _ = _beurt(monkeypatch, _antwoord(_LAAD), session=session)

    assert _slot(events)["vervolgvragen"] == [
        "Hoe verdelen eerstejaars zich over de provincies?",
        "Wat is de M/V-verhouding bij eerstejaars?",
    ]
    _, events, _ = _beurt(monkeypatch, _antwoord(_LAAD), session=session)
    assert "vervolgvragen" not in _slot(events)


@pytest.mark.parametrize(
    ("aanroep", "resultaat"),
    [
        (_ZOEK, "no_match: Geen resultaten gevonden."),
        (
            {"id": "u", "name": "get_uwv_vacatures", "arguments": '{"provincie": "Utrecht"}'},
            json.dumps({"bron": "UWV Open Match", "dataset": "uwv-open-match-data", "totaal_vacatures": 1200}),
        ),
        (
            {"id": "r", "name": "get_roa_benchmark", "arguments": "{}"},
            json.dumps({"bron": "ROA, AIS 2030", "dataset": "ais2030", "regio": "Nederland"}),
        ),
    ],
    ids=["alleen-zoeken", "uwv", "roa"],
)
def test_zonder_geladen_dataset_geen_vervolgvragen(monkeypatch, aanroep, resultaat):
    _, events, _ = _beurt(monkeypatch, _antwoord(aanroep, tekst="Dit laat de bron zien."), toolresultaat=resultaat)

    assert "vervolgvragen" not in _slot(events)


def _gestopt(stop_event: asyncio.Event) -> StreamResult:
    """Een modelronde waarin de gebruiker op stop drukt."""
    stop_event.set()
    return StreamResult(text="Het hbo had", tool_calls=[])


def _verduidelijkt(text: str, events: list[dict]) -> bool:
    return any(e["type"] == "clarification" for e in events)


_KAART = Kaart(slot="scope", vraag="Over welke instelling gaat het?", opties=[{"label": "Alle"}, {"label": "Eén"}])


@pytest.mark.parametrize(
    ("steps", "opties", "einde"),
    [
        pytest.param(
            [StreamResult(text="Ik kan geen antwoord geven.", tool_calls=[])],
            {},
            lambda text, events: text == WEIGER_ANTWOORD,
            id="weigering",
        ),
        pytest.param(
            [StreamResult(text="Het hbo had 12.345 eerstejaars.", tool_calls=[])],
            {},
            lambda text, events: text == WEIGER_ANTWOORD,
            id="getal-zonder-data",
        ),
        pytest.param(
            [*_antwoord(_LAAD, tekst="Fout."), StreamResult(text="Nog steeds fout.", tool_calls=[])],
            {"problemen": hard([Probleem("12.345 staat niet in de data.")])},
            lambda text, events: text == INGEHOUDEN,
            id="ingehouden",
        ),
        pytest.param(
            _antwoord(_LAAD, tekst=""),
            {},
            lambda text, events: text == run_module.LEEG_ANTWOORD,
            id="leeg",
        ),
        pytest.param(
            _antwoord(_LAAD),  # het antwoord komt uit de afrondronde
            {"max_iteraties": 1},
            lambda text, events: text.startswith(DEELANTWOORD) and _slot(events)["partial"],
            id="deelantwoord",
        ),
        pytest.param(
            [
                StreamResult(text="", tool_calls=[_LAAD]),
                StreamResult(text="Het hbo", tool_calls=[], finish_reason="length"),
            ],
            {},
            lambda text, events: _slot(events)["truncated"],
            id="afgekapt",
        ),
        pytest.param(
            _antwoord(_LAAD, tekst=""),  # ook de afrondronde geeft geen antwoord
            {"max_iteraties": 1},
            lambda text, events: _slot(events)["partial"] and not text.startswith(DEELANTWOORD),
            id="uitgeput",
        ),
        pytest.param(
            [StreamResult(text="", tool_calls=[_LAAD]), _gestopt],
            {},
            lambda text, events: _slot(events)["aborted"],
            id="afgebroken",
        ),
        pytest.param([StreamResult(text="", tool_calls=[_CLARIFY])], {}, _verduidelijkt, id="clarify_scope"),
        pytest.param([], {"kaart": _KAART}, _verduidelijkt, id="verduidelijkingskaart"),
    ],
)
def test_geen_vervolgvragen_na_een_beurt_zonder_gewoon_antwoord(monkeypatch, kies_aanroepen, steps, opties, einde):
    text, events, session = _beurt(monkeypatch, steps, **opties)

    assert einde(text, events)  # de beurt eindigde echt zo
    assert kies_aanroepen == []
    assert not any("vervolgvragen" in e for e in events)
    assert "vervolgvragen_getoond" not in session


@pytest.mark.parametrize(
    ("result", "tekst"),
    [
        (LoopResult(), WEIGER_ANTWOORD),
        (LoopResult(), INGEHOUDEN),
        (LoopResult(), run_module.LEEG_ANTWOORD),
        (LoopResult(wrapped_up=True), "Deelantwoord."),
        (LoopResult(finish_reason="length"), "Een afgekapt antw"),
    ],
    ids=["weigering", "ingehouden", "leeg", "deelantwoord", "afgekapt"],
)
def test_geen_keuze_buiten_een_gewoon_antwoord(kies_aanroepen, result, tekst):
    assert asyncio.run(run_module._vervolgvragen(result, tekst, _VRAAG, {})) == []
    assert kies_aanroepen == []


def test_een_fout_bij_het_kiezen_kost_het_antwoord_niet(monkeypatch):
    def kapot(*a):
        raise RuntimeError("catalogus weg")

    monkeypatch.setattr(vervolgvragen, "kies", kapot)

    assert asyncio.run(run_module._vervolgvragen(LoopResult(), "Een antwoord.", _VRAAG, {})) == []


def test_elk_gewoon_antwoord_logt_het_aanbod_ook_zonder_vragen(monkeypatch, caplog):
    # Zo is na een deploy uit het log te tellen hoe vaak er knoppen komen (#539): alleen aantallen, geen vraagtekst.
    with caplog.at_level(logging.INFO, logger="agent.run"):
        _beurt(monkeypatch, _antwoord(_LAAD))
        _beurt(monkeypatch, _antwoord(_ZOEK, tekst="Daar vond ik niets."), toolresultaat="no_match: Geen resultaten.")

    regels = [r.getMessage() for r in caplog.records if r.getMessage().startswith("VERVOLGVRAGEN")]
    assert regels == ["VERVOLGVRAGEN  aangeboden=3  datasets=1", "VERVOLGVRAGEN  aangeboden=0  datasets=0"]


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


@pytest.mark.parametrize(
    ("tool", "dataset_id", "bron"),
    [("get_cbs_data", "85353NED", "cbs"), ("get_cbs_data", "85354NED", "cbs"), ("get_duo_data", "p01hoinges", "duo")],
)
def test_de_datasets_van_de_testronde_krijgen_vervolgvragen(tool, dataset_id, bron):
    # Onder antwoorden op deze datasets ontbraken de knoppen in de testronde van 14 oktober (#539).
    steps = [(tool, _laad(f"{bron}:{dataset_id}:0", dataset_id, bron))]

    gekozen = vervolgvragen.kies(steps, "Hoeveel studenten telt het hoger onderwijs?", [])

    assert 1 <= len(gekozen) <= 3
    # Wat beantwoordbare_vragen() voor deze dataset geeft, zonder de hele catalogus te toetsen.
    assert set(gekozen) <= set(vervolgvragen._beantwoordbaar(dataset_id))
