# Configuratie

Alle instellingen worden beheerd via het `.env` bestand. Kopieer `.env.example` naar `.env` en pas de waarden aan.

## Verplichte instellingen

| Variabele | Beschrijving |
|-----------|--------------|
| `MODEL` | Model in LiteLLM-formaat: `provider/model-naam` — zie [Providers & modellen](providers.md) |
| API key | Afhankelijk van de provider: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc. |

Minimale configuratie voor Anthropic:

```dotenv
MODEL=anthropic/claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Optionele instellingen

| Variabele | Standaard | Beschrijving |
|-----------|-----------|--------------|
| `AVAILABLE_MODELS` | *(niet ingesteld)* | Kommagescheiden lijst van modellen in de model-picker — zie [Model-picker](#model-picker) |
| `USER_MODELS` | *(niet ingesteld)* | Per-gebruiker model-picker — zie [Per-gebruiker model-picker](#per-gebruiker-model-picker) |
| `MAX_TOKENS` | `40960` | Maximum tokens per LLM-aanroep |
| `TEMPERATURE` | `0` | Sampling-temperatuur van het model; 0 voor herhaalbare analyses |
| `SEED` | `42` | Vaste seed voor providers die dat ondersteunen; de rest negeert hem |
| `MAX_TOOL_ITERATIONS` | `25` | Maximum tool-aanroepen per vraag |
| `MAX_HISTORY` | `40` | Maximum aantal berichten in gespreksgeschiedenis |
| `CHAT_RATE_LIMIT` | `30` | Verzoeken die het model kosten (vraag, verduidelijking, dashboard, rapport) per gebruiker per venster; zonder login per verbinding. Daarboven een melding met de wachttijd (#444) |
| `CHAT_RATE_WINDOW_S` | `600` | Het venster van `CHAT_RATE_LIMIT` in seconden |
| `MAX_WS_PER_USER` | `10` | Open chatverbindingen per ingelogde gebruiker (elk venster met chat of dashboard is er een). Daarboven sluit de server de nieuwe verbinding met code 1013 en een melding. Ruim, omdat een gedeeld demo-account in een zaal veel vensters opent; zonder login telt alleen het totaal (#688) |
| `MAX_WS_TOTAL` | `100` | Open chatverbindingen op de pod samen (#688) |
| `MAX_CONCURRENT_RUNS` | `8` | Runs die tegelijk het model aanroepen (vraag, verduidelijking, dashboard, rapport, verversen). Een volgende wacht op een plaats (#688) |
| `RUN_QUEUE_TIMEOUT_S` | `60` | Seconden dat een run op een plaats wacht; daarna de melding dat het druk is, en geen run |
| `MAX_SANDBOX_RUNS` | `2` | Gelijktijdige kindprocessen van `run_analysis`; elk laadt pandas en de data, dus het geheugen van de pod bepaalt dit (#688) |
| `SANDBOX_QUEUE_TIMEOUT_S` | `20` | Seconden dat een analyse op een vrij proces wacht; daarna krijgt het model de melding dat de analyseomgeving bezet is |
| `MAX_MESSAGE_CHARS` | `4000` | Maximum aantal tekens per nieuw chatbericht (na het weghalen van witruimte aan begin en eind). Langere berichten weigert de server met een foutmelding; de invoerbalk telt mee vanaf 80%. De invoerbalk krijgt deze waarde via `/api/config` en volgt dus een gewijzigde instelling |
| `HISTORY_MAX_CHARS` | `MAX_HISTORY × MAX_MESSAGE_CHARS` (160000) | Maximum aantal tekens van de hele aangeleverde gespreksgeschiedenis samen. Daarboven vallen de oudste beurten af, zodat lange gesprekken blijven openen; de historie begint daarna altijd met een gebruikersbeurt. Minimaal 1: een lagere waarde wordt 1 |
| `RUN_SLOW_S` | `20` | Seconden tot de chat onder de voortgang zegt dat het even kan duren |
| `RUN_TIMEOUT_S` | `300` | Seconden tot een vraag wordt gestopt |
| `CBS_ROW_LIMIT` | `5000` | Maximum rijen uit CBS-datasets |
| `RIO_PAGE_SIZE` | `50` | Maximum records per RIO-aanroep |
| `DUO_ROW_LIMIT` | `500` | Maximum rijen uit DUO-datasets |
| `CORS_ORIGINS` | *(leeg)* | Komma-gescheiden lijst van origins die de API cross-origin mogen aanroepen. Leeg is genoeg zolang de frontend via dezelfde origin draait. Origins worden exact vergeleken, zonder patronen: een origin met ergens een `*`, ook `https://*.nl`, wordt bij het opstarten geweigerd |
| `STORE_MAX_MB` | `512` | Bovengrens van de datastore in het geheugen (#13): daarboven gaan de langst niet gebruikte tabellen eruit; een gesprek haalt ze uit zijn recept terug. Houd dit onder het geheugen van de pod |
| `DATABASE_PATH` | `onderwijsdata.db` | Pad voor het SQLite-databasebestand (alleen gebruikt zonder `POSTGRES_URI`) |
| `POSTGRES_URI` | *(niet ingesteld)* | PostgreSQL-URI (`postgresql://…`). Indien ingesteld slaat de app gesprekken en rapporten op in PostgreSQL in plaats van SQLite — zie [Professioneel hosten](../hosting.md#1-database-postgresql) |
| `ENABLE_DASHBOARDS` | `true` | Zet op `false` om de dashboardfunctie (pagina en `/api/dashboard/*`) uit te schakelen |
| `ENABLE_FEEDBACK` | `true` | Zet op `false` om de feedbackknop op rapporten en dashboards, de 👍/👎 per chatantwoord en de link Feedback (en `/api/feedback*`, `/api/answer-feedback`) uit te schakelen. De vragen staan in `core/feedback.py`; antwoorden komen in de tabel `feedback`. Oordelen per antwoord komen met de tool-trace in `answer_feedback`; `python -m scripts.antwoordfeedback` zet ze als markdown op een rij. Na het verwijderen van een gesprek blijven ze staan zonder gebruikersnaam en gesprek-id (#476). Ook de link Feedback (`/api/feedback/algemeen`, #600) hangt eraan: berichten komen in `algemene_feedback`, `python -m scripts.algemene_feedback` zet ze op een rij |
| `APP_ENV` | `local` | De omgeving: `local`, `development`, `test`, `playground` of `production`; `manifests/<omgeving>/values.yaml` zet hem. Buiten `local` schrijft de app JSON-logs; op `playground` en `production` is er geen API-documentatie (`/api/docs`, `/redoc`, `/api/openapi.json`). Een andere waarde laat de app niet starten (#676) |
| `LOG_LEVEL` | `INFO` | Loggingniveau: `DEBUG`, `INFO`, `WARNING` of `ERROR`. **Let op:** op `DEBUG` komt de letterlijke vraag- en antwoordtekst — en dus eventuele persoonsgegevens — in het log en de logaggregatie terecht (op `INFO` alleen lengte en hash). Ook fouttekst en de traceback van een interne fout staan alleen op `DEBUG` in het log; op `INFO` alleen het fout-ID, het type en een kenmerk (#502). Niet gebruiken op test of productie met echte gebruikers, en houd rekening met de bewaartermijn van de logaggregatie |
| `LOG_HASH_SECRET` | *(niet ingesteld)* | Geheim voor de hash in logregels (`len=… hash=…`, #475): met geheim een HMAC, zodat wie het log heeft geen geraden vraag tegen de hash kan controleren (#502). Via SOPS/Flux, nooit in de repo; zonder geheim een kale SHA-256 |

---

## Model-picker

De model-picker verschijnt alleen als `AVAILABLE_MODELS` is ingesteld. Zonder deze instelling gebruikt de app altijd het `MODEL` uit `.env` — geen picker, geen keuze.

```dotenv
AVAILABLE_MODELS=azure_ai/claude-sonnet-4-6,azure_ai/claude-haiku-4-5,azure_ai/gpt-4o
MODEL=azure_ai/claude-sonnet-4-6
```

`MODEL` bepaalt welk model standaard geselecteerd is in de picker. Zet dit op één van de modellen in `AVAILABLE_MODELS`.

Modellen van verschillende providers kunnen gecombineerd worden — LiteLLM leest per provider automatisch de juiste API keys:

```dotenv
AVAILABLE_MODELS=anthropic/claude-sonnet-4-6,openai/gpt-4o,ollama_chat/llama3.1:8b,deepseek/deepseek-chat
```

!!! warning "Zet altijd alle benodigde API keys"
    Elk model in `AVAILABLE_MODELS` moet via de bijbehorende omgevingsvariabele bereikbaar zijn. Een model in de picker zonder werkende API key geeft een foutmelding bij gebruik.

---

## Per-gebruiker model-picker

Met `USER_MODELS` kun je per gebruiker een apart modelaanbod configureren. Gebruikers die niet in de lijst staan, krijgen de globale `AVAILABLE_MODELS`.

```dotenv
USER_MODELS=alice:anthropic/claude-sonnet-4-6,anthropic/claude-haiku-4-5;bob:openai/gpt-4o
```

Formaat: `gebruiker:model1,model2;gebruiker2:model3`. Vereist dat `CHAT_USERS` is ingesteld voor authenticatie.

---

## Chatgeschiedenis & authenticatie

| Variabele | Standaard | Beschrijving |
|-----------|-----------|--------------|
| `CHAT_SECRET` | *(niet ingesteld)* | HMAC-secret voor de tokens. Verplicht zodra `CHAT_USERS` of `OIDC_PROVIDER` is ingesteld: zonder start de app dan niet (`core/auth.py`). Zonder login gebruikt de app een vaste ontwikkelsleutel |
| `CHAT_USERS` | *(niet ingesteld)* | Wachtwoord-authenticatie: `user:pass,user2:pass2`. Vereist dat `CHAT_SECRET` is ingesteld. |
| `SESSION_TTL_HOURS` | `8` | Geldigheid van een token in uren (decimaal mag, bv. `0.5`). Bij wachtwoord-login (geen verversing) moet de gebruiker na deze tijd opnieuw inloggen. |
| `SESSION_MAX_HOURS` | `24` | Maximale sessieduur in uren vanaf het inloggen: verversen (SRAM) geeft nooit een token dat later verloopt. |

Een ongeldige of niet-positieve waarde voor `SESSION_TTL_HOURS` of `SESSION_MAX_HOURS` laat de app niet starten. Uitloggen trekt het token ook server-side in (tabel `revoked_tokens`).

### Bewaartermijn en opschoning

| Variabele | Standaard | Beschrijving |
|-----------|-----------|--------------|
| `BEWAARTERMIJN_GESPREKKEN_DAGEN` | `90` | Dagen na de laatste activiteit waarna een gesprek (met zijn datarecepten) en feedback (`answer_feedback` met de `trace`, `feedback`, `algemene_feedback`) worden verwijderd. Feedback per antwoord blijft zolang het gesprek bestaat. |
| `BEWAARTERMIJN_RAPPORTEN_DAGEN` | `365` | Dagen nadat een rapport of dashboard voor het laatst is opgeslagen of geopend waarna het wordt verwijderd. |

De opschoning draait als `python -m persistence.opschonen` (met `--droog`: alleen tellen), op SDP als CronJob uit de Helm-chart (`opschonen.enabled`, aan op test en playground). Een termijn die geen geheel getal is of korter dan 7 dagen verwijdert niets (exitcode 2); een databasefout rolt alles terug (exitcode 1). De app zelf start altijd, ook met een ongeldige termijn. Zie `docs/privacy.md` (#485).

### SURF SRAM-login (OIDC)

SRAM-login is actief als `OIDC_PROVIDER` is ingesteld én de discovery-URL, client-gegevens en `SERVER_URL` aanwezig zijn (`auth/oidc.py`). Ook hiervoor moet `CHAT_SECRET` ingesteld zijn.

| Variabele | Standaard | Beschrijving |
|-----------|-----------|--------------|
| `OIDC_PROVIDER` | *(niet ingesteld)* | Naam van de provider (bijv. `sram`); zet OIDC-login aan |
| `OIDC_DISCOVERY_URL` | *(niet ingesteld)* | OpenID-discovery-URL van de provider (`…/.well-known/openid-configuration`) |
| `OIDC_CLIENT_ID` | *(niet ingesteld)* | Client-ID van de geregistreerde applicatie |
| `OIDC_CLIENT_SECRET` | *(niet ingesteld)* | Client-secret; hoort in een (SOPS-versleutelde) secret, nooit in de repo |
| `SERVER_URL` | *(niet ingesteld)* | Publieke basis-URL van de app, bijv. `https://onderwijsdata-chat.test.sdp.surf.nl` |
| `SERVER_REDIRECT` | `/api/auth/oidc/callback` | Callback-pad dat bij de provider als redirect-URI is geregistreerd |

Endpoints: zie [API Referentie → Authenticatie](../api.md).

!!! info "Authenticatie is optioneel"
    Zonder `CHAT_USERS` en zonder OIDC werkt de app zonder login. Gesprekken worden dan wel bewaard, maar allemaal onder één gedeelde gebruiker (`gast`).

---

## SURF Willma AI-Hub

Willma is de AI-Hub van SURF voor het Nederlandse onderwijs. Om via Willma te draaien:

```dotenv
MODEL=openai/<model-naam>
WILLMA_API_KEY=<jouw-willma-key>
WILLMA_BASE_URL=https://willma.surf.nl/api/v0
```

De beschikbare modelnamen haal je op bij Willma zelf:

```bash
curl -H "X-API-KEY: $WILLMA_API_KEY" "$WILLMA_BASE_URL/models"
```

!!! note "Hoe werkt dit in de code?"
    Wanneer `WILLMA_API_KEY` is ingesteld, worden `api_base`, `api_key` en een `X-API-KEY` header automatisch meegegeven aan elke LiteLLM-aanroep (zie `agent/models.py`). Voor alle andere providers regelt LiteLLM de authenticatie op basis van standaard omgevingsvariabelen.

---

Zie [Providers & modellen](providers.md) voor een overzicht van alle ondersteunde providers met voorbeeldconfiguraties.
