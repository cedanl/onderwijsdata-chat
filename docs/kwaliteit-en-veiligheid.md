# Kwaliteit & veiligheid

De app heeft meerdere lagen van kwaliteitscontrole en beveiliging om betrouwbare antwoorden te garanderen.

---

## Antwoordkwaliteit

De system prompt (`prompts/system.md`) schrijft strikte regels voor die het LLM moet volgen:

| Regel | Uitleg |
|-------|--------|
| **Nooit zelf rekenen** | Alle berekeningen gaan via `query_data` (group_by/aggregate) of `run_analysis` (pandas/numpy). Handmatig optellen is verboden. |
| **Nooit data verzinnen** | Alleen rapporteren wat daadwerkelijk is opgehaald. Als een patroon niet zichtbaar is, wordt dat expliciet gezegd. |
| **Bronvermelding verplicht** | Elk getal verwijst naar een dataset-ID en periode (bijv. "CBS, 85423NED, Perioden: 2023JJ00"). |
| **Eerlijk falen** | Na 2 mislukte pogingen om data op te halen, wordt eerlijk gezegd wat er wel beschikbaar is. |
| **Professionele toon** | Geen complimenten ("goede vraag!"), geen opvulzinnen, direct antwoord. |
| **Voorzichtig met causaliteit** | Causale claims worden geformuleerd als hypothese, niet als feit. |

### Controle na het antwoord (#207)

Code controleert elk antwoord tegen de opgehaalde data. Vindt de controle iets, dan krijgt het model één herkansing. Wat daarna blijft, wordt per soort behandeld:

| Soort | Voorbeelden | Chat | Rapport |
|-------|-------------|------|---------|
| **Hard** | getal dat niet in de data staat, telling op afgekapte data, verkeerd schooljaar of verkeerde instelling in de selectie, getal of kenmerk bij de verkeerde rij, KPI-periode | Het antwoord wordt ingehouden; de gebruiker ziet een vaste tekst met de meldingen eronder | Geweigerd |
| **Zacht** | label of opleidingsvorm, teleenheid, metatekst, verwijzing naar "resource 3", getal dat alleen de gebruiker noemde (een weerlegging citeert het ook) | Het antwoord blijft, met "Let op: …" eronder | Gemaakt, met een waarschuwing |

Welke controle hard is, staat in code: `hard()` in `agent/probleem.py`, toegepast in `agent/run.py` en `agent/report_checks.py`.

---

## Beveiligingsmaatregelen

### Analyse-sandbox

