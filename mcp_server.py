"""MCP-server voor de onderwijscatalogus (#41, stap 1).

Stelt de catalogustools van de chat via het Model Context Protocol beschikbaar aan elke
MCP-client (Claude Desktop, Cursor, VS Code), zonder de chat-app te draaien. De tooldefinities
zijn dezelfde JSON-schema's als het model in de chat ziet (tools/schemas.py) en de uitvoering is
dezelfde `tools.dispatch`: de scopegrens mbo/hbo/wo (#355), de bron-ID's (#356) en de statussen
per record gelden hier dus ook.

Alleen tools zonder sessie: `search_catalog`, `dataset_details` en `dataset_counts` lezen de
statische catalogus. De datatools (get_*_data, query_data, compute_kpi, get_maat) werken op de
datastore per proces en horen bij stap 2, met auth en de limieten van de chat. Geen auth: de
catalogus is openbaar. Transport: stdio, voor lokale clients.

Starten:  uv sync --extra mcp && uv run python mcp_server.py
"""

import logging
import os
import sys
import tomllib
from pathlib import Path
from typing import Any

import tools
from tools import fouten
from tools.schemas import TOOL_DATASET_COUNTS, TOOL_DATASET_DETAILS, TOOL_SCHEMAS, TOOL_SEARCH_CATALOG

NAAM = "onderwijscatalogus"
INSTRUCTIES = (
    "Catalogus van open Nederlandse onderwijsdata (CBS, DUO en RIO) over mbo, hbo en wo. "
    "Zoek met search_catalog (2 tot 4 losse trefwoorden), bekijk kolommen en bestanden van één "
    "dataset met dataset_details en tel de catalogus met dataset_counts. Elke zoekhit draagt een "
    "`status`: alleen `opvraagbaar` is in de chat-app als data te laden. Deze server levert "
    "metadata; de cijfers zelf haal je bij de bron of in de chat-app."
)

# Stateless: geen data_key en geen datastore. De datatools zijn stap 2 (#41).
CATALOGUS_TOOLS = (TOOL_SEARCH_CATALOG, TOOL_DATASET_DETAILS, TOOL_DATASET_COUNTS)

_PYPROJECT = Path(__file__).resolve().parent / "pyproject.toml"


def _versie() -> str:
    """De release uit het chart (APP_VERSION), anders pyproject.toml; zoals agent.manifest.app_versie,
    maar zonder die module te laden (die trekt litellm mee, seconden opstarttijd voor een catalogus)."""
    if versie := os.getenv("APP_VERSION"):
        return versie
    with open(_PYPROJECT, "rb") as bestand:
        return tomllib.load(bestand)["project"]["version"]


def _functies() -> dict[str, dict[str, Any]]:
    return {s["function"]["name"]: s["function"] for s in TOOL_SCHEMAS}


def tooldefinities() -> list[dict[str, Any]]:
    """De MCP-tooldefinities (naam, beschrijving, invoerschema), één op één uit TOOL_SCHEMAS."""
    functies = _functies()
    return [
        {"name": naam, "description": functies[naam]["description"], "input_schema": functies[naam]["parameters"]}
        for naam in CATALOGUS_TOOLS
    ]


def _controleer(naam: str, argumenten: dict[str, Any]) -> str | None:
    """Verplichte en onbekende parameters vooraf, tegen het schema: de melding noemt de naam, niet de waarde."""
    schema = _functies()[naam]["parameters"]
    bekend = schema.get("properties", {})
    if ontbrekend := [p for p in schema.get("required", []) if p not in argumenten]:
        return f"{naam}: verplichte parameter ontbreekt: {', '.join(ontbrekend)}."
    if onbekend := [p for p in argumenten if p not in bekend]:
        return f"{naam}: onbekende parameter: {', '.join(onbekend)}. Toegestaan: {', '.join(bekend)}."
    return None


def voer_uit(naam: str, argumenten: dict[str, Any] | None) -> tuple[str, bool]:
    """Voer een catalogustool uit via tools.dispatch; (tekst, is_fout).

    Een sessiegebonden of onbekende tool, een schema-afwijking en een toolfout zijn fouten; een lege
    zoekuitkomst (`no_match`) is een gewoon resultaat, net als in de chat.
    """
    if naam not in CATALOGUS_TOOLS:
        return f"Onbekende tool: {naam}. Deze server biedt alleen {', '.join(CATALOGUS_TOOLS)}.", True
    argumenten = dict(argumenten or {})
    if melding := _controleer(naam, argumenten):
        return melding, True
    tekst, _ = tools.dispatch(naam, argumenten)
    return tekst, fouten.code(tekst) is not None


def maak_server():
    """De MCP-server met de catalogustools; de mcp-package laadt pas hier (extra `mcp`)."""
    from mcp import types
    from mcp.server.lowlevel import Server

    async def lijst(_context, _params) -> types.ListToolsResult:
        return types.ListToolsResult(tools=[types.Tool(**definitie) for definitie in tooldefinities()])

    async def aanroep(_context, params: types.CallToolRequestParams) -> types.CallToolResult:
        tekst, fout = voer_uit(params.name, params.arguments)
        return types.CallToolResult(content=[types.TextContent(type="text", text=tekst)], is_error=fout)

    return Server(NAAM, version=_versie(), instructions=INSTRUCTIES, on_list_tools=lijst, on_call_tool=aanroep)


async def _serveer() -> None:
    from mcp.server.stdio import stdio_server

    server = maak_server()
    async with stdio_server() as (lezen, schrijven):
        await server.run(lezen, schrijven, server.create_initialization_options())


def main() -> None:
    import anyio

    # Het protocol loopt over stdout; logregels (zoals de zoeklog van tools/catalog.py) gaan naar stderr.
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s")
    anyio.run(_serveer)


if __name__ == "__main__":
    main()
