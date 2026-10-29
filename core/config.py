"""Runtime-instellingen voor agent, tools en routes: model, limieten, feature-vlaggen.

Elke env-variabele wordt hier één keer gelezen; wie hem nodig heeft importeert
de constante. De root-config.py (klasse Config) gaat over het opstarten van de
server: logging, CORS, OIDC en de validatie daarvan, en leest het model hiervandaan.
Uitzondering: core/auth.py en persistence/db.py lezen hun eigen variabelen bij
import, omdat tests die modules met een andere omgeving herladen.
"""

import os

MODEL = os.getenv("MODEL", "anthropic/claude-sonnet-4-6")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "40960"))
# Analyses horen herhaalbaar te zijn: temperature 0 en een vaste seed (#46). Providers die een
# van beide niet kennen, laten hem vallen (drop_params in agent/models.py).
TEMPERATURE = float(os.getenv("TEMPERATURE", "0"))
SEED = int(os.getenv("SEED", "42"))
MAX_TOOL_ITERATIONS = int(os.getenv("MAX_TOOL_ITERATIONS", "25"))
CBS_ROW_LIMIT = int(os.getenv("CBS_ROW_LIMIT", "5000"))
RIO_PAGE_SIZE = int(os.getenv("RIO_PAGE_SIZE", "50"))
DUO_ROW_LIMIT = int(os.getenv("DUO_ROW_LIMIT", "500"))
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "40"))
# Maximale lengte van een nieuw chatbericht in tekens, na strip() (#481, SECURITY.md S7).
# De composer krijgt de echte waarde via /api/config (#501); frontend/src/constants.js MAX_MESSAGE_CHARS
# is alleen de terugvalwaarde en gelijk aan deze standaard.
MAX_MESSAGE_CHARS = int(os.getenv("MAX_MESSAGE_CHARS", "4000"))
# Tekencap op de hele aangeleverde historie (#500, SECURITY.md S15): zonder cap kon een
# handgemaakte client via de history-actie tot MAX_HISTORY beurten van willekeurige grootte
# naar het model sturen. 40 × 4000 is ruim voor echte gesprekken; daarboven vallen de
# oudste beurten af, zodat bestaande lange gesprekken blijven openen. Minimaal 1: een cap van
# 0 (of een negatieve waarde, of MAX_HISTORY=0 in de standaard) zou beurten tot lege tekst afkappen.
HISTORY_MAX_CHARS = max(1, int(os.getenv("HISTORY_MAX_CHARS", str(MAX_HISTORY * MAX_MESSAGE_CHARS))))
# Tijdsgrens per run (#90): na RUN_SLOW_S een wachtregel in de chat (#599), na RUN_TIMEOUT_S stopt de run.
# 20 s: na 45 s dacht de gebruiker al dat de app hing (UX-audit P3-5).
RUN_SLOW_S = float(os.getenv("RUN_SLOW_S", "20"))
RUN_TIMEOUT_S = float(os.getenv("RUN_TIMEOUT_S", "300"))
# Berichtlimiet op de chat (#444, SECURITY.md S5): zoveel vragen, verduidelijkingen, dashboards en rapporten per
# gebruiker (zonder login: per verbinding) per venster; daarboven een melding met de wachttijd. Een grens voor de
# LLM-kosten, niet voor gewoon gebruik: dertig in tien minuten is een vraag per twintig seconden.
CHAT_RATE_LIMIT = int(os.getenv("CHAT_RATE_LIMIT", "30"))
CHAT_RATE_WINDOW_S = int(os.getenv("CHAT_RATE_WINDOW_S", "600"))
# Wat er tegelijk mag op de pod (#688, core/gelijktijdig.py). Per gebruiker ruim: het gedeelde demo-account opent in
# een zaal veel vensters, en elke pagina met chat of dashboard is een eigen verbinding. Zonder login alleen het totaal.
MAX_WS_PER_USER = int(os.getenv("MAX_WS_PER_USER", "10"))
MAX_WS_TOTAL = int(os.getenv("MAX_WS_TOTAL", "100"))
# Runs die het model aanroepen (vraag, verduidelijking, dashboard, rapport, verversen); daarboven wachten, na
# RUN_QUEUE_TIMEOUT_S een melding dat het druk is.
MAX_CONCURRENT_RUNS = int(os.getenv("MAX_CONCURRENT_RUNS", "8"))
RUN_QUEUE_TIMEOUT_S = float(os.getenv("RUN_QUEUE_TIMEOUT_S", "60"))
# Gelijktijdige sandboxprocessen van run_analysis: elk laadt pandas en de data, dus het geheugen bepaalt dit.
MAX_SANDBOX_RUNS = int(os.getenv("MAX_SANDBOX_RUNS", "2"))
SANDBOX_QUEUE_TIMEOUT_S = float(os.getenv("SANDBOX_QUEUE_TIMEOUT_S", "20"))
# Grootste HTTP-verzoek en WebSocket-bericht (#682, core/verzoeklimiet.py en --ws-max-size in de Dockerfile). Gemeten
# op 23-10: het grootste gesprek 163 kB, het grootste werkboek 85 kB; het herstel van een gesprek gaat als één bericht.
MAX_REQUEST_BYTES = 4 * 1024 * 1024
# Bovengrens van de datastore in het geheugen (tools/store.py, #13): daarboven gaan de langst niet
# gebruikte tabellen eruit; een gesprek haalt ze zo nodig uit zijn recept terug (#472). De pod heeft
# 2 GiB (playground) tot 4 GiB (productie); de catalogus en de modellen delen dat geheugen.
STORE_MAX_MB = int(os.getenv("STORE_MAX_MB", "512"))
# Zoekacties per vraag: de code dwingt dit af en de systeemprompt noemt het (#52).
SEARCH_CATALOG_LIMIT = 3
# Wat het model van één toolresultaat ziet (agent/loop.py kapt daarboven af, #395). search_catalog blijft er
# zelf onder door hele treffers weg te laten met een melding, zodat het model geldige JSON leest (#358).
TOOL_RESULT_MAX_CHARS = int(os.getenv("TOOL_RESULT_MAX_CHARS", "12000"))
# Dashboardfunctie (pagina en /api/dashboard/*); stond eerder los in twee routes (#234). Standaard uit:
# de dashboardbouwer heeft een eigen chatclient die achterloopt op useChat (#765), dus alleen aan waar
# de omgeving hem bewust aanzet (manifests/<omgeving>/values.yaml).
DASHBOARDS_ENABLED = os.getenv("ENABLE_DASHBOARDS", "false").lower() == "true"
# Feedbackknop op rapporten en dashboards (#250); vragen staan in core/feedback.py.
FEEDBACK_ENABLED = os.getenv("ENABLE_FEEDBACK", "true").lower() != "false"
# Bewaartermijnen in dagen (#485, besluit 21-10-2026), voor de opschoning (persistence/opschonen.py):
# gesprekken met hun datarecepten en alle feedback 90 dagen na de laatste activiteit, rapporten en dashboards
# 365 dagen nadat ze voor het laatst zijn opgeslagen of geopend. Als tekst: de opschoning toetst ze zelf en
# verwijdert niets bij een ongeldige waarde of een termijn onder de 7 dagen; de app start er altijd mee.
BEWAARTERMIJN_GESPREKKEN_DAGEN = os.getenv("BEWAARTERMIJN_GESPREKKEN_DAGEN", "90")
BEWAARTERMIJN_RAPPORTEN_DAGEN = os.getenv("BEWAARTERMIJN_RAPPORTEN_DAGEN", "365")

