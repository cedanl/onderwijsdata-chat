# Kwaliteit & veiligheid

De app heeft meerdere lagen van kwaliteitscontrole en beveiliging om betrouwbare antwoorden te garanderen.

---

## Antwoordkwaliteit

### Wat code afdwingt en wat de prompt alleen vraagt

Een regel in de systeemprompt is een verzoek aan het model, geen garantie. Meetbaar afgedwongen, in code, zijn:

- **Elk getal uit een tool**: de controle na het antwoord (hieronder) houdt een antwoord in met een getal dat niet in de
  opgehaalde data staat; wat die controle wel en niet dekt staat in [Anti-hallucinatie architectuur](anti-hallucination-architecture.md).
- **Herleidbaarheid**: elke toolstap heeft een Python-snippet (`REPRODUCEER` in het log, de redeneerkaart), elk antwoord en
  rapport een manifest met model, prompt-, catalogus-, app- (met de korte build-commit uit `GIT_COMMIT`, #1123) en dataversie (#345; de catalogusversie is dezelfde digest
  als `catalogus_digest` in `/version`, #1029), en elk gepubliceerd resultaat (antwoord,
  figuur, CSV-export, rapport) één logregel `GEPUBLICEERD` met per data-key bron, dataset, resource, de key (de digest van de
  selectie), volledigheid, afronding, herlaaddatum en, voor een CBS- of RIO-bron, de `inhoudshash` van de brontabel (#715) en voor een DUO-bron de `bronhash`, de md5 van het bestand (#717), plus die versies en het tijdstip (#169). Geen vraag- of antwoordtekst;
  de selectiestappen in woorden staan op DEBUG.
- **Bronwaarheid, van buiten**: de evals in `tests/e2e/` toetsen natuurlijke vragen tegen ijkwaarden die rechtstreeks bij
  CBS, DUO en RIO zijn opgehaald (#190), en de CI-job `eval:bronwaarheid` draait ze gepland of met de hand tegen de
  testomgeving (`EVAL_BASE_URL`, `EVAL_USERNAME`, `EVAL_PASSWORD`), los van `/health` en `/ready`: dat de server draait
  zegt niets over de juistheid van een antwoord. Het slagingspercentage per model en vraag komt als artifact in
  `eval_results/`.
- **Bronnen, gepland**: de CI-job `bron:ping` doet dagelijks één aanroep per bron door de toollaag van de chat (CBS,
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
| **Verklaringen alleen op verzoek** | Een oorzaak of vermoeden komt alleen in het antwoord als de gebruiker erom vraagt (#1036); code beslist dat uit de vraag. Dan staat het in een apart blok "Niet uit de data": hooguit drie toetsbare vragen, elk met een bron uit de catalogus of "hiervoor is geen bron in deze app", nooit als feit. De controle na het antwoord toetst het. |

### Controle na het antwoord (#207)

Code controleert elk antwoord tegen de opgehaalde data. Vindt de controle iets, dan krijgt het model één herkansing. Het stappenbudget geldt voor de hele vraag: de herkansing krijgt hooguit wat er van het budget over is, en na een op budget (of een afrondronde) geen tools meer (#1090). Wat daarna blijft, wordt per soort behandeld:

| Soort | Voorbeelden | Chat | Rapport |
|-------|-------------|------|---------|
| **Hard** | getal dat niet in de data staat, telling op afgekapte data, verkeerd schooljaar of verkeerde instelling in de selectie, getal of kenmerk bij de verkeerde rij, KPI-periode, een uitgeschreven rekensom die niet klopt (alleen chat, #1001), een telling ("10 van de 12") die niet klopt met de tabel in het antwoord (alleen chat, #1013), een dataset-ID dat niet in de catalogus staat en dat noch de vraag noch een toolresultaat noemde (alleen chat, #1084) | Het antwoord wordt ingehouden; de gebruiker ziet een vaste tekst met de meldingen eronder | Geweigerd |
| **Zacht** | label of opleidingsvorm, teleenheid, metatekst, verwijzing naar "resource 3", getal dat alleen de gebruiker noemde (een weerlegging citeert het ook), antwoord in de andere taal dan de vraag, u-vorm die de code niet kon omzetten, een vergelijking ("meer A dan B") die niet klopt met de tabel (alleen chat, #1013) | Het antwoord blijft, met "Let op: …" eronder | Gemaakt, met een waarschuwing |

Een uitzondering in de chat (#619): is het enige harde probleem na de herkansing een getal dat niet in de data staat, dan vervalt alleen de zin of tabelrij met dat getal (`agent/schrappen.py`). De rest wordt opnieuw gecontroleerd en de gebruiker ziet "Zinnen met een getal dat niet in de opgehaalde data staat, zijn weggelaten." Gaat het om een tabelrij, dan noemt de melding de rij bij haar eerste cel ("Tabelrijen met een getal … zijn weggelaten (rij: 2025/26)", #1099). Valt er meer dan de helft weg, of blijft de rest hard, dan wordt het antwoord ingehouden zoals hierboven.

Welke controle hard is, staat in code: `hard()` in `agent/probleem.py`, toegepast in `agent/controles.py` en `agent/report_checks.py`.

### Welke beurten in het rapport komen (#908)

Bij "Genereer rapport" toont de app boven het veld met de onderzoeksvraag een checklist van de beurten met data: per beurt de vraag van de gebruiker (ingekort) en de bronregels van haar data. Alles staat standaard aan; het veld blijft van de gebruiker en wordt niet uit de keuze herschreven. De lijst en het filter zijn code (`agent/rapportselectie.py`), geen model, en er wordt niets op een gok aan- of uitgezet.

- **Een beurt** is een vraag van de gebruiker waarbij minstens één dataset ontstond (`session["data_vraag"]`, #733). Een beurt die alleen data van een eerdere beurt hergebruikt, heeft geen eigen regel.
- **De server filtert.** Het rapportverzoek (`generate_report`) kan `beurten` meesturen. De server controleert die tegen het gesprek en bouwt een weergave zonder de uitgezette beurten: hun vraag, datasets, rekenbewijs en figuren. Bronnen, definities, dataversie (#738), de getal- en percentage-controle (#754, #872), de afwijkingen (#734) en wat een tool "beschikbare data" noemt volgen uit die weergave, dus een uitgezette beurt komt nergens terug. De overgebleven vragen krijgen opnieuw een nummer, en zonder bevestigde onderzoeksvraag is de eerste overgebleven vraag het onderwerp.
- **Zonder selectie, of met alles aan,** is het rapport hetzelfde als vroeger. Een lege selectie, een onbekend nummer of een selectie bij een gesprek zonder checklist wordt geweigerd met een melding, vóór er een run start; onbekende nummers negeren zou stil een ander rapport geven dan de gebruiker op zijn scherm kiest. De UI laat alles uit niet toe.
- **Eén uitzondering:** de herkomst van een gekozen dataset blijft tot zijn laadaanroep. Bouwt een beurt voort op de data van een uitgezette beurt, dan staat de bron van die laadaanroep in het rapport, want de data komt daar vandaan. De checklist zegt dat bij de beurt ("Bouwt voort op … Die bron blijft vermeld").
- **Geen checklist** zonder bewijs per beurt: heeft een dataset van het gesprek geen vraagnummer (een gesprek van vóór #875, of een antwoord dat de geschiedenis niet meer haalt), of is er één beurt met data, dan toont de app alleen het veld en rust het rapport op het hele gesprek. Een heropend gesprek met bewijs per beurt (`beurtbewijs`, ADR-009) geeft dezelfde lijst als een levend gesprek.
- **Privacy:** de selectie wordt nergens bewaard; ze reist mee in het rapportverzoek. De vragen in de checklist komen uit het gesprek van de gebruiker zelf en staan niet in het log (alleen aantallen).

### Welke figuren in het rapport komen (#993)

Het rapport toont wat de gebruiker in de chat zag, en niets anders (besluit 18-11): het rapportmodel heeft geen grafiek- of kaarttool en tekent zelf niets. De checklist noemt per beurt de figuren die op haar data rusten, standaard aan; het rapport bevat precies de figuren die aanstaan, hoogstens vier. Zonder gekozen figuren, of in een gesprek zonder figuren, heeft het rapport alleen tekst.

- **Opnieuw gemaakt, niet gekopieerd.** De server legt bij elke figuur in de chat de stap vast die haar maakte (`agent/figuurstappen.py`): tool, argumenten, de titel van de figuur die de server maakte en de keys waarop ze rust. Het rapport draait die stap opnieuw (`agent/report_figuren.py`) via `tools.dispatch`, op de data die `herstel_data` terugzette, met dezelfde sandbox en scriptcontrole als in de chat. De figuur-JSON in het opgeslagen gesprek komt van de client en wordt nooit gelezen.
- **Een figuur trekt haar beurt mee.** Een figuur staat bij de beurt waarin de data van haar `data_key` ontstond. Kiest de gebruiker een figuur, dan gaan de beurten van al haar keys mee in de selectie; de server controleert de ids tegen het gesprek, en een onbekende id of meer dan vier wordt geweigerd.
- **Het model krijgt de figuren als gegeven.** De prompt beschrijft elke figuur uit code (titel, soort, reeksen of knopen en waarden); het model schrijft per figuur een titel en toelichting en de conclusie. De waarden van de figuren tellen als bewijs voor de controles; hun titels niet, want die schreef het model in de chat (#211). Net als bij een toolresultaat telt een getal dat niet van de data afhangt niet mee (#410, CH-27): bij een figuur uit een script draait de server dat script nog twee keer op verstoorde invoer en meet welke waarden in de figuur dan blijven staan (`analysis.figuurtoets`); bij een grafiek of kaart telt niet wat haar key als eigen berekening meedraagt (`scriptconstanten`). Een figuur zonder bron (een script dat geen data las, een key zonder bekende herkomst) bewijst niets (#201). Alle controles (getallen, percentages, figuurverwijzing, bronregel onder de figuur, periode in de titel) gelden voor deze figuren.
- **Lukt een figuur niet meer** (data niet te herstellen, een fout in het script, een lege figuur), dan valt ze weg met de regel "Deze figuur uit het gesprek kon niet opnieuw gemaakt worden." vooraan in wat het rapport niet beantwoordt. Het rapport wordt daarom niet geweigerd.
- **Een figuur blijft zoals ze was.** Het rapport snijdt een figuur niet meer bij tot een periode in een titel (dat deed #385 met figuren van het rapportmodel). Herladen data kan afwijken van de chat; de melding "data is herladen" en de bronregel blijven.

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
| `MAX_HISTORY` | 40 | Beheert context window grootte; de eerste vraag blijft altijd staan (#789). De helft is het aantal vragen per gesprek |
| Tool-resultaat grootte | 12.000 karakters | Voorkomt oversized responses |

### Rate limiting

| Endpoint | Limiet | Werking |
|----------|--------|---------|
| `/api/auth/login` | 5 pogingen/minuut per gebruikersnaam + adres (S5) | HTTP 429 met `Retry-After` header |
| WebSocket `/api/chat` | `CHAT_RATE_LIMIT` verzoeken per `CHAT_RATE_WINDOW_S` (standaard 30 per 600 s) per gebruiker, zonder login per verbinding | Vraag, verduidelijking en rapport tellen mee; daarboven een foutmelding met de wachttijd, geen modelaanroep (#444) |
| Tokenbudget | `TOKENBUDGET_DAG` (1.500.000) per dag en `TOKENBUDGET_MAAND` (15.000.000) per maand per gebruiker, in invoertoken-equivalenten (gewogen naar de tarieven) | Elke run telt mee in de database (`tokengebruik`, gedeeld door de pods); erboven een melding wanneer het weer kan en geen modelaanroep. Een databasefout laat de chat door (#678). Accounts in `TOKENBUDGET_VRIJGESTELD` hebben geen budget; op test is dat `demo` (#1234) |
| Open WebSocket-verbindingen | `MAX_WS_PER_USER` (10) per gebruiker, `MAX_WS_TOTAL` (100) in totaal | Daarboven een melding en close-code 1013 (#688) |
| Gelijktijdige runs | `MAX_CONCURRENT_RUNS` (8) modelruns, `MAX_SANDBOX_RUNS` (2) sandboxprocessen | Wachtrij; na `RUN_QUEUE_TIMEOUT_S` (60 s) of `SANDBOX_QUEUE_TIMEOUT_S` (20 s) een melding dat het druk is (#688) |
| Dashboardladingen | `MAX_DASHBOARD_LOADS` (4) tegelijk, tijdsgrens `DASHBOARD_TIMEOUT_S` (90 s) | Wachtrij; na `DASHBOARD_QUEUE_TIMEOUT_S` (30 s) HTTP 503 dat het druk is, na de tijdsgrens HTTP 504; de frontend biedt een nieuwe poging (#901) |
| Opslag per gebruiker | `MAX_GESPREKKEN_PER_GEBRUIKER` (1000) gesprekken, `MAX_WERKBOEKEN_PER_GEBRUIKER` (500) werkboeken, samen `MAX_OPSLAG_PER_GEBRUIKER_MB` (100 MB) | `PUT` van een gesprek of werkboek daarboven krijgt HTTP 507 met een melding; wat er staat blijft, bijwerken telt alleen het verschil, zonder login geen quotum (#682, S24) |
| Verzoekgrootte | `MAX_REQUEST_BYTES` (4 MiB) per HTTP-verzoek en per WebSocket-bericht | Daarboven HTTP 413; uvicorn sluit een te groot WebSocket-bericht (#682) |
| LLM API | Exponential backoff (4 retries) | 2s, 4s, 8s, 16s vertraging bij rate limit errors |

### Input validatie

- `query_data` controleert of filterkolommen bestaan, operators geldig zijn (`eq`, `gte`, `lte`, `in`) en aggregatiefuncties correct zijn
- `search_catalog` filtert op geografisch niveau en geeft altijd één envelope met een getypeerde `status` (`candidates`, `no_match`, `needs_clarification`, `out_of_scope`, `metadata_unknown`, `source_unavailable`, `tool_error`); een miss is nooit "de data bestaat niet"
- `dataset_details` geeft "not found" voor onbekende dataset-ID's
- Foutafhandeling: alle tool-exceptions worden gevangen en als vriendelijke foutmelding teruggegeven aan het LLM — nooit als raw stack trace naar de gebruiker
- Persoonsgegevens in de invoer (#478): de app waarschuwt onder het invoerveld dat een vraag naar een externe AI-dienst gaat, herkent in code een BSN (elfproef), een e-mailadres en een Nederlands telefoonnummer (`frontend/src/persoonsgegevens.js`, `core/persoonsgegevens.py`), waarschuwt bij het typen en houdt zulke tekst uit de gesprekstitel, de exportbestandsnaam en de terugvaltitel van een rapport. De herkenning blokkeert niet: een naam is niet te herkennen en een 9-cijferige code kan de elfproef toevallig doorstaan. De systeemprompt heeft één regel over persoonsgegevens en kleine aantallen

### HTTP beveiligingsheaders

- `Content-Security-Policy` — alleen de eigen origin voor scripts en styles; Plotly voor rapporten en dashboards komt van de eigen server en niet van een CDN (#486); `base-uri` en `form-action` alleen de eigen origin (#682)
- `Cache-Control: no-store` op `/api/` (#682)
- WebSocket `/api/chat` alleen vanaf de eigen origin of een origin uit `CORS_ORIGINS`, anders close-code 4003 (#682, `core/herkomst.py`)
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
(OData), DUO en RIO (`onderwijsbronnen`) ophaalt, buiten `tools/` om: een fout in de tools verandert de ijkwaarde niet
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
- **Rapport volgt de keuze:** de rapporteval (`rapport-bijsturing.spec.js`, #752) speelt ook een gesprek waarin de gebruiker bij
  Genereer rapport een zijsprong uitzet (`rapport-zijsprong-uit`, #908): het rapport noemt die nergens, ook niet in de
  bronnen of de dataversie (`spec_niet` in `tests/e2e/rapportscenarios.json`)
- **Weigeringen:** vragen zonder open data, buiten de reeks, over een niet-bestaande opleiding of instelling of over een
  toekomstig jaar moeten geweigerd worden, zonder getal dat niet uit een tool komt (`expected.must_refuse` in
  `tests/e2e/evaluations.json`, gescoord door `refusal.js`). Ze zijn kritiek: een weigering moet in elke herhaling
  slagen ([Promoten](promoten.md), stap 0)

### Bekende beperkingen

Transparantie over wat nog niet getest is:

- Multi-turn gesprekken buiten het rapport: alleen de rapporteval (`rapport-bijsturing.spec.js`, #752) speelt een gesprek
  van meer beurten, als opmaat naar een rapport
- De sandbox van `run_analysis` is geen kernelgrens: een ontsnapping uit Python draait als dezelfde gebruiker als de server (#443)
- Reference values kunnen verouderen na dataverversing; voor de ijkwaarden maakt `scripts/ijkwaarden.py` dat zichtbaar

---

## Productiemonitoring

- **Health check:** `GET /health` retourneert `{"status":"ok"}`
- **Logging:** gestructureerde logging op INFO-niveau. Per tool-aanroep staan op INFO `GEHEUGEN` (toolnaam, geheugen van
  proces en datastore) en `REPRODUCEER` (toolnaam met alleen lengte en hash van de snippet, `tekst_kenmerk`). De
  argumenten (`TOOL CALL`), het resultaat (`TOOL RESULT`) en de snippet zelf staan alleen op DEBUG, want ze bevatten
  tekst uit de vraag (#475; `Agents.md`, "Logs: geen gebruikerstekst op INFO+")
- **Reproduceerbaarheid:** de Python-snippet van elke tool-aanroep staat in de chat en in de export, niet in het log op
  INFO
- **Eval resultaten:** uitvoer van evalruns komt lokaal in `eval_results/` (niet in git, zie `.gitignore`); de CI-job `eval:bronwaarheid` bewaart ze 90 dagen als artifact (#169)
- **Bron-ping:** de geplande CI-job `bron:ping` (schema op `main` met `BRON_PING=1`, ook met de hand via "Run pipeline") roept elke bron één keer aan door de toollaag; een rode geplande pipeline is het signaal (#627)
- **Tokengebruik:** per run (vraag, rapport) één regel `TOKENS` (INFO) met model, aantal modelaanroepen, invoer, uitvoer en gelezen en geschreven cache (#678). De regel draagt het verbindings-ID; `VERBINDING open` noemt bij dat ID het pseudoniem `gebruiker=` (een HMAC met `LOG_HASH_SECRET`; zonder dat geheim `-`, want een kale hash van een e-mailadres is terug te rekenen). Per modelaanroep precies één regel `MODELAANROEP` (INFO), zonder gebruikerstekst: model, uitkomst (`ok`, `gestopt` na de stopknop of het stopsignaal van de grens, `afgebroken_runlimiet` als de harde grens van de run (`RUN_TIMEOUT_S` plus de uitloop) of van het rapport (`GENEREER_TIMEOUT_S`) een vastzittende aanroep afbrak, `geannuleerd` bij een annulering van buitenaf zoals een gesloten WebSocket, reset of ander gesprek, of anders het fouttype), de seconden tot de provider antwoordde (`open`, inclusief wachten na een rate limit of time-out), tot de eerste chunk en tot het einde (`totaal`, bij een afbraak de duur tot de afbraak), en de uitvoertokens. Een veld dat niet bereikt werd, staat op `-`. Daarop kiest #800 `LITELLM_REQUEST_TIMEOUT`
- **Herkomstlog:** per gepubliceerd resultaat één regel `GEPUBLICEERD` (INFO) met soort, data-keys en versies; de selectiestappen op DEBUG (#169)
- **Metrics:** `GET /metrics` in het tekstformaat van Prometheus, per pod (#678); zie hieronder

### Metrics (`GET /metrics`, #678)

Het eindpunt is niet openbaar en staat niet in het OpenAPI-schema.

- **Zonder `METRICS_TOKEN`** bestaat het niet: 404, net als een onbekende route. Zo staat het op elke omgeving tot het
  token in het secret staat.
- **Met `METRICS_TOKEN`** (een geheim uit `onderwijsdata-chat-secrets`, `optional: true` in
  `manifests/<omgeving>/values.yaml`, nu op test) vraagt elk verzoek `Authorization: Bearer <token>`; zonder of met een
  fout token 401. De vergelijking is constant-time. De scraper van het platform krijgt hetzelfde token
  (`authorization.credentials` in een ServiceMonitor of `bearer_token_file` in een scrape-config).
- **Per pod, één proces:** de standaardregistry van `prometheus_client` zonder multiprocess-modus; de Dockerfile start
  één uvicorn-proces. De procesmetrics van de bibliotheek (`process_resident_memory_bytes`, `process_cpu_seconds_total`,
  `python_gc_*`) komen mee. Een herstart zet de tellers op nul; PromQL `rate()` en `increase()` vangen dat op.
- **Labels zijn begrensd:** het routesjabloon (`/api/conversations/{conv_id}`, nooit het pad), de methode (een onbekende
  wordt `ANDERS`), de statuscode, de modelnaam uit het aanbod en vaste woorden. Geen gebruikersnaam, pseudoniem,
  sleutel-ID of vraagtekst (`tests/test_metrics.py` toetst de labelsets).

| Metric | Soort | Labels | Wat |
|---|---|---|---|
| `edudata_http_requests_total` | counter | `method`, `route`, `status` | HTTP-verzoeken (geen WebSocket); `route="<geen route>"` als geen route paste |
| `edudata_http_request_duration_seconds` | histogram | `method`, `route` | Duur tot het antwoord klaar is (bij een gestreamd antwoord tot het einde) |
| `edudata_http_server_errors_total` | counter | `method`, `route` | Verzoeken met een 5xx, ook de 503 van `/ready` en een druk dashboard |
| `edudata_websockets_open` | gauge | | Open chatverbindingen op deze pod |
| `edudata_websockets_per_user_max` | gauge | | Het grootste aantal open verbindingen van één gebruiker, zonder te zeggen wie |
| `edudata_runs_running` | gauge | `pool` (`chat`, `dashboard`, `mcp`) | Lopende runs per wachtrij; `mcp` alleen met `MCP_API_KEYS` |
| `edudata_sandbox_running` | gauge | | Lopende sandboxprocessen van `run_analysis` |
| `edudata_concurrency_limit` | gauge | `counter` | De grens van elke teller hierboven (`websockets_total`, `websockets_per_user`, `chat`, `dashboard`, `mcp`, `sandbox`) |
| `edudata_model_calls_total` | counter | `model`, `outcome` | Modelaanroepen; `outcome` is die van `MODELAANROEP` (`ok`, `gestopt`, `geannuleerd`, `afgebroken_runlimiet`), een fouttype telt als `fout` |
| `edudata_model_call_errors_total` | counter | `model` | Mislukte modelaanroepen: `fout` en `afgebroken_runlimiet` |
| `edudata_model_call_duration_seconds` | histogram | `model` | Duur van een modelaanroep (`totaal` in `MODELAANROEP`) |
| `edudata_model_first_chunk_seconds` | histogram | `model` | Tijd tot de eerste chunk (`eerste_chunk`), per aanroep die er een kreeg |
| `edudata_model_tokens_total` | counter | `model`, `direction` (`input`, `output`) | Tokens per run, zoals `TOKENS` |
| `edudata_sandbox_runs_total` | counter | `outcome` (`ok`, `fout`, `timeout`, `gestopt`, `bezet`) | Scripts van `run_analysis` |
| `edudata_sandbox_timeouts_total` | counter | | Scripts die na de tijdslimiet (10 s) zijn afgebroken |
| `edudata_limiter_refusals_total` | counter | `limiter` | Geweigerd door een limiet: de rate limits (`login`, `bericht`, `feedback`, `feedback_algemeen`, `rapport_docx`, `mcp_ip`, `mcp_sleutel`) en de volle plaatsen (`runplaatsen_chat`, `runplaatsen_dashboard`, `mcp_plaatsen`, `sandbox`, `verbindingen`) |
| `edudata_limiter_db_fallback_total` | counter | `limiter` | Pogingen die een limiet in het geheugen van de pod telde omdat de database niet bereikbaar was (fail-open, `core/rate_limit.py`) |

### SLO's (voorstel)

Interne doelen om de metrics op te lezen, geen afspraak met gebruikers: publiek blijft de beschikbaarheid best effort
(ADR-011, [Operatie](operatie.md#beschikbaarheid)). De waarden zijn een startpunt; stel ze bij na een maand meten.

| SLO | Doel | Zo lees je het af |
|---|---|---|
| Beschikbaarheid | 99% van de HTTP-verzoeken zonder 5xx, over 30 dagen; daarnaast `up` van de scrape | `1 - sum(rate(edudata_http_server_errors_total{route!="/metrics"}[30d])) / sum(rate(edudata_http_requests_total{route!="/metrics"}[30d]))` |
| Tijd tot het eerste token | p95 onder 10 s, over een uur | `histogram_quantile(0.95, sum by (le) (rate(edudata_model_first_chunk_seconds_bucket[1h])))` |
| Foutpercentage model | onder 2% van de modelaanroepen, over een uur | `sum(rate(edudata_model_call_errors_total[1h])) / sum(rate(edudata_model_calls_total[1h]))` |

De tijd tot het eerste token geldt per modelaanroep, niet per vraag: een vraag met tools doet er meerdere, en de
gebruiker ziet eerder de stappen van de tools. Een pod die niet antwoordt, schrijft zelf geen 5xx; dan zegt `up == 0`
het, of de 502/503 van de ingress.

### Alertvoorstellen

Nog niet geïnstalleerd op het SDP-platform (#678). Als `PrometheusRule`, met `job="onderwijsdata-chat"` als de naam van
de scrape:

```yaml
groups:
  - name: onderwijsdata-chat
    rules:
      - alert: EdudataVeel5xx
        expr: |
          sum(rate(edudata_http_server_errors_total{route!="/metrics"}[10m]))
            / sum(rate(edudata_http_requests_total{route!="/metrics"}[10m])) > 0.05
        for: 10m
        annotations:
          summary: "Meer dan 5% van de HTTP-verzoeken eindigt in een 5xx"
      - alert: EdudataModelFouten
        expr: |
          sum(rate(edudata_model_call_errors_total[15m]))
            / sum(rate(edudata_model_calls_total[15m])) > 0.10
        for: 15m
        annotations:
          summary: "Meer dan 10% van de modelaanroepen mislukt (provider, sleutel of runlimiet)"
      - alert: EdudataLimietZonderDatabase
        expr: sum(increase(edudata_limiter_db_fallback_total[5m])) > 0
        annotations:
          summary: "Een limiet telt per pod: de database was niet bereikbaar (fail-open)"
      - alert: EdudataOpschoningMislukt
        # kube-state-metrics; de CronJob heet <release>-opschonen (charts/onderwijsdata-chat/templates/cronjob-opschonen.yaml).
        expr: increase(kube_job_status_failed{job_name=~".*-opschonen-.*"}[1d]) > 0
        annotations:
          summary: "De nachtelijke opschoning (persistence/opschonen.py) is mislukt: bewaartermijnen worden niet gehaald"
      - alert: EdudataPodWeg
        expr: up{job="onderwijsdata-chat"} == 0
        for: 5m
        annotations:
          summary: "De scrape van /metrics faalt: de pod antwoordt niet of het token klopt niet"
```

`bron:ping` draait in GitLab CI, niet in de pod, en staat dus niet in de metrics: het signaal is een rode geplande
pipeline. Zet daarvoor in GitLab de melding bij een mislukte pipeline aan (Settings > Integrations > Pipeline status
emails, "Notify only broken pipelines", branch `main`).
