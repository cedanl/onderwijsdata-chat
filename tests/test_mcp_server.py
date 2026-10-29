"""MCP-server voor de catalogus (#41, stap 1): dezelfde schema's en dezelfde uitvoering als de chat.

De definities en de uitvoering zijn zonder de mcp-package te toetsen; het protocol zelf (initialize,
list_tools, call_tool over een in-memory verbinding) alleen met de extra `mcp` geïnstalleerd.
"""

import json
import urllib.parse

import pytest

import mcp_server
import tools
from tools.schemas import TOOL_SCHEMAS


def _functie(naam: str) -> dict:
    return next(s["function"] for s in TOOL_SCHEMAS if s["function"]["name"] == naam)


def test_alleen_de_stateless_catalogustools():
    definities = mcp_server.tooldefinities()
    assert [d["name"] for d in definities] == ["search_catalog", "dataset_details", "dataset_counts"]
    for definitie in definities:
        assert definitie["name"] in tools._HANDLERS
        assert "data_key" not in definitie["input_schema"]["properties"], "een datastore-tool is niet stateless"


def test_definities_volgen_het_toolschema_van_de_chat():
    for definitie in mcp_server.tooldefinities():
        functie = _functie(definitie["name"])
        assert definitie["description"] == f"{functie['description']} {mcp_server.REGEL_GETALLEN}"
        assert definitie["input_schema"] == functie["parameters"]


def test_instructies_noemen_de_regel_voor_getallen():
    assert mcp_server.REGEL_GETALLEN in mcp_server.INSTRUCTIES
    assert "bewijs" in mcp_server.INSTRUCTIES and "vervolg" in mcp_server.INSTRUCTIES


def test_zoeken_geeft_hetzelfde_resultaat_als_de_chat():
    argumenten = {"query": "ingeschrevenen hbo", "top_n": 3}
    tekst, fout = mcp_server.voer_uit("search_catalog", argumenten)
    assert not fout
    envelop = json.loads(tekst)
    assert envelop["status"] == "candidates"
    assert envelop["kandidaten"] and all("status" in hit and "dataset_id" in hit for hit in envelop["kandidaten"])
    zonder_herkomst = {k: v for k, v in envelop.items() if k not in ("bewijs", "vervolg")}
    assert zonder_herkomst == mcp_server.ontsmet(json.loads(tools.dispatch("search_catalog", argumenten)[0]))


def test_lege_zoekuitkomst_is_een_resultaat_geen_fout():
    tekst, fout = mcp_server.voer_uit("search_catalog", {"query": "xyzzyq"})
    assert not fout
    assert json.loads(tekst)["status"] == "no_match"


def test_telling_komt_uit_de_catalogus():
    tekst, fout = mcp_server.voer_uit("dataset_counts", None)
    assert not fout
    assert set(json.loads(tekst)["datasets_per_bron"]) == {"CBS", "DUO", "RIO"}


def test_details_lezen_door_het_bronvoorvoegsel_heen():
    tekst, fout = mcp_server.voer_uit("dataset_details", {"dataset_id": "duo:p01hoinges"})
    assert not fout
    assert json.loads(tekst)["status"] == "opvraagbaar"


def test_sessietool_is_niet_beschikbaar():
    tekst, fout = mcp_server.voer_uit("query_data", {"data_key": "cbs_85423NED"})
    assert fout
    assert "query_data" in tekst and "search_catalog" in tekst


@pytest.mark.parametrize(
    ("argumenten", "verwacht"),
    [({}, "verplichte parameter ontbreekt: query"), ({"query": "hbo", "onzin": 1}, "onbekende parameter: onzin")],
)
def test_argumenten_worden_vooraf_tegen_het_schema_getoetst(argumenten, verwacht):
    tekst, fout = mcp_server.voer_uit("search_catalog", argumenten)
    assert fout
    assert verwacht in tekst


def test_toolfout_is_een_fout(monkeypatch):
    def kapot():
        raise RuntimeError("geheim argument")

    monkeypatch.setitem(tools._HANDLERS, "dataset_counts", kapot)
    tekst, fout = mcp_server.voer_uit("dataset_counts", {})
    assert fout
    assert "toolfout" in tekst
    assert "geheim" not in tekst, "de fouttekst citeert de uitzondering niet (#502)"