# Willma AI-Hub (SURF) — optioneel. Zet WILLMA_API_KEY om via Willma te draaien.
# Zet MODEL naar bijv. "openai/Qwen2.5-Coder-7B-Instruct" om een specifiek Willma-model te kiezen.
WILLMA_API_KEY = os.getenv("WILLMA_API_KEY")
WILLMA_BASE_URL = os.getenv("WILLMA_BASE_URL", "")

# Kommagescheiden lijst van LiteLLM model-IDs voor de model-picker in de UI.
# Niet ingesteld → geen model-picker, de app gebruikt altijd MODEL.
_AVAILABLE_MODELS_RAW = os.getenv("AVAILABLE_MODELS")

# Per-gebruiker model-picker: "user1:model_a,model_b;user2:model_c"
# Gebruikers niet in deze lijst krijgen de globale AVAILABLE_MODELS.
_USER_MODELS_RAW = os.getenv("USER_MODELS", "")

# Provider prefix → API key environment variable mapping. Centraal punt voor drift-preventie.
# Zie #53: één plek waar alle provider→key mappings staan.
_PROVIDER_API_KEYS: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "azure_ai": "AZURE_AI_API_KEY",
    "azure": "AZURE_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "willma": "WILLMA_API_KEY",
    "ollama": None,  # Ollama doesn't require API key
    "ollama_chat": None,
}


