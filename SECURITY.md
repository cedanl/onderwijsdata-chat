# Security bevindingen

Overzicht van bekende en mogelijke beveiligingsproblemen. Gebaseerd op de quickscan van Alan Berg (30-06-2026) en aanvullende code-review. Op 09-10-2026 nagelopen tegen de code op `main` (#484).

---

## Status overzicht

| # | Bevinding | Ernst | Status |
|---|---|---|---|
| S1 | HTML-injectie in geëxporteerde rapporten | Hoog | ✅ Opgelost (escaping in de frontend); ongebruikte dependency `nh3` opruimen — nog geen issue |
| S2 | Lodash kwetsbare versie op loginpagina | Hoog | ✅ Opgelost (Chainlit verwijderd) |
| S3 | Ontbrekende HTTP security headers | Gemiddeld | ✅ Opgelost (middleware); CSP-restpunten in S13 |
| S4 | Foutmeldingen lekken interne exceptie-tekst | Gemiddeld | ⚠️ Gedeeltelijk — model-/API-fouten tonen nog de exceptietekst; nog geen issue |
| S5 | Geen rate limiting op login of chat | Gemiddeld | ⚠️ Gedeeltelijk — login beperkt, chat niet (#444) |
| S6 | JWT-token in query parameter (WebSocket) | Laag–Gemiddeld | ✅ Opgelost (`bearer`-subprotocol, #103) |
| S7 | Geen maximale inputlengte op chatberichten | Laag | ✅ Opgelost voor nieuwe invoer (`MAX_MESSAGE_CHARS`); `history` valt erbuiten — zie S7 en S15 (#500) |
| S8 | CORS staat op `*` als env var ontbreekt | Gemiddeld | ✅ Opgelost (standaard dicht, `*` geweigerd, #421) |
| S9 | JWT opgeslagen in localStorage | Laag | ℹ️ Geaccepteerd — zie S9; CSP-voorbehoud in S13 (#486) |
| S10 | Sessieduur 24 uur, niet instelbaar | Laag | ❌ Open (#479) |
| S11 | Tool-enumeratie via LLM | Laag | ℹ️ By design |
| S12 | Dependency-kwetsbaarheden | Variabel | ⚠️ Te verifiëren — nog geen issue |
| S13 | CSP staat `'unsafe-inline'` en twee CDN-hosts toe | Laag–Gemiddeld | ❌ Open (#486) |
| S14 | Token blijft na uitloggen geldig | Gemiddeld | ❌ Open (#479) |
| S15 | `history`-actie omzeilt de invoerlimiet | Laag | ❌ Open (#500) |
| S16 | Geen privacy-informatie bij opslag van gesprekken | Gemiddeld | ❌ Open (#477) |

---

## Details

### S1 — HTML-injectie in rapporten ✅ Opgelost

**Aangetroffen in:** quickscan A1  
**Was:** `md.markdown(llm_output)` injecteerde raw `<script>` tags in geëxporteerde HTML-bestanden.  
**Nu:** de server-side export (`export/`) bestaat niet meer. Rapporten en dashboards worden in de frontend opgebouwd door `buildReportHtml` (`frontend/src/reportHtml.js`) en `buildDashboardHtml` (`frontend/src/dashboardHtml.js`). Tekst uit het model gaat door `escapeHtml`; de figure-JSON in het inline script gaat door `scriptSafe` (#474); de dashboard-toelichting wordt met `react-markdown` gerenderd. Tests: `frontend/src/__tests__/reportHtml.test.js` en `frontend/src/__tests__/dashboardHtml.test.js`.  
**Restpunt:** `nh3` staat nog als dependency in `pyproject.toml`, maar wordt nergens geïmporteerd. Opruimen; nog geen issue.

---

### S2 — Kwetsbare lodash ✅ Opgelost

**Aangetroffen in:** quickscan A2  
**Was:** lodash 4.17.21 op de Chainlit loginpagina (CVE-2026-2950, CVE-2025-13465, CVE-2026-4800).  
**Fix:** Chainlit verwijderd; eigen React-frontend gebruikt lodash niet.

---

### S3 — Ontbrekende HTTP security headers ✅ Opgelost

**Aangetroffen in:** ZAP-scan (16 alerts waaronder CSP, X-Frame-Options, HSTS, X-Content-Type-Options)  
**Fix:** middleware in `server.py` zet:
- `Content-Security-Policy` — beperkt script/style/connect bronnen (restpunten: zie S13)
- `X-Frame-Options: DENY` en CSP `frame-ancestors 'none'` — voorkomt clickjacking
- `Strict-Transport-Security` — dwingt HTTPS af
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Server: ""` — verbergt serverversie

---

### S4 — Foutmeldingen lekken interne tekst ⚠️ Gedeeltelijk

**Locatie:** `core/errors.py` — `friendly_error()`  
**Opgelost (#404):** een interne fout (een fout in de eigen code) komt niet meer als exceptietekst bij de gebruiker. `log_interne_fout()` logt de exceptie onder een kort fout-ID; de gebruiker ziet een vaste melding met dat ID.  
**Restpunt:** een model- of API-fout (`modelafhankelijk()`: `openai.OpenAIError` en subklassen, `litellm.BudgetExceededError`, `TimeoutError`) waarvoor geen vaste tekst in `_FRIENDLY_ERRORS` staat, gaat nog als `f"❌ {exc}"` naar de browser. Dat geldt ook voor `litellm.BadRequestError`. De inhoud van zo'n tekst bepaalt de app niet zelf; hij kan details over provider of model bevatten. Nog geen issue.

---

### S5 — Rate limiting op login en chat ⚠️ Gedeeltelijk

**Login (opgelost):** `POST /api/auth/login` in `routes/auth.py` gebruikt `_login_limiter = RateLimiter(max_attempts=5, window_seconds=60)`: maximaal 5 pogingen per minuut per `request.client.host`. Daarboven volgt `429` met een `Retry-After`-header. `RateLimiter` (`core/rate_limit.py`) houdt de pogingen in het geheugen bij, per proces.  
**Feedback:** `routes/feedback.py` heeft een eigen limiter (3 per 600 seconden).  
**Chat (open):** de WebSocket `/api/chat` heeft geen limiet op het aantal berichten per verbinding of per gebruiker (LLM-kosten). Vervolg in #444. De maximale berichtlengte staat los daarvan, zie S7.  
**Te verifiëren:** de sleutel is `request.client.host`. De `Dockerfile` start uvicorn zonder `--forwarded-allow-ips` en de manifests zetten `FORWARDED_ALLOW_IPS` niet. Of de limiet achter de ingress per gebruiker of per proxy-adres telt, is niet nagegaan. Nog geen issue.

---

### S6 — JWT-token zichtbaar in query parameter ✅ Opgelost

**Was:** de WebSocket kreeg het token als query-parameter in de URL mee, en die belandt in proxy- en serverlogs.  
**Fix (#103, commit `2e7dbb0`):** de browser geeft het token mee als subprotocol (`["bearer", token]`). `routes/chat.py` leest de header `Sec-WebSocket-Protocol` met `token_uit_protocol()` uit `core/auth.py` en bevestigt het subprotocol `WS_SUBPROTOCOL` (`bearer`). De server neemt geen token uit de query-string meer aan. Test: `tests/test_token_niet_in_url.py`.

---

### S7 — Geen maximale inputlengte op chatberichten ✅ Opgelost voor nieuwe invoer

**Locatie:** `routes/chat.py` — de WebSocket-acties `message` en `clarification_choice`  
**Probleem:** Een gebruiker kon een bericht van willekeurige lengte sturen. Een extreem lang bericht (bijv. 500k tokens) leidt tot hoge LLM-kosten en trage respons.  
**Fix (#481):** `MAX_MESSAGE_CHARS` (env, standaard 4000 tekens, geteld na `strip()`). De server weigert een langer bericht of een langere verduidelijkingskeuze met een foutmelding die het maximum en de verstuurde lengte noemt, zonder de inhoud te herhalen; er start geen LLM-aanroep. De invoerbalk heeft `maxLength`, toont vanaf 80% een teller en verstuurt niets boven de grens. Opgeslagen gesprekken (`history`) vallen buiten de grens, zodat een oud gesprek altijd te heropenen is. Let op: daardoor neemt de actie `history` nog steeds tot `MAX_HISTORY` (40) door de client aangeleverde beurten van willekeurige lengte aan, die bij de volgende vraag naar het model gaan; een aangepaste client kan zo de grens omzeilen. Rate limiting (#444) begrenst de grootte van die beurten niet; het vervolg staat in #500 (zie S15).

---

### S8 — CORS staat standaard op `*` ✅ Opgelost

**Was:** de CORS-origins vielen terug op `*` als `CORS_ORIGINS` niet was ingesteld.  
**Fix (#421):**
- `config.py`: `CORS_ORIGINS` heeft als standaard `""`, dus zonder instelling staat geen enkele cross-origin toe.
- `Config.validate()` gooit een `ConfigError` als `CORS_ORIGINS` een `*` bevat; de server start dan niet.
- `server.py` geeft `Config.get_parsed_cors_origins()` aan de `CORSMiddleware`.
- `manifests/{development,test,playground,production}/values.yaml` noemen elk één expliciete `https://`-origin voor de eigen omgeving.

Test: `tests/test_config_cors.py`.

---

### S9 — JWT in localStorage ℹ️ Geaccepteerd

**Locatie:** `frontend/src/auth.js`  
**Probleem:** localStorage is toegankelijk via JavaScript (XSS-vector). Alternatieven zoals `httpOnly` cookies zijn robuuster.  
**Waarom geaccepteerd:** Een `httpOnly` cookie-oplossing vereist significante refactor en introduceert CSRF-risico's. Acceptabel risico voor de huidige doelgroep (interne gebruikers).  
**Voorbehoud:** de CSP beperkt XSS maar ten dele: `script-src` staat `'unsafe-inline'` en twee CDN-hosts toe (zie S13, #486).  
**Heroverwegen bij:** publieke toegang of gevoeliger data.

---

### S10 — Sessieduur 24 uur ❌ Open

**Locatie:** `core/auth.py` — `_TOKEN_TTL = 24 * 3600`  
**Probleem:** de geldigheid van een token staat vast op 24 uur en is niet via een environment variable in te stellen. Met OIDC geeft `POST /api/auth/refresh` (`routes/auth.py`) voor een geldig token een nieuw token van 24 uur.  
**Vervolg:** #479.

---

### S11 — Tool-enumeratie via LLM ℹ️ By design

**Aangetroffen in:** quickscan A3  
**Bevinding:** Het LLM beantwoordt vragen als "welke tools heb je?" met een accurate lijst van beschikbare functies.  
**Beoordeling:** De toolnamen en beschrijvingen zijn niet geheim; ze staan ook in de open source repository. Het LLM beperkt zich tot de aangeboden tools en kan geen willekeurige code uitvoeren. Geaccepteerd.

---

### S12 — Dependency-kwetsbaarheden ⚠️ Te verifiëren

**Was beschreven als:** een GitHub Actions-workflow met `pip-audit` en `npm audit`. Die workflow bestaat niet meer: `.github/workflows/` bevat alleen `docs.yml`, en `.gitlab-ci.yml` roept `pip-audit` noch `npm audit` aan.  
**Wel aanwezig:**
- `.gitlab-ci.yml` neemt de CI-component `surf-internal/sdp/components/base/security` op. Wat die component scant, staat niet in deze repository en is niet nagegaan.
- Renovate (`renovate.json`) stelt dependency-updates voor.

**Te doen:** vaststellen welke dependency-scan in CI draait en of een bevinding de pipeline blokkeert. Nog geen issue.

---

### S13 — CSP staat `'unsafe-inline'` en CDN-hosts toe ❌ Open

**Locatie:** `server.py` — middleware `security_headers`  
**Probleem:** `script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdn.plot.ly`.
- `cdn.jsdelivr.net` wordt door de app niet gebruikt (geen verwijzing in `frontend/src` of `frontend/index.html`; alleen `mkdocs.yml` van de docs-site laadt er een script van).
- `cdn.plot.ly` levert Plotly voor de HTML van rapporten en dashboards (`frontend/src/reportHtml.js`, `frontend/src/dashboardHtml.js`).
- `'unsafe-inline'` laat inline scripts toe, waardoor de CSP XSS maar ten dele afvangt.

**Vervolg:** #486 (Plotly self-hosten, CDN-hosts uit de CSP; `'unsafe-inline'` apart beoordelen).

---

### S14 — Token blijft na uitloggen geldig ❌ Open

**Locatie:** `core/auth.py` (`make_token`, `verify_token`), `routes/auth.py`  
**Probleem:** het token is een ondertekende tekst met gebruikersnaam en verloopmoment. De backend kent geen intrekking: na uitloggen blijft een token geldig tot het verloopt (S10).  
**Vervolg:** #479.

---

### S15 — `history`-actie omzeilt de invoerlimiet ❌ Open

**Locatie:** `routes/chat.py` — WebSocket-actie `history`  
**Probleem:** zie S7. De actie neemt tot `MAX_HISTORY` (40) door de client aangeleverde beurten van willekeurige lengte aan; die gaan bij de volgende vraag naar het model.  
**Vervolg:** #500.

---

### S16 — Geen privacy-informatie bij opslag van gesprekken ❌ Open

**Wat wordt opgeslagen:**
- Server-side, per gebruikersnaam (`persistence/db.py`): gesprekken (`conversations`), rapporten en dashboards (`workbooks`), feedback (`feedback`, `answer_feedback`) en data-recepten (`data_recipes`).
- In de browser: gesprekken en het lopende gesprek in localStorage (`frontend/src/conversationStore.js`).

**Probleem:** de app (`frontend/src`), `README.md` en `docs/` bevatten geen privacy-informatie: privacy, AVG of persoonsgegevens worden nergens genoemd. De gebruiker leest dus niet wat er wordt bewaard.  
**Vervolg:** #477.

---

## Aanbevelingen voor volgende stap

1. **S5 chat** — berichtlimiet per verbinding of gebruiker (#444); daarnaast nagaan welk adres de login-limiter als sleutel ziet (nog geen issue)
2. **S10/S14** — kortere of instelbare sessieduur en intrekking bij uitloggen (#479)
3. **S13** — Plotly self-hosten en CDN-hosts uit de CSP (#486)
4. **S15** — `history`-actie begrenzen (#500)
5. **S16** — privacy-informatie in app en docs (#477)
6. **S4 restpunt** — vaste tekst voor model-/API-fouten zonder eigen melding (nog geen issue)
7. **S12** — vaststellen welke dependency-scan in CI draait (nog geen issue); `nh3` uit `pyproject.toml` halen (S1, nog geen issue)
8. **Grondiger pentest** (aanbeveling Alan Berg punt 6) — met focus op: WebSocket aanvalsoppervlak, prompt-injection via datapayloads, uitgebreidere ZAP-scan van geauthenticeerde sessie
