# Kwaliteit & veiligheid

De app heeft meerdere lagen van kwaliteitscontrole en beveiliging om betrouwbare antwoorden te garanderen.

---

## Antwoordkwaliteit

### Wat code afdwingt en wat de prompt alleen vraagt

Een regel in de systeemprompt is een verzoek aan het model, geen garantie. Meetbaar afgedwongen, in code, zijn:

- **Elk getal uit een tool**: de controle na het antwoord (hieronder) houdt een antwoord in met een getal dat niet in de
  opgehaalde data staat; wat die controle wel en niet dekt staat in [Anti-hallucinatie architectuur](anti-hallucination-architecture.md).
- **Herleidbaarheid**: elke toolstap heeft een Python-snippet (`REPRODUCEER` in het log, de redeneerkaart), elk antwoord en
  rapport een manifest met model, prompt-, catalogus-, app- en dataversie (#345), en elk gepubliceerd resultaat (antwoord,
  figuur, CSV-export, rapport) één logregel `GEPUBLICEERD` met per data-key bron, dataset, resource, de key (de digest van de
  selectie), volledigheid, afronding en herlaaddatum, plus die versies en het tijdstip (#169). Geen vraag- of antwoordtekst;
  de selectiestappen in woorden staan op DEBUG.
- **Bronwaarheid, van buiten**: de evals in `tests/e2e/` toetsen natuurlijke vragen tegen ijkwaarden die rechtstreeks bij
  CBS, DUO en RIO zijn opgehaald (#190), en de CI-job `eval:bronwaarheid` draait ze gepland of met de hand tegen de
  testomgeving (`EVAL_BASE_URL`, `EVAL_USERNAME`, `EVAL_PASSWORD`), los van `/health` en `/ready`: dat de server draait
  zegt niets over de juistheid van een antwoord. Het slagingspercentage per model en vraag komt als artifact in
  `eval_results/`.
- **Bronnen, gepland**: de CI-job `bron:ping` doet wekelijks één aanroep per bron door de toollaag van de chat (CBS,
  DUO, RIO en de GeoJSON van de kaart; `scripts/bronping.py`, zonder LLM en zonder testomgeving) en faalt zodra één
  bron niet antwoordt. Een verwijderde API of een gewijzigd filtercontract (RIO v2 → v3 op 19 oktober 2026, #627) komt
  zo bij de beheerder binnen in plaats van via een gebruiker: pytest mockt de bronnen en `/health` toetst er geen.
  Waarden vergelijkt de ping niet; dat doet `scripts/ijkwaarden.py`.

Niet afgedwongen, alleen gevraagd: toon, voorzichtigheid met causaliteit, en of het model de bron goed duidt. De
regels hieronder zijn die verzoeken.

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
| **Zacht** | label of opleidingsvorm, teleenheid, metatekst, verwijzing naar "resource 3", getal dat alleen de gebruiker noemde (een weerlegging citeert het ook), antwoord in de andere taal dan de vraag, u-vorm die de code niet kon omzetten | Het antwoord blijft, met "Let op: …" eronder | Gemaakt, met een waarschuwing |

Een uitzondering in de chat (#619): is het enige harde probleem na de herkansing een getal dat niet in de data staat, dan vervalt alleen de zin of tabelrij met dat getal (`agent/schrappen.py`). De rest wordt opnieuw gecontroleerd en de gebruiker ziet "Zinnen met een getal dat niet in de opgehaalde data staat, zijn weggelaten." Valt er meer dan de helft weg, of blijft de rest hard, dan wordt het antwoord ingehouden zoals hierboven.

Welke controle hard is, staat in code: `hard()` in `agent/probleem.py`, toegepast in `agent/run.py` en `agent/report_checks.py`.

### Taal, decimale komma en aanspreekvorm (#326, #536)

Besluit van de product owner (#326, 14 oktober 2026): het antwoord is in de taal van de vraag, een Nederlands antwoord schrijft decimalen met een komma, en de app spreekt de gebruiker aan met je/jij, nooit met u. De code dwingt dat af; de regels in `prompts/system.md` en `prompts/report.md` zijn een hulpmiddel, geen garantie.

| Regel | Hoe de code het doet |
|-------|----------------------|
| **Taal van de vraag** | `agent/antwoordtaal.py` bepaalt de taal van de vraag met een woordenlijst (nl/en; bij een korte of gemengde vraag beslist de code niets) en zegt het model per beurt in welke taal het antwoordt. Een antwoord dat duidelijk in de andere taal is, krijgt één herkansing. |
| **Decimale komma** | `agent/getalnotatie.py` zet in een antwoord dat niet Engels is 3303 om naar 3.303 en 56.4% naar 56,4%. Een Engels antwoord houdt de notatie van het model. De getalcontrole leest beide spellingen als hetzelfde getal. |
| **Je/jij** | `agent/aanspreekvorm.py` zet in het eindantwoord, de modeltekst van het rapport, de verduidelijkingsvraag en de meldingen een u-vorm om ("het getal dat u noemt" wordt "het getal dat je noemt", "jullie instelling" wordt "je instelling"). `agent/aanspreekcontrole.py` meldt wat daarna nog over is. |

**Liever u dan kapot Nederlands.** Na "u" verandert het werkwoord soms ("wilt u" wordt "wil je", "heeft u" wordt "heb je") en soms niet ("moet u" wordt "moet je"). Zonder woordenboek is dat niet te raden, dus zet de code alleen werkwoorden uit een vaste lijst om. Per zin geldt alles of niets: blijft er in een zin een u-vorm over die niet zeker om te zetten is ("Verlangt u een uitsplitsing?"), dan blijft die hele zin zoals het model hem schreef; de andere zinnen gaan wel om. "Jullie" wordt alleen "je" vóór instelling, opleiding(en) of school. Code, links, HTML, de eigen Bronnen-sectie van het model, en in een rapport de onderzoeksvraag, de titel, de definities en de bronnen blijven ongemoeid: dat zijn citaten van de gebruiker of de bron.

**Zacht, met één herkansing.** Een antwoord in de verkeerde taal en een overgebleven u-vorm zijn zachte problemen: het model krijgt één herkansing, en blijft het probleem, dan staat er "Let op: …" onder het antwoord. Ze houden een antwoord nooit in: het gaat om de vorm, niet om de data. Een rapport krijgt bij een overgebleven u-vorm ook één herkansing en daarna een waarschuwing, nooit een weigering; de taal van een rapport is altijd Nederlands. Eén herkansing en niet meer, omdat elke modelronde tijd en geld kost (#409). Om dezelfde reden kijkt de controle op de aanspreekvorm naar de tekst ná de omzetting: alleen een u-vorm die de code niet kon herstellen kost een herkansing, en een zin die de code zelf omzet niet. In het log staan beide controles per antwoord in de regel `CONTROLES` (`verkeerde_antwoordtaal`, `overgebleven_u_vorm`).

Buiten de je-vorm vallen de dashboards en de redeneerkaart (wat het model onderweg herzag). Vaste teksten uit de app zijn Nederlands, ook bij een Engelse vraag; vertalen is een vervolgstap.

---

## Beveiligingsmaatregelen

Wat de app met gegevens van gebruikers doet (AI-dienst, opslag, browser, log) staat op [Privacy](privacy.md).

### Analyse-sandbox

De `run_analysis`-tool voert door het model geschreven Python uit, in een apart proces (#410, #62). Het model kan daarmee willekeurige Python laten uitvoeren; de afscherming beperkt de schade, maar is **geen beveiligingsgrens** (#443):

- **AST-controle vooraf** (`tools/scriptcontrole.py`): weigert imports, namen en attributen met `__` (ook in een string), frame-attributen, functies als `exec`, `eval`, `open` en `getattr`, en een stdlib-module als attribuut van een bibliotheekobject (`pd.io.common.os`, `pd.compat.sys`; #443), ook in een string: pandas lost `@naam` in `df.query`/`df.eval` en elke naam in `pd.eval` op in de variabelen van het script, dus `df.eval('@pd.io.common.os.getpid()')` wordt op dezelfde tokens geweigerd. `store_get` vraagt een letterlijke key. Dezelfde controle weigert een script dat geen data leest of zelf een reeks getallen intypt; dat bewaakt de herkomst van getallen.
- **Apart proces** (`tools/sandbox.py` start `tools/sandbox_kind.py` met `python -I`): een eigen lege werkmap, een omgeving zonder geheimen (alleen `HOME`, `LANG` en thread-instellingen) en alleen de tabellen die het script opvraagt.
- **Limieten in dat proces:** CPU-tijd (15 s), geheugen (1 GiB), geen bestanden schrijven, geen nieuwe processen. Na 10 seconden stopt de server het proces.
- **Audit hook:** weigert onder meer netwerk, subprocessen, schrijven en het lezen van bestanden buiten de Python-installatie.
- **Beperkte namen:** alleen een handvol builtins (`len`, `range`, `sorted`, `sum`, `round` en vergelijkbare) en `pd`, `np`, `math`, `px`, `go`, `df` en `store_get`.

De AST-controle en de audit hook draaien in Python zelf. De pod draait als niet-root met `seccompProfile: RuntimeDefault`, zonder capabilities en zonder privilege-escalatie (`charts/onderwijsdata-chat/values.yaml`), maar die grens omsluit server en kindproces samen; tussen die twee staat geen kernelgrens zoals een eigen container, seccomp-profiel of aparte gebruiker. Wie de AST-controle omzeilt (de controle op strings is een heuristiek: een expressie die uit stukken is geplakt komt erlangs), kan in het kindproces `os.getpid()`, `os.getcwd()` of de (lege) `os.environ` lezen; `tests/test_sandbox_isolatie.py` legt precies dat vast. Dat restrisico is voor de demofase geaccepteerd en wordt gevolgd in #443; zie ook S11 in `SECURITY.md`. De limieten van het kindproces tellen bovenop het serverproces: de geheugenlimiet van de pod (`manifests/<omgeving>/values.yaml`: 2 GiB op test en playground, 4 GiB op productie) moet die 1 GiB plus de server en de datastore (`STORE_MAX_MB`) kunnen dragen; met de chartstandaard van 1 GiB zou een zwaar script de hele server laten stoppen in plaats van alleen het kindproces.

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
| Search efficiency | 20 | `search_catalog` binnen limiet (≤3x, `SEARCH_CATALOG_LIMIT`) |
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
- **Eval resultaten:** uitvoer van evalruns komt lokaal in `eval_results/` (niet in git, zie `.gitignore`); de CI-job `eval:bronwaarheid` bewaart ze 90 dagen als artifact (#169)
- **Bron-ping:** de geplande CI-job `bron:ping` (schema op `main` met `BRON_PING=1`, ook met de hand via "Run pipeline") roept elke bron één keer aan door de toollaag; een rode geplande pipeline is het signaal (#627)
- **Herkomstlog:** per gepubliceerd resultaat één regel `GEPUBLICEERD` (INFO) met soort, data-keys en versies; de selectiestappen op DEBUG (#169)
