# MCP-server voor de catalogus

De catalogus van de chat (CBS, DUO en RIO; mbo, hbo en wo) is ook te doorzoeken vanuit een MCP-client
zoals Claude Desktop, Cursor of VS Code, zonder de chat-app te draaien. `mcp_server.py` biedt drie
tools aan via het [Model Context Protocol](https://modelcontextprotocol.io/), met dezelfde JSON-schema's
die het model in de chat ziet (`tools/schemas.py`) en dezelfde uitvoering (`tools.dispatch`). De
scopegrens mbo/hbo/wo, de bron-ID's en de status per record zijn daardoor gelijk aan die in de chat.

## Tools

| Tool | Doet | Voorbeeld |
|------|------|-----------|
| `search_catalog` | Zoekt datasets op 2 tot 4 losse trefwoorden, optioneel gefilterd op geografisch niveau | `{"query": "gediplomeerden mbo", "top_n": 5}` |
| `dataset_details` | Kolommen, bestanden en definities van één dataset; met bronvoorvoegsel (`cbs:85423NED`, `duo:p01hoinges`, `rio:erkenningen`) of zonder | `{"dataset_id": "duo:p01hoinges"}` |
| `dataset_counts` | Aantal datasets per bron | `{}` |

Elke zoekhit en elk detailrecord draagt een `status`: `opvraagbaar`, `via_tool`, `alleen_documentatie` of
`alleen_catalogus`; alleen `opvraagbaar` is in de chat-app als data te laden. Een lege zoekuitkomst
(`"status":"no_match"`) is een gewoon resultaat, net als in de chat: `search_catalog` geeft altijd dezelfde
JSON-envelope met `status`, `kandidaten`, `melding` en `vervolgstap` (zie [Tools](tools.md#search_catalog)). Een onbekende tool, een parameter buiten het
schema of een fout in de tool komt terug als MCP-fout (`isError`), met de parameternaam en zonder de waarde.

**Niet beschikbaar** zijn de datatools van de chat (`get_cbs_data`, `get_duo_data`, `get_rio_data`,
`query_data`, `compute_kpi`, `get_maat`, …). Die werken op een datastore per sessie en horen bij auth en de
limieten van de chat; dat is stap 2 van [#41](https://git.ia.surf.nl/surf-internal/npuls/ceda/onderwijsdata-chat/-/issues/41).
De server levert metadata; de cijfers haal je bij de bron of in de chat-app.

## Stabiliteit

De MCP-server is een stabiele interface: toolnamen, parameters en de envelope van `search_catalog` veranderen niet
zonder dat de wijziging als breaking change is aangekondigd. Een nieuwe tool of een nieuwe optionele parameter is dat niet.
Wat stabiel is en wat niet, staat in [API-referentie → Wat is stabiel](api.md#wat-is-stabiel).

## Starten

De server zit in de optionele extra `mcp`; de MCP-SDK staat niet in het chat-image.

```bash
uv sync --extra mcp
uv run python mcp_server.py     # stdio: wacht op een MCP-client
```

Het transport is stdio: de client start het proces zelf. Protocolberichten lopen over stdout, logregels
over stderr. Er is geen API-sleutel nodig: de catalogus is openbaar en de server roept geen taalmodel
aan. De eerste zoekactie laadt het instellingenregister van DUO (netwerk, enkele seconden); daarna is
zoeken direct. De server meldt zich als `onderwijscatalogus` met de versie uit `APP_VERSION` of
`pyproject.toml`, zoals `/version`.

Zonder client testen kan met de MCP Inspector:

```bash
npx @modelcontextprotocol/inspector uv run --extra mcp python mcp_server.py
```

## Clientconfiguratie

Claude Desktop (`claude_desktop_config.json`), Cursor (`.cursor/mcp.json`) en VS Code (`.vscode/mcp.json`)
gebruiken hetzelfde formaat; vul het pad naar deze repository in:

```json
{
  "mcpServers": {
    "onderwijscatalogus": {
      "command": "uv",
      "args": ["run", "--directory", "/pad/naar/onderwijsdata-chat", "--extra", "mcp", "python", "mcp_server.py"]
    }
  }
}
```

## Hoe het werkt

- `tooldefinities()` zet naam, beschrijving en `parameters` van elke tool in `CATALOGUS_TOOLS` om naar een
  MCP-tooldefinitie (`inputSchema`); het schema is letterlijk dat van de chat.
- `voer_uit()` toetst de argumenten vooraf tegen het schema (verplicht, onbekend) en roept `tools.dispatch`
  aan: dezelfde code als een toolaanroep uit het model.
- Een nieuwe catalogustool in de chat is in de MCP-server beschikbaar zodra hij in `CATALOGUS_TOOLS` staat.
  `tests/test_mcp_server.py` bewaakt dat de definities het chatschema volgen en toetst het protocol zelf
  (initialize, `tools/list`, `tools/call`) over een in-memory verbinding.