def get_required_api_key_env_var(model_id: str) -> str | None:
    """Get the environment variable name for a model's required API key.

    Extracts the provider prefix (part before first '/') and looks up the
    corresponding environment variable. Returns None if provider is unknown
    or doesn't require a key (ollama).

    Examples:
        'anthropic/claude-opus' → 'ANTHROPIC_API_KEY'
        'openai/gpt-4o' → 'OPENAI_API_KEY'
        'ollama/mistral' → None
        'unknown-provider/model' → None (unknown provider handled gracefully)
    """
    if not model_id:
        return None
    provider = model_id.split("/")[0].lower()
    return _PROVIDER_API_KEYS.get(provider)


def get_all_api_key_env_vars() -> list[str]:
    """Get all environment variable names that might contain API keys.

    Used to check if ANY API key is configured (for startup checks).
    Filters out None values (providers that don't need keys).
    """
    return [k for k in _PROVIDER_API_KEYS.values() if k is not None]


# Wie het model draait: de modelkiezer noemt die partij in een bijschrift "Via …" (#496, F10).
_ANTHROPIC = "Anthropic"
_FOUNDRY = "Microsoft Azure AI Foundry"
_OPENAI = "OpenAI"
_WILLMA = "SURF Willma"
_PROVIDER_BY_PREFIX: dict[str, str] = {"anthropic": _ANTHROPIC, "azure_ai": _FOUNDRY, "openai": _OPENAI}

# (naam, omschrijving, icoon, provider) voor bekende modellen. Naam en omschrijving zijn gewone taal
# voor de gebruiker; de provider staat alleen in het vierde veld. Een onbekend model heet naar het deel
# na de laatste '/'.
_KNOWN_NAMES: dict[str, tuple[str, str, str, str]] = {
    "anthropic/claude-haiku-4-5-20251001": ("Haiku", "snel", "zap", _ANTHROPIC),
    "anthropic/claude-sonnet-4-6": ("Sonnet", "voor de meeste vragen", "sparkles", _ANTHROPIC),
    "anthropic/claude-opus-4-6": ("Opus 4.6", "grondiger, wat trager", "brain", _ANTHROPIC),
    "anthropic/claude-opus-4-7": ("Opus 4.7", "grondiger, wat trager", "brain", _ANTHROPIC),
    "anthropic/claude-opus-4-8": ("Opus 4.8", "grondigst", "brain", _ANTHROPIC),
    "azure_ai/claude-sonnet-4-6": ("Sonnet", "voor de meeste vragen", "sparkles", _FOUNDRY),
    "azure_ai/claude-sonnet-5-5": ("Sonnet 5.5", "voor de meeste vragen", "sparkles", _FOUNDRY),
    "azure_ai/claude-opus-4-6": ("Opus 4.6", "grondiger, wat trager", "brain", _FOUNDRY),
    "azure_ai/claude-opus-5-5": ("Opus 5.5", "grondiger, wat trager", "brain", _FOUNDRY),
    "azure_ai/claude-haiku-4-5": ("Haiku", "snel", "zap", _FOUNDRY),
    "openai/gpt-4o-mini": ("GPT-4o mini", "snel", "zap", _OPENAI),
    "openai/gpt-4o": ("GPT-4o", "voor de meeste vragen", "sparkles", _OPENAI),
    "openai/gpt-5": ("GPT-5", "grondigst", "brain", _OPENAI),
    "openai/openai/gpt-oss-120b": ("GPT-OSS 120B", "goed in het ophalen van data", "cpu", _WILLMA),
    "openai/Qwen/Qwen2.5-VL-32B-Instruct-AWQ": ("Qwen 2.5 VL 32B", "ook voor afbeeldingen", "cpu", _WILLMA),
    "openai/Qwen/Qwen2.5-Coder-32B-Instruct-AWQ": ("Qwen 2.5 Coder 32B", "gericht op code", "cpu", _WILLMA),
}


