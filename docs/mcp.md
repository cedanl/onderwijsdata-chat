# MCP-server voor de catalogus

De catalogus van de chat (CBS, DUO en RIO; mbo, hbo en wo) is ook te doorzoeken vanuit een MCP-client
zoals Claude Desktop, Cursor of VS Code, zonder de chat-app te draaien. `mcp_server.py` biedt drie
tools aan via het [Model Context Protocol](https://modelcontextprotocol.io/), met dezelfde JSON-schema's
die het model in de chat ziet (`tools/schemas.py`) en dezelfde uitvoering (`tools.dispatch`). De
scopegrens mbo/hbo/wo, de bron-ID's en de status per record zijn daardoor gelijk aan die in de chat.
Elk resultaat zegt bovendien zelf waar het vandaan komt en wijst naar de volledige app
([Bewijs en vervolg](#bewijs-en-vervolg)): bij een MCP-client schrijft het model van de client het antwoord, niet de chat.

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

Elke toolbeschrijving eindigt op de regel "Noem geen getal dat niet in een toolresultaat staat."; de instructies
van de server noemen hem ook, met `bewijs` en `vervolg`.

**Niet beschikbaar** zijn de datatools van de chat (`get_cbs_data`, `get_duo_data`, `get_rio_data`,
`query_data`, `compute_kpi`, `get_maat`, …). Die werken op een datastore per sessie en horen bij auth en de
limieten van de chat; stateless datatools voor de EduGenAI-subset zijn [#708](https://git.ia.surf.nl/surf-internal/npuls/ceda/onderwijsdata-chat/-/issues/708).
De server levert metadata; de cijfers haal je bij de bron of in de chat-app.

## Bewijs en vervolg

In de chat controleert de app na het model elk getal tegen de opgehaalde data (`agent/grounding.py`, ADR-001). Bij een
MCP-client gebeurt dat niet: het model van de client schrijft het antwoord. Elk geslaagd resultaat is daarom één
JSON-object met de velden van de chat plus twee vaste sleutels (#707). Wat dat wel en niet waarborgt staat in
[EduGenAI-koppeling](edugenai.md).

**`bewijs`**: waar de waarden in het resultaat vandaan komen. Alle sleutels staan er altijd; `null` als een sleutel
niet van toepassing is.

| Sleutel | Betekenis | Bij de catalogustools |
|---|---|---|
| `bron` | `CBS`, `DUO`, `RIO` of `catalogus` | De leverancier bij `dataset_details` van een dataset die de catalogus kent, anders `catalogus` |
| `dataset_id` | Het ID zoals de catalogus het schrijft | Alleen bij `dataset_details` van een bekende dataset (`cbs:85423NED` → `85423NED`) |
| `selectie` | De argumenten waarmee het resultaat is gemaakt | De toolargumenten; `null` bij `dataset_counts` |
| `maat`, `waarde` | Eén getal uit een datatool en wat het meet | `null`: de catalogus levert metadata; de datatools volgen in #708 |
| `peildatum` | De datum van de bron | De laatste update van een CBS-tabel volgens de catalogus; `null` bij DUO en RIO |
| `versie` | Wat het resultaat leverde | `catalogus <hash>`, dezelfde hash als `catalogus` in de envelope van `search_catalog` |
| `verwijzing` | Waar je het nagaat | De documentatie-URL van de dataset (StatLine-OData, DUO-open-data) |

**`vervolg`**: `{"tekst": "…", "url": "…/chat#vraag=…"}`. De link opent de volledige app met een vraag in de invoer van
een nieuw gesprek ([deep link](api.md#deep-link-naar-de-chat)): bij `search_catalog` de zoekopdracht, bij
`dataset_details` "Welke cijfers staan er in <ID>?". Een dataset die de catalogus niet kent of die buiten mbo, hbo en wo
valt, en `dataset_counts` krijgen de link zonder vraag. De link wijst naar playground; zet `APP_URL` voor een andere
omgeving. De vraag is ten hoogste 500 tekens, dezelfde grens als de app.

**Ontsmet.** Titels, beschrijvingen en definities komen van CBS, DUO en RIO en gaan naar een client die Markdown toont.
In elke tekst van een resultaat, ook in sleutels, krijgen `[` en `]` een backslash en worden `<` en `>` `&lt;` en
`&gt;`. Zo wordt een link, afbeelding of tag uit een bronbeschrijving in de client geen actieve inhoud. Een resultaat in
gewone tekst (een onbekend dataset-ID) staat als `melding` in hetzelfde object: buiten de JSON staat nooit tekst. Een
fout (`isError`) blijft eigen tekst, zonder `bewijs`.

## Stabiliteit

De MCP-server is een stabiele interface: toolnamen, parameters, de envelope van `search_catalog` en de sleutels van
`bewijs` en `vervolg` veranderen niet zonder dat de wijziging als breaking change is aangekondigd. Een nieuwe tool of een nieuwe optionele parameter is dat niet.
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
`pyproject.toml`, zoals `/version`. `APP_URL` (optioneel) is de app waar `vervolg` heen wijst; zonder staat er
playground.

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
  MCP-tooldefinitie (`inputSchema`); het schema is letterlijk dat van de chat, de beschrijving krijgt de regel over
  getallen erachter.
- `voer_uit()` toetst de argumenten vooraf tegen het schema (verplicht, onbekend) en roept `tools.dispatch`
  aan: dezelfde code als een toolaanroep uit het model. `_envelop()` zet er `bewijs` en `vervolg` bij en ontsmet de tekst.
- Een nieuwe catalogustool in de chat is in de MCP-server beschikbaar zodra hij in `CATALOGUS_TOOLS` staat.
  `tests/test_mcp_server.py` bewaakt dat de definities het chatschema volgen en toetst het protocol zelf
  (initialize, `tools/list`, `tools/call`) over een in-memory verbinding.