# ── Bewijs, vervolg en ontsmetting (#707, #709) ─────────────────────────────────────────

RESULTATEN = [
    ("search_catalog", {"query": "gediplomeerden mbo", "top_n": 2}),
    ("search_catalog", {"query": "xyzzyq"}),
    ("dataset_details", {"dataset_id": "cbs:85423NED"}),
    ("dataset_details", {"dataset_id": "duo:p01hoinges"}),
    ("dataset_details", {"dataset_id": "cbs:80040ned"}),
    ("dataset_details", {"dataset_id": "onbekend123"}),
    ("dataset_counts", {}),
]
BEWIJS_SLEUTELS = ["bron", "dataset_id", "selectie", "maat", "waarde", "peildatum", "versie", "verwijzing"]


def _teksten(waarde):
    """Elke tekst in een JSON-waarde, sleutels meegeteld."""
    if isinstance(waarde, str):
        yield waarde
    elif isinstance(waarde, list):
        for w in waarde:
            yield from _teksten(w)
    elif isinstance(waarde, dict):
        for k, w in waarde.items():
            yield k
            yield from _teksten(w)


@pytest.mark.parametrize(("naam", "argumenten"), RESULTATEN)
def test_elk_resultaat_is_een_envelope_met_bewijs_en_vervolg(naam, argumenten):
    tekst, fout = mcp_server.voer_uit(naam, argumenten)
    assert not fout
    envelop = json.loads(tekst)
    assert isinstance(envelop, dict), "er staat geen tekst buiten de JSON"
    assert list(envelop["bewijs"]) == BEWIJS_SLEUTELS
    assert envelop["bewijs"]["versie"] == f"catalogus {tools.catalog.catalogus_digest()}"
    assert envelop["vervolg"]["tekst"] == mcp_server.VERVOLG_TEKST
    assert envelop["vervolg"]["url"].startswith(f"{mcp_server.STANDAARD_APP_URL}/chat")


@pytest.mark.parametrize(("naam", "argumenten"), RESULTATEN)
def test_geen_tekst_die_in_de_client_actief_wordt(naam, argumenten):
    tekst, _ = mcp_server.voer_uit(naam, argumenten)
    actief = [
        t
        for t in _teksten(json.loads(tekst))
        if any(teken in t.replace("\\[", "").replace("\\]", "") for teken in "<>[]")
    ]
    assert actief == []


def test_bewijs_van_een_cbs_tabel_noemt_bron_peildatum_en_verwijzing():
    envelop = json.loads(mcp_server.voer_uit("dataset_details", {"dataset_id": "cbs:85423NED"})[0])
    bewijs = envelop["bewijs"]
    assert bewijs["bron"] == "CBS"
    assert bewijs["dataset_id"] == "85423NED"
    assert bewijs["selectie"] == {"dataset_id": "cbs:85423NED"}
    assert bewijs["peildatum"] == tools.catalog.catalogus_laatste_update("85423NED")
    assert bewijs["verwijzing"] == envelop["documentatie"]["url"]


def test_bewijs_van_een_onbekende_dataset_noemt_geen_bron():
    envelop = json.loads(mcp_server.voer_uit("dataset_details", {"dataset_id": "onbekend123"})[0])
    assert "niet gevonden" in envelop["melding"], "een resultaat in gewone tekst staat in de envelope"
    assert envelop["bewijs"]["bron"] == "catalogus"
    assert envelop["bewijs"]["dataset_id"] is None
    assert envelop["vervolg"]["url"] == f"{mcp_server.STANDAARD_APP_URL}/chat", "geen vraag over een onbekende dataset"