def model_provider(model_id: str) -> str:
    """Wie het model draait, zoals agent/models.py:litellm_kwargs de aanroep routeert; "" als dat onbekend is.

    Met WILLMA_API_KEY gaat elk openai/-model naar Willma, ook een bekend OpenAI-model.
    """
    if WILLMA_API_KEY and model_id.startswith("openai/"):
        return _WILLMA
    if model_id in _KNOWN_NAMES:
        return _KNOWN_NAMES[model_id][3]
    return _PROVIDER_BY_PREFIX.get(model_id.split("/")[0].lower(), "")


def model_naam(model_id: str) -> str:
    """De naam van het model voor de gebruiker, zonder provider: "Claude Sonnet 5.5" voor azure_ai/claude-sonnet-5-5.

    Een bekend Claude-model krijgt het merk erbij (de picker toont alleen "Sonnet 5.5" onder een kop); een
    onbekend model heet naar het deel na de laatste '/', zoals in de picker."""
    if model_id not in _KNOWN_NAMES:
        return model_id.split("/")[-1]
    naam = _KNOWN_NAMES[model_id][0]
    return f"Claude {naam}" if "/claude-" in model_id else naam


def _parse_user_models() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    if not _USER_MODELS_RAW.strip():
        return result
    for entry in _USER_MODELS_RAW.split(";"):
        entry = entry.strip()
        if ":" not in entry:
            continue
        username, _, models_str = entry.partition(":")
        models = [m.strip() for m in models_str.split(",") if m.strip()]
        if username.strip() and models:
            result[username.strip()] = models
    return result


_USER_MODELS: dict[str, list[str]] = _parse_user_models()


def _model_entry(model_id: str) -> tuple[str, str, str, str, str]:
    name, desc, icon, _provider = _KNOWN_NAMES.get(model_id, (model_id.split("/")[-1], "", "cpu", ""))
    return model_id, name, desc, icon, model_provider(model_id)


def _models_from_ids(model_ids: list[str]) -> list[tuple[str, str, str, str, str]]:
    return [_model_entry(mid) for mid in model_ids]


def get_available_models() -> list[tuple[str, str, str, str, str]] | None:
    """Return list of (model_id, name, description, icon, provider), or None if no picker."""
    if not _AVAILABLE_MODELS_RAW:
        return None
    result = _models_from_ids([m.strip() for m in _AVAILABLE_MODELS_RAW.split(",") if m.strip()])
    return result or None


def get_available_models_for_user(username: str | None) -> list[tuple[str, str, str, str, str]] | None:
    """Return per-user models if configured, else fall back to global AVAILABLE_MODELS."""
    if username and username in _USER_MODELS:
        return _models_from_ids(_USER_MODELS[username]) or None
    return get_available_models()


def toegestaan_model(username: str | None, gevraagd: object) -> str:
    """Het model voor een beurt: het gevraagde als het in het aanbod van deze gebruiker staat, anders ``MODEL``.

    De picker in de frontend toont alleen het aanbod, maar een eigen WebSocket-client stuurt elke naam
    mee (#755). Zonder aanbod (geen picker) is alleen ``MODEL`` toegestaan.
    """
    aanbod = get_available_models_for_user(username)
    if isinstance(gevraagd, str) and aanbod and gevraagd in {model_id for model_id, *_ in aanbod}:
        return gevraagd
    return MODEL
