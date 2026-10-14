"""MCP-server voor de catalogus (#41, stap 1): dezelfde schema's en dezelfde uitvoering als de chat.

De definities en de uitvoering zijn zonder de mcp-package te toetsen; het protocol zelf (initialize,
list_tools, call_tool over een in-memory verbinding) alleen met de extra `mcp` geïnstalleerd.
"""

import json

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
        assert definitie["description"] == functie["description"]
        assert definitie["input_schema"] == functie["parameters"]


def test_zoeken_geeft_hetzelfde_resultaat_als_de_chat():
    argumenten = {"query": "ingeschrevenen hbo", "top_n": 3}
    tekst, fout = mcp_server.voer_uit("search_catalog", argumenten)
    assert not fout
    hits = json.loads(tekst)
    assert hits and all("status" in hit for hit in hits)
    assert tekst == tools.dispatch("search_catalog", argumenten)[0]


def test_lege_zoekuitkomst_is_een_resultaat_geen_fout():
    tekst, fout = mcp_server.voer_uit("search_catalog", {"query": "xyzzyq"})
    assert not fout
    assert tekst.startswith("no_match:")


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
    assert json.loads(resultaat.content[0].text)


def test_protocol_markeert_een_sessietool_als_fout():
    _, resultaat = _via_protocol(lambda sessie: sessie.call_tool("query_data", {"data_key": "x"}))
    assert resultaat.is_error
    assert "query_data" in resultaat.content[0].text
