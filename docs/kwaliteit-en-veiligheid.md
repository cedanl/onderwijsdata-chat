# Kwaliteit & veiligheid

De app meerdere lagen van kwaliteitscontrole en beveiliging om betrouwbare antwoorden te garanderen.

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

---

## Beveiligingsmaatregelen

### Analyse-sandbox

De `run_analysis`-tool voert arbitrary Python uit in een beveiligde omgeving:

- **Geblokkeerde patronen:** `import`, `exec`, `eval`, `os.`, `sys.`, `subprocess`, `open`, `breakpoint`
- **Beperkte builtins:** alleen veilige functies (`len`, `range`, `sorted`, `sum`, `round`, etc.)
- **Beschikbare bibliotheken:** pandas, numpy, math, plotly.express, plotly.graph_objects — geen netwerktoegang, geen bestands-I/O
- **Timeout:** 10 seconden via daemon thread

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
- HMAC-gehandtekende JWT tokens met 24-uur TTL
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
- `run_analysis` sandbox niet gestresstest
- Reference values kunnen verouderen na dataverversing
- Geen max-lengte op chat-berichten

---

## Productiemonitoring

- **Health check:** `GET /health` retourneert `{"status":"ok"}`
- **Logging:** gestructureerde logging op INFO-niveau, tool-calls gelogd met argumenten en executietijden
- **Reproduceerbaarheid:** bij elke tool-aanroep wordt een Python-snippet gelogd voor debugging
- **Eval resultaten:** tijdstempel-opslag in `eval_results/` voor langdurige kwaliteitsbewaking
