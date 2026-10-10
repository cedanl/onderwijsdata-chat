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
| `MAX_MESSAGE_CHARS` | `4000` | Maximum aantal tekens per nieuw chatbericht (na het weghalen van witruimte aan begin en eind). Langere berichten weigert de server met een foutmelding; de invoerbalk telt mee vanaf 80%. De invoerbalk krijgt deze waarde via `/api/config` en volgt dus een gewijzigde instelling |
| `RUN_SLOW_S` | `20` | Seconden tot de melding "dit duurt langer dan normaal" |
| `RUN_TIMEOUT_S` | `300` | Seconden tot een vraag wordt gestopt |
| `CBS_ROW_LIMIT` | `5000` | Maximum rijen uit CBS-datasets |
| `RIO_PAGE_SIZE` | `50` | Maximum records per RIO-aanroep |
| `DUO_ROW_LIMIT` | `500` | Maximum rijen uit DUO-datasets |
| `CORS_ORIGINS` | *(leeg)* | Komma-gescheiden lijst van origins die de API cross-origin mogen aanroepen. Leeg is genoeg zolang de frontend via dezelfde origin draait; `*` wordt bij het opstarten geweigerd |
| `DATABASE_PATH` | `app.db` | Pad voor het SQLite-databasebestand (alleen gebruikt zonder `POSTGRES_URI`) |
| `POSTGRES_URI` | *(niet ingesteld)* | PostgreSQL-URI (`postgresql://…`). Indien ingesteld slaat de app gesprekken en rapporten op in PostgreSQL in plaats van SQLite — zie [Professioneel hosten](../hosting.md#1-database-postgresql) |
| `ENABLE_DASHBOARDS` | `true` | Zet op `false` om de dashboardfunctie (pagina en `/api/dashboard/*`) uit te schakelen |
| `ENABLE_FEEDBACK` | `true` | Zet op `false` om de feedbackknop op rapporten en dashboards en de 👍/👎 per chatantwoord (en `/api/feedback*`, `/api/answer-feedback`) uit te schakelen. De vragen staan in `core/feedback.py`; antwoorden komen in de tabel `feedback`. Oordelen per antwoord komen met de tool-trace in `answer_feedback`; `python -m scripts.antwoordfeedback` zet ze als markdown op een rij |
| `LOG_LEVEL` | `INFO` | Loggingniveau: `DEBUG`, `INFO`, `WARNING` of `ERROR` |

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
| `CHAT_SECRET` | *(per herstart gegenereerd)* | HMAC-secret voor sessiebeheer. Stel in voor stabiele tokens die herstarts overleven. |
| `CHAT_USERS` | *(niet ingesteld)* | Wachtwoord-authenticatie: `user:pass,user2:pass2`. Vereist dat `CHAT_SECRET` is ingesteld. |
| `SESSION_TTL_HOURS` | `8` | Geldigheid van een token in uren (decimaal mag, bv. `0.5`). Bij wachtwoord-login (geen verversing) moet de gebruiker na deze tijd opnieuw inloggen. |
| `SESSION_MAX_HOURS` | `24` | Maximale sessieduur in uren vanaf het inloggen: verversen (SRAM) geeft nooit een token dat later verloopt. |

Een ongeldige of niet-positieve waarde voor `SESSION_TTL_HOURS` of `SESSION_MAX_HOURS` laat de app niet starten. Uitloggen trekt het token ook server-side in (tabel `revoked_tokens`).

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