def test_vervolg_neemt_de_zoekvraag_mee_begrensd(monkeypatch):
    monkeypatch.setenv("APP_URL", "https://app.example.nl/")
    lang = "instroom " * 100
    envelop = json.loads(mcp_server.voer_uit("search_catalog", {"query": lang})[0])
    url = urllib.parse.urlsplit(envelop["vervolg"]["url"])
    assert f"{url.scheme}://{url.netloc}{url.path}" == "https://app.example.nl/chat"
    assert url.query == "", "in het fragment, niet in de query: die komt in toegangslogs"
    vraag = urllib.parse.parse_qs(url.fragment)["vraag"][0]
    assert vraag == lang.strip()[: mcp_server.MAX_VRAAG]


def test_vervolg_bij_een_dataset_vraagt_naar_de_cijfers_ervan():
    envelop = json.loads(mcp_server.voer_uit("dataset_details", {"dataset_id": "duo:p01hoinges"})[0])
    vraag = urllib.parse.parse_qs(urllib.parse.urlsplit(envelop["vervolg"]["url"]).fragment)["vraag"][0]
    assert vraag == "Welke cijfers staan er in p01hoinges?"


def test_tekst_van_een_bron_wordt_ontsmet(monkeypatch):
    kwaad = {
        "toelichting": "Zie [hier](https://kwaad.example/x) ![](https://kwaad.example/p.png) <img src=x onerror=alert(1)>",
        "<b>kolom</b>": ["[a]", 3],
    }
    monkeypatch.setitem(tools._HANDLERS, "dataset_counts", lambda: json.dumps(kwaad))
    envelop = json.loads(mcp_server.voer_uit("dataset_counts", {})[0])
    assert envelop["toelichting"] == (
        "Zie \\[hier\\](https://kwaad.example/x) !\\[\\](https://kwaad.example/p.png) &lt;img src=x onerror=alert(1)&gt;"
    )
    assert envelop["&lt;b&gt;kolom&lt;/b&gt;"] == ["\\[a\\]", 3]


def test_een_fout_krijgt_geen_bewijs():
    tekst, fout = mcp_server.voer_uit("search_catalog", {})
    assert fout
    assert "bewijs" not in tekst


# ── Het protocol zelf, over een in-memory verbinding ────────────────────────────────────


def _via_protocol(actie):
    pytest.importorskip("mcp", reason="extra `mcp` niet geïnstalleerd")
    import anyio
    from mcp.client.session import ClientSession
    from mcp.shared.memory import create_client_server_memory_streams

    async def draai():
        server = mcp_server.maak_server()
        async with (
            create_client_server_memory_streams() as (client_streams, server_streams),
            anyio.create_task_group() as groep,
        ):
            groep.start_soon(server.run, *server_streams, server.create_initialization_options())
            async with ClientSession(*client_streams) as sessie:
                init = await sessie.initialize()
                uitkomst = await actie(sessie)
            groep.cancel_scope.cancel()
        return init, uitkomst

    return anyio.run(draai)


def test_protocol_noemt_naam_versie_en_instructies():
    init, _ = _via_protocol(lambda sessie: sessie.list_tools())
    assert init.server_info.name == "onderwijscatalogus"
    assert init.server_info.version == mcp_server._versie()
    assert "search_catalog" in (init.instructions or "")


def test_protocol_toont_de_catalogustools_met_het_chatschema():
    _, resultaat = _via_protocol(lambda sessie: sessie.list_tools())
    per_naam = {t.name: t for t in resultaat.tools}
    assert set(per_naam) == {"search_catalog", "dataset_details", "dataset_counts"}
    for naam, tool in per_naam.items():
        assert tool.input_schema == _functie(naam)["parameters"]


def test_protocol_voert_een_zoekactie_uit():
    _, resultaat = _via_protocol(lambda sessie: sessie.call_tool("search_catalog", {"query": "ingeschrevenen hbo"}))
    assert not resultaat.is_error
    envelop = json.loads(resultaat.content[0].text)
    assert envelop["kandidaten"]
    assert list(envelop["bewijs"]) == BEWIJS_SLEUTELS
    assert envelop["vervolg"]["url"].startswith(mcp_server.STANDAARD_APP_URL)


def test_protocol_markeert_een_sessietool_als_fout():
    _, resultaat = _via_protocol(lambda sessie: sessie.call_tool("query_data", {"data_key": "x"}))
    assert resultaat.is_error
    assert "query_data" in resultaat.content[0].text
