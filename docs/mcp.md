# MCP-server voor de catalogus

De catalogus van de chat (CBS, DUO en RIO; mbo, hbo en wo) is ook te doorzoeken vanuit een MCP-client
zoals Claude Desktop, Cursor of VS Code, zonder de chat-app te draaien, en vanuit SURF AI Chat (EduGenAI) via
`/mcp` in de app ([Over HTTP](#over-http-mcp-in-de-app)). `mcp_server.py` biedt drie
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

De MCP-SDK (`mcp`) is een gewone dependency en zit ook in het chat-image (#938); `uv sync` installeert hem.

```bash
uv sync
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
npx @modelcontextprotocol/inspector uv run python mcp_server.py
```

## Over HTTP: /mcp in de app

SURF AI Chat (aichat.surf.nl, voorheen EduGenAI) koppelt een extensie met een URL, een transporttype en een header; een
stdio-server kan het niet aanroepen. Daarom biedt de chat-app dezelfde server ook aan op `/mcp`, als
streamable-http-endpoint (#706). Eén pod en dezelfde ingress als de chat: `/health`, `/version` en de chat blijven
werken zoals ze werkten, en er is geen tweede deployment.

- **Stateless, JSON-antwoorden.** Elk verzoek krijgt een eigen transport: geen sessie per client (`Mcp-Session-Id`
  ontbreekt), geen SSE-stroom en geen GET-stroom. Dat past bij de catalogustools, die geen datastore hebben, en bij
  één pod. Elke `POST /mcp` draagt één JSON-RPC-bericht en krijgt één JSON-antwoord; `GET` en `DELETE` krijgen 405
  (`Allow: POST`), zoals de spec voor een server zonder stroom voorschrijft.
- **Dezelfde server als stdio.** Beide transporten bouwen hun server met `maak_server()`: dezelfde
  `tooldefinities()`, `INSTRUCTIES` en `voer_uit()`, dus dezelfde envelope, scopegrens en statussen. Over HTTP draait
  een aanroep in een thread, zodat de eerste zoekactie (het DUO-register laden) de chat niet ophoudt.
- **Alleen met sleutels.** Zonder `MCP_API_KEYS` bestaat `/mcp` niet: elk verzoek, ook `GET`, krijgt 404 en het log
  zegt bij de start één keer waarom. Met sleutels vraagt elk verzoek er een ([Sleutels](#sleutels)).
- **Log.** Per aanroep een regel `MCP TOOL <naam> args_len=… args_hash=… fout=… duur=… tekens=… sleutel_len=… sleutel_hash=…`:
  de argumenten (zoekwoorden, vaak uit de vraag van de gebruiker) alleen als kenmerk, zoals in de chat, en welke
  sleutel de aanroep deed.

Lokaal, met de app op poort 8000 en een sleutel in `MCP_API_KEYS`:

```bash
npx @modelcontextprotocol/inspector --cli http://localhost:8000/mcp --transport http \
  --header "Authorization: Bearer $MCP_SLEUTEL" --method tools/list
```

Zonder `--cli` opent de Inspector in de browser; kies daar transport "Streamable HTTP", URL `http://localhost:8000/mcp`
en de header `Authorization`.

### Sleutels

`/mcp` staat niet open op internet: elk verzoek draagt `Authorization: Bearer <sleutel>` met een sleutel uit
`MCP_API_KEYS` (#939). Zonder header, met een ander schema of met een onbekende sleutel: 401 met
`WWW-Authenticate: Bearer`. Geen OAuth in deze stap.

- **Meer sleutels tegelijk**, kommagescheiden: een eigen sleutel per consument (een gebruikersextensie in de spike
  #705, een globale entry per tenant #711), en roteren zonder onderbreking.
- **Vergelijking** constant-time, op een SHA-256 van gelijke lengte en tegen alle sleutels zonder vroeg te stoppen.
- **Nooit in een log of foutmelding.** Het log noemt per aanroep een sleutel-ID (`sleutel_len=… sleutel_hash=…`,
  `tekst_kenmerk`; met `LOG_HASH_SECRET` een HMAC), genoeg om te zien welke consument het was en niet terug te rekenen.
  Een geweigerd verzoek geeft de regel `MCP 401: geen of ongeldige sleutel`, zonder de aangeboden waarde.

**Aanmaken.** Een willekeurige sleutel per consument, buiten een LLM-sessie:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

**Zetten.** `MCP_API_KEYS` staat in de secret `onderwijsdata-chat-secrets` van de omgeving; `manifests/test/values.yaml`
leest hem `optional` (zonder sleutel geen `/mcp`). Sjabloon: `manifests/test/secret.yaml.example`; versleutelen met
SOPS zoals in [Deployment → Secrets](deployment.md#3-secrets-configuration). De sleutel van een consument gaat via een
eigen, veilig kanaal naar de beheerder van die consument (bij een globale entry: Npuls/SURF, #711), nooit in een issue
of chat.

**Roteren.** Zet de nieuwe sleutel naast de oude (`oud,nieuw`), rol uit, laat de consument overstappen en haal daarna
de oude weg. Een sleutel intrekken is hetzelfde zonder de nieuwe. Na een wijziging van de secret herstart de pod niet
vanzelf: `kubectl rollout restart` (de app leest `MCP_API_KEYS` bij de start).

### Limieten

Eén pod met toestand in het geheugen (#677): één consument van `/mcp` mag de chat niet voor iedereen traag maken (#940).
De limieten staan los van die van de chat; een volle `/mcp` raakt de chat niet, en andersom. Volgorde per verzoek:

| Stap | Antwoord | Instelling (standaard) |
|---|---|---|
| Rate limit per IP, ook voor een foute sleutel | 429 met `Retry-After` | `MCP_RATE_LIMIT_IP` (120) per `MCP_RATE_WINDOW_S` (60 s) |
| Sleutel | 401 | `MCP_API_KEYS` |
| Alleen POST | 405 | |
| Rate limit per sleutel | 429 met `Retry-After` | `MCP_RATE_LIMIT` (60) per `MCP_RATE_WINDOW_S` |
| Een vrije plaats | 503 met `Retry-After: 5`, na hooguit `MCP_WACHT_S` (1 s) | `MCP_MAX_GELIJKTIJDIG` (4) |
| Tijdslimiet per toolaanroep | MCP-fout (`isError`) met de tool en de grens | `MCP_TOOL_TIMEOUT_S` (30 s) |
| Grootte van een resultaat | `{"melding": "Afgekapt: …", "begin": "…", "bewijs": …, "vervolg": …}` | `TOOL_RESULT_MAX_CHARS` (12000) |

- Een sessie van een MCP-client kost een paar verzoeken (`initialize`, de bevestiging, `tools/list`) plus één per
  toolaanroep; 60 per minuut is ruim voor een paar gelijktijdige gesprekken per sleutel.
- **Per IP** ziet de app achter de ingress het adres van de ingress, zolang uvicorn `X-Forwarded-For` niet vertrouwt
  (`FORWARDED_ALLOW_IPS`, SECURITY.md S5). Dan werkt deze grens als totaalgrens voor `/mcp` op de pod.
- **Tijdslimiet.** Een toolaanroep draait in een thread en is daar niet te stoppen: na de grens krijgt de client een
  fout, de aanroep loopt door en houdt zijn thread vast. Toolaanroepen van `/mcp` hebben eigen threads
  (`MCP_MAX_GELIJKTIJDIG`), dus een hangende aanroep raakt de threads van de chat niet.
- **Afkappen.** Zoals in de chat ziet het model het begin met een melding; anders dan daar blijft het resultaat één
  geldig JSON-object, met `bewijs` en `vervolg`. `search_catalog` blijft zelf onder de grens door hele treffers weg te
  laten.
- Voorzichtige standaarden; de definitieve waarden volgen uit de belastingsmeting (#942).

### SURF AI Chat

Een extensie in SURF AI Chat, of een globale entry in de LibreChat-config van een tenant (`mcpServers`, #711):

```yaml
mcpServers:
  onderwijsdata:
    type: streamable-http
    url: https://onderwijsdata-chat.test.sdp.surf.nl/mcp
    headers:
      Authorization: "Bearer ${ONDERWIJSDATA_MCP_KEY}"
    serverInstructions: true
```

In het formulier voor een eigen extensie: URL zoals hierboven, transport "Streamable HTTP", authenticatie "API Key" met
de sleutel als Bearer. `/mcp` staat nog op geen enkele omgeving: eerst test (#941).

## Clientconfiguratie (stdio)

Claude Desktop (`claude_desktop_config.json`), Cursor (`.cursor/mcp.json`) en VS Code (`.vscode/mcp.json`)
gebruiken hetzelfde formaat; vul het pad naar deze repository in:

```json
{
  "mcpServers": {
    "onderwijscatalogus": {
      "command": "uv",
      "args": ["run", "--directory", "/pad/naar/onderwijsdata-chat", "python", "mcp_server.py"]
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
- `routes/mcp_http.py` zet dezelfde server achter `/mcp`: de sessiemanager van de SDK in stateless modus met
  JSON-antwoorden. Die heeft een taakgroep nodig die zo lang leeft als de app, dus `server.create_app` start hem in de
  lifespan van de app; een gemounte Starlette-app krijgt geen eigen lifespan. `tests/test_mcp_http.py` toetst het
  protocol eind tot eind tegen de app, met de client van de SDK.