De `run_analysis`-tool voert door het model geschreven Python uit, in een apart proces (#410, #62). Het model kan daarmee willekeurige Python laten uitvoeren; de afscherming beperkt de schade, maar is **geen beveiligingsgrens** (#443):

- **AST-controle vooraf** (`tools/scriptcontrole.py`): weigert imports, namen en attributen met `__` (ook in een string), frame-attributen, functies als `exec`, `eval`, `open` en `getattr`, en een stdlib-module als attribuut van een bibliotheekobject (`pd.io.common.os`, `pd.compat.sys`; #443). `store_get` vraagt een letterlijke key. Dezelfde controle weigert een script dat geen data leest of zelf een reeks getallen intypt; dat bewaakt de herkomst van getallen.
- **Apart proces** (`tools/sandbox.py` start `tools/sandbox_kind.py` met `python -I`): een eigen lege werkmap, een omgeving zonder geheimen (alleen `HOME`, `LANG` en thread-instellingen) en alleen de tabellen die het script opvraagt.
- **Limieten in dat proces:** CPU-tijd (15 s), geheugen (1 GiB), geen bestanden schrijven, geen nieuwe processen. Na 10 seconden stopt de server het proces.
- **Audit hook:** weigert onder meer netwerk, subprocessen, schrijven en het lezen van bestanden buiten de Python-installatie.
- **Beperkte namen:** alleen een handvol builtins (`len`, `range`, `sorted`, `sum`, `round` en vergelijkbare) en `pd`, `np`, `math`, `px`, `go`, `df` en `store_get`.

De AST-controle en de audit hook draaien in Python zelf; er is geen kernelgrens zoals seccomp, een container of een aparte gebruiker. Wie de AST-controle omzeilt, kan in het kindproces `os.getpid()`, `os.getcwd()` of de (lege) `os.environ` lezen; `tests/test_sandbox_isolatie.py` legt precies dat vast. Dat restrisico is voor de demofase geaccepteerd en wordt gevolgd in #443; zie ook S11 in `SECURITY.md`. De limieten van het kindproces tellen bovenop het serverproces: de geheugenlimiet van de pod (`manifests/<omgeving>/values.yaml`, 2 tot 4 GiB) moet die 1 GiB plus de server en de datastore (`STORE_MAX_MB`) kunnen dragen.

### Hard tool limits

| Limiet | Waarde | Reden |
|--------|--------|-------|
| `search_catalog` per vraag | 5 | Voorkomt oneindige zoeklussen |
| `MAX_TOOL_ITERATIONS` | 25 | Breekt de agent-loop af bij te veel stappen |
| `MAX_HISTORY` | 40 | Beheert context window grootte |
| Tool-resultaat grootte | 12.000 karakters | Voorkomt oversized responses |

### Rate limiting

| Endpoint | Limiet | Werking |
|----------|--------|---------|
| `/api/auth/login` | 5 pogingen/minuut per IP | HTTP 429 met `Retry-After` header |
| WebSocket `/api/chat` | `CHAT_RATE_LIMIT` verzoeken per `CHAT_RATE_WINDOW_S` (standaard 30 per 600 s) per gebruiker, zonder login per verbinding | Vraag, verduidelijking, dashboard en rapport tellen mee; daarboven een foutmelding met de wachttijd, geen modelaanroep (#444) |
| LLM API | Exponential backoff (4 retries) | 2s, 4s, 8s, 16s vertraging bij rate limit errors |

### Input validatie

- `query_data` controleert of filterkolommen bestaan, operators geldig zijn (`eq`, `gte`, `lte`, `in`) en aggregatiefuncties correct zijn
- `search_catalog` filtert op geografisch niveau
- `dataset_details` geeft "not found" voor onbekende dataset-ID's
- Foutafhandeling: alle tool-exceptions worden gevangen en als vriendelijke foutmelding teruggegeven aan het LLM — nooit als raw stack trace naar de gebruiker
- Persoonsgegevens in de invoer (#478): de app waarschuwt onder het invoerveld dat een vraag naar een externe AI-dienst gaat, herkent in code een BSN (elfproef), een e-mailadres en een Nederlands telefoonnummer (`frontend/src/persoonsgegevens.js`, `core/persoonsgegevens.py`), waarschuwt bij het typen en houdt zulke tekst uit de gesprekstitel, de exportbestandsnaam en de terugvaltitel van een rapport. De herkenning blokkeert niet: een naam is niet te herkennen en een 9-cijferige code kan de elfproef toevallig doorstaan. De systeemprompt heeft één regel over persoonsgegevens en kleine aantallen

### HTTP beveiligingsheaders

- `Content-Security-Policy` — alleen de eigen origin voor scripts en styles; Plotly voor rapporten en dashboards komt van de eigen server en niet van een CDN (#486)
- `X-Frame-Options: DENY` — geen iframe embed
- `Strict-Transport-Security` — HTTPS forceren
- `X-Content-Type-Options: nosniff` — MIME-type sniffing voorkomen
- `Referrer-Policy: strict-origin-when-cross-origin`

### Authenticatie

- Optionele wachtwoordauthenticatie via `CHAT_USERS`
- HMAC-ondertekende tokens (gebruikersnaam, inlogmoment en vervaltijd, ondertekend met `CHAT_SECRET`) met 8-uur TTL (`SESSION_TTL_HOURS`) en een maximale sessieduur van 24 uur (`SESSION_MAX_HOURS`)
- Uitloggen trekt het token server-side in (denylist in de database)
- Timing-safe wachtwoordvergelijking (`hmac.compare_digest`)

---

## Eval framework

Het project heeft een uitgebreid eval-systeem om de kwaliteit van antwoorden te meten.

### Ground-truth vragen

5 vragen met bekende juiste antwoorden, Elk evalueert een andere complexiteit:

| Vraag | Wat het test |
|-------|-------------|
| Trend-analyse | Meerjarige trend + grafiek |
| Marktaandeel | Berekening + filteren |
| Herkomst-concurrentie | Geografische analyse + aggregatie |
| Arbeidsmarkt-aansluiting | Cross-bron (CBS arbeidsmarkt) |
| VSV-regio | Niche dataset + percentage |

Elke vraag definieert:
- Verwachte datasets en tool-flow
- Referentiewaarden met tolerantiepercentages
- Verplichte termen die in het antwoord moeten voorkomen

### IJkwaarden rechtstreeks uit de bron (#190)

De bronwaarheid-cases (`ijk-*` en de bijbehorende `weigering-*` in `evaluations.json`) stellen ongehulpte,
natuurlijke vragen en toetsen het antwoord tegen waarden die `scripts/ijkwaarden.py` rechtstreeks bij CBS
(OData), DUO en RIO (`riodata`) ophaalt, buiten `tools/` om: een fout in de tools verandert de ijkwaarde niet
mee. De vastgelegde stand staat in `tests/e2e/ijkwaarden.json`, per waarde met bron, selectie, eenheid,
schooljaar, CBS-status en ophaaldag; een eval verwijst ernaar (`data_points.ijkwaarden`) en is exact, zonder
tolerantie. Zonder `--schrijf` toont het script elk verschil met de bron en faalt het; een nieuwe stand is een
bewuste stap in een MR. Definities: `tests/ijkwaarden/README.md`. Met `TEST_REPEATS=3` loopt elke vraag drie
keer per model en schrijft de runner het slagingspercentage per model en vraag naar
`eval_results/slagingspercentage-<datum>.json`; één fout in drie beurten telt.

### Scoring (per vraag, max 100 punten)

| Criterium | Punten | Wat het meet |
|-----------|--------|-------------|
| Search efficiency | 20 | `search_catalog` binnen limiet (≤5x) |
| Juiste tools | 20 | Verwachte tools aangeroepen |
| Dataset match | 20 | Verwacht dataset-ID gevonden |
| Inhoudelijke kwaliteit | 20 | Verplichte termen aanwezig |
| Geen hallucinatie | 10 | Getallen alleen als data-tools zijn aangeroepen |
| Geen timeout | 10 | Antwoord binnen tijd geretourneerd |

### Gedragstests (Playwright E2E)

- **Scope-discipline:** vage vraag moet `clarify_scope` activeren (niet direct data ophalen)
- **Catalog-flow:** `search_catalog` → `dataset_details` (two-stage retrieval)
- **Toon-check:** zakelijke toon, geen fluff of complimenten (regex-detectie)
- **Cross-model vergelijking:** beide modellen vinden dezelfde datasets en vergelijkbare getallen

### Bekende beperkingen

Transparantie over wat nog niet getest is:

- Negatieve gevragen (model moet "nee" zeggen bij niet-bestaande instellingen of toekomstige jaren)
- Multi-turn gesprekken
- De sandbox van `run_analysis` is geen kernelgrens: een ontsnapping uit Python draait als dezelfde gebruiker als de server (#443)
- Reference values kunnen verouderen na dataverversing; voor de ijkwaarden maakt `scripts/ijkwaarden.py` dat zichtbaar
- Geen max-lengte op chat-berichten

---

## Productiemonitoring

- **Health check:** `GET /health` retourneert `{"status":"ok"}`
- **Logging:** gestructureerde logging op INFO-niveau, tool-calls gelogd met argumenten en executietijden
- **Reproduceerbaarheid:** bij elke tool-aanroep wordt een Python-snippet gelogd voor debugging
- **Eval resultaten:** uitvoer van evalruns komt lokaal in `eval_results/` (niet in git, zie `.gitignore`); bewaar langdurige resultaten als CI-artifact
