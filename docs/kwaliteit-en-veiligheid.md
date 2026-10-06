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

De `run_analysis`-tool voert door het model geschreven Python uit in het serverproces. Dat is **geen vertrouwensgrens** (#62):

- **Geblokkeerde patronen:** een regex-lijst (`import`, `exec`, `eval`, `os.`, `sys.`, `subprocess`, `open`, `breakpoint`). Een tekstpatroon, geen semantische controle: via objectattributen is het te omzeilen.
- **Beperkte builtins:** alleen `len`, `range`, `sorted`, `sum`, `round` en vergelijkbare functies.
- **Beschikbare bibliotheken:** pandas, numpy, math, plotly.express, plotly.graph_objects. De bestandsfuncties daarvan (`pd.read_csv`, `df.to_csv`, `np.load`) zijn niet geblokkeerd: een script kan bestanden lezen en schrijven waar het serverproces bij kan.
- **Timeout:** 10 seconden in een daemon-thread, best effort: code die in I/O blokkeert, wordt niet altijd gestopt.
- **AST-controle:** weigert een script dat geen data leest of zelf een reeks getallen intypt. Dat bewaakt de herkomst van getallen, niet de toegang.

Procesisolatie of getypeerde operaties in plaats van vrije scripts staat open in #62.

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
| LLM API | Exponential backoff (4 retries) | 2s, 4s, 8s, 16s vertraging bij rate limit errors |

### Input validatie

- `query_data` controleert of filterkolommen bestaan, operators geldig zijn (`eq`, `gte`, `lte`, `in`) en aggregatiefuncties correct zijn
- `search_catalog` filtert op geografisch niveau
- `dataset_details` geeft "not found" voor onbekende dataset-ID's
- Foutafhandeling: alle tool-exceptions worden gevangen en als vriendelijke foutmelding teruggegeven aan het LLM — nooit als raw stack trace naar de gebruiker

### HTTP beveiligingsheaders

- `Content-Security-Policy` — beperkte bronnen voor scripts/styles
- `X-Frame-Options: DENY` — geen iframe embed
- `Strict-Transport-Security` — HTTPS forceren
- `X-Content-Type-Options: nosniff` — MIME-type sniffing voorkomen
- `Referrer-Policy: strict-origin-when-cross-origin`

### Authenticatie

- Optionele wachtwoordauthenticatie via `CHAT_USERS`
- HMAC-ondertekende tokens (gebruikersnaam en vervaltijd, ondertekend met `CHAT_SECRET`) met 24-uur TTL
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
- `run_analysis` is niet geïsoleerd: bestands-I/O via pandas/numpy werkt en de patroonlijst is te omzeilen (#62)
- Reference values kunnen verouderen na dataverversing
- Geen max-lengte op chat-berichten

---

## Productiemonitoring

- **Health check:** `GET /health` retourneert `{"status":"ok"}`
- **Logging:** gestructureerde logging op INFO-niveau, tool-calls gelogd met argumenten en executietijden
- **Reproduceerbaarheid:** bij elke tool-aanroep wordt een Python-snippet gelogd voor debugging
- **Eval resultaten:** uitvoer van evalruns komt lokaal in `eval_results/` (niet in git, zie `.gitignore`); bewaar langdurige resultaten als CI-artifact
