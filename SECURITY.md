# Security bevindingen

Overzicht van bekende en mogelijke beveiligingsproblemen. Gebaseerd op de quickscan van Alan Berg (30-06-2026) en aanvullende code-review. Op 09-10-2026 nagelopen tegen de code op `main` (#484).

---

## Status overzicht

| # | Bevinding | Ernst | Status |
|---|---|---|---|
| S1 | HTML-injectie in geëxporteerde rapporten | Hoog | ✅ Opgelost (escaping in de frontend) |
| S2 | Lodash kwetsbare versie op loginpagina | Hoog | ✅ Opgelost (Chainlit verwijderd) |
| S3 | Ontbrekende HTTP security headers | Gemiddeld | ✅ Opgelost (middleware); CSP-restpunten in S13 (#486, #506) |
| S4 | Foutmeldingen lekken interne exceptie-tekst | Gemiddeld | ✅ Opgelost (#404, #503) |
| S5 | Geen rate limiting op login of chat | Gemiddeld | ⚠️ Gedeeltelijk — login beperkt per gebruikersnaam + adres (#504, restrisico hieronder); chat per gebruiker of verbinding (#444) |
| S6 | JWT-token in query parameter (WebSocket) | Laag–Gemiddeld | ✅ Opgelost (`bearer`-subprotocol, #103) |
| S7 | Geen maximale inputlengte op chatberichten | Laag | ✅ Opgelost (`MAX_MESSAGE_CHARS` voor nieuwe invoer; `HISTORY_MAX_CHARS` voor de historie, zie S15) |
| S8 | CORS staat op `*` als env var ontbreekt | Gemiddeld | ✅ Opgelost (standaard dicht, #421; elke origin met een `*`, ook een patroon als `https://*.nl`, geweigerd bij het opstarten, #506) |
| S9 | JWT opgeslagen in localStorage | Laag | ℹ️ Geaccepteerd — zie S9; CSP-voorbehoud in S13 (#486) |
| S10 | Sessieduur 24 uur, niet instelbaar | Laag | ✅ Opgelost (8 u per token via `SESSION_TTL_HOURS`, max. 24 u na inloggen via `SESSION_MAX_HOURS`, #479) |
| S11 | Tool-enumeratie via LLM; `run_analysis` voert modelcode uit | Laag | ℹ️ Geaccepteerd — het model kan via `run_analysis` willekeurige Python laten uitvoeren; de sandbox beperkt de schade maar is geen beveiligingsgrens (#443) |
| S12 | Dependency-kwetsbaarheden | Variabel | ⚠️ Te verifiëren (#506) |
| S13 | CSP staat `'unsafe-inline'`, twee CDN-hosts en WebSocket naar elke host toe | Laag–Gemiddeld | ❌ Open (#486; `connect-src` in #506) |
| S14 | Token blijft na uitloggen geldig | Gemiddeld | ✅ Opgelost (denylist bij uitloggen, #479); restrisico — zie S14 |
| S15 | `history`-actie omzeilt de invoerlimiet | Laag | ✅ Opgelost (#500) — tekencap op de hele historie |
| S16 | Geen privacy-informatie bij opslag van gesprekken | Gemiddeld | ❌ Open (#477); browseropslag na uitloggen (#507) |
| S17 | Dashboard-refresh voert tool-aanroepen van de client uit | Gemiddeld | ✅ Opgelost (#505) — allowlist van load-tools |
| S18 | `/info` gaf zonder inloggen databasetype en omgeving prijs | Laag | ✅ Opgelost (#518) |
| S19 | `LOG_LEVEL=DEBUG` zet gesprekstekst in het log | Laag | ℹ️ Gedocumenteerd (#516) — waarschuwing bij opstarten en in de docs |

---

## Details

### S1 — HTML-injectie in rapporten ✅ Opgelost

**Aangetroffen in:** quickscan A1  
**Was:** `md.markdown(llm_output)` injecteerde raw `<script>` tags in geëxporteerde HTML-bestanden.  
**Nu:** de server-side export (`export/`) bestaat niet meer. Rapporten en dashboards worden in de frontend opgebouwd door `buildReportHtml` (`frontend/src/reportHtml.js`) en `buildDashboardHtml` (`frontend/src/dashboardHtml.js`). Tekst uit het model gaat door `escapeHtml`; de figure-JSON in het inline script gaat door `scriptSafe` (#474); de dashboard-toelichting wordt met `react-markdown` gerenderd. Tests: `frontend/src/__tests__/reportHtml.test.js` en `frontend/src/__tests__/dashboardHtml.test.js`.  
**Opgeruimd (#506):** de ongebruikte dependency `nh3`, een overblijfsel van de server-side export, staat niet meer in `pyproject.toml` en `uv.lock`.

---

### S2 — Kwetsbare lodash ✅ Opgelost

**Aangetroffen in:** quickscan A2  
**Was:** lodash 4.17.21 op de Chainlit loginpagina (CVE-2026-2950, CVE-2025-13465, CVE-2026-4800).  
**Fix:** Chainlit verwijderd; eigen React-frontend gebruikt lodash niet.

---

### S3 — Ontbrekende HTTP security headers ✅ Opgelost

**Aangetroffen in:** ZAP-scan (16 alerts waaronder CSP, X-Frame-Options, HSTS, X-Content-Type-Options)  
**Fix:** middleware in `server.py` zet:
- `Content-Security-Policy` — beperkt script-, style-, img- en font-bronnen. `connect-src 'self' wss: ws:` beperkt WebSocket-verbindingen niet tot de eigen host (restpunten: zie S13)
- `X-Frame-Options: DENY` en CSP `frame-ancestors 'none'` — voorkomt clickjacking
- `Strict-Transport-Security` — dwingt HTTPS af
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Server: ""` — verbergt serverversie

---

### S4 — Foutmeldingen lekken interne tekst ✅ Opgelost

**Locatie:** `core/errors.py` (`friendly_error()`, `Gebruikersfout`), `routes/chat.py`, `agent/replay.py`  
**Fix (#404, #503):** alleen een `Gebruikersfout` — een fout waarvan de tekst voor de gebruiker is geschreven, zoals "Geen datasets geladen" — bereikt de browser letterlijk. Elke andere fout krijgt een vaste melding met een kort fout-ID; `log_interne_fout()` logt onder dat ID het type en een kenmerk van de exceptie (`fout_len=… fout_hash=…`) op ERROR, de traceback staat alleen op DEBUG in het log (#502). Dat geldt voor alle paden: het chat-antwoord, dashboard en rapport (`_generate_dashboard()`/`_generate_report()` vangen `Gebruikersfout` apart, al het andere gaat generiek), dashboard-refresh (`replay_data_calls()` bewaart per mislukte call een vaste tekst, de details staan in het log) en model-/API-fouten zonder vaste tekst in `_FRIENDLY_ERRORS` (vaste melding met fout-ID, `modelafhankelijk` blijft gelden).

---

### S5 — Rate limiting op login en chat ⚠️ Gedeeltelijk

**Login (beperkt):** `POST /api/auth/login` in `routes/auth.py` gebruikt `_login_limiter = RateLimiter(max_attempts=5, window_seconds=60)`: maximaal 5 pogingen per minuut per gebruikersnaam + `request.client.host` (#504). Daarboven volgt `429` met een `Retry-After`-header, ook voor een poging met het juiste wachtwoord — de limiter verraadt niet welke poging goed was. `RateLimiter` (`core/rate_limit.py`) houdt de pogingen in het geheugen bij, per proces.  
**Feedback:** `routes/feedback.py` heeft een eigen limiter (3 per 600 seconden).  
**Chat (beperkt, #444):** de WebSocket `/api/chat` telt elk verzoek dat het model kost (vraag, verduidelijking, dashboard, rapport) met `RateLimiter(CHAT_RATE_LIMIT, CHAT_RATE_WINDOW_S)` (standaard 30 per 600 s) per gebruikersnaam, en zonder login per verbinding (een vast ID per WebSocket dat een reset overleeft). Daarboven krijgt de client een foutmelding met de wachttijd en start er geen taak; voorbeeldvragen tellen niet mee. Per proces, in het geheugen, net als de login-limiter. De dashboard-refresh (`/api/dashboard/refresh` en de WebSocket-actie) kost geen model en telt niet mee. De maximale berichtlengte staat los daarvan, zie S7.  
**Blokkade voor iedereen opgelost (#504):** uvicorn draait zonder `--forwarded-allow-ips` en de manifests zetten `FORWARDED_ALLOW_IPS` niet, dus achter de ingress ziet de limiter waarschijnlijk voor iedereen hetzelfde adres. Met alleen het IP als sleutel deelden alle wachtwoordgebruikers dan één budget van 5 pogingen per pod, en kon iemand zonder inloggegevens wachtwoord-login voor iedereen blokkeren. De sleutel is nu gebruikersnaam + adres: een vol budget raakt alleen die ene combinatie.  
**Restrisico:** de limiter ziet waarschijnlijk alleen het adres van de ingress. Daardoor kan iedereen die een gebruikersnaam kent die account blijvend buitensluiten door elke minuut 5 pogingen te doen, en kan één client met 5 pogingen per minuut per gebruikersnaam één wachtwoord over veel gebruikersnamen spuiten. Per echte client tellen vergt dat uvicorn `X-Forwarded-For` van de ingress vertrouwt (`FORWARDED_ALLOW_IPS` op het ingress-subnet; uvicorn leest die env var zelf). Het subnet is nog niet vastgesteld en welk adres de limiter in het cluster ziet is nog niet nagegaan.

---

### S6 — JWT-token zichtbaar in query parameter ✅ Opgelost

**Was:** de WebSocket kreeg het token als query-parameter in de URL mee, en die belandt in proxy- en serverlogs.  
**Fix (#103, commit `2e7dbb0`):** de browser geeft het token mee als subprotocol (`["bearer", token]`). `routes/chat.py` leest de header `Sec-WebSocket-Protocol` met `token_uit_protocol()` uit `core/auth.py` en bevestigt het subprotocol `WS_SUBPROTOCOL` (`bearer`). De server neemt geen token uit de query-string meer aan. Test: `tests/test_token_niet_in_url.py`.

---

### S7 — Geen maximale inputlengte op chatberichten ✅ Opgelost

**Locatie:** `routes/chat.py` — de WebSocket-acties `message` en `clarification_choice`  
**Probleem:** Een gebruiker kon een bericht van willekeurige lengte sturen. Een extreem lang bericht (bijv. 500k tokens) leidt tot hoge LLM-kosten en trage respons.  
**Fix (#481):** `MAX_MESSAGE_CHARS` (env, standaard 4000 tekens, geteld na `strip()`). De server weigert een langer bericht of een langere verduidelijkingskeuze met een foutmelding die het maximum en de verstuurde lengte noemt, zonder de inhoud te herhalen; er start geen LLM-aanroep. De invoerbalk krijgt het maximum via `/api/config` (#501), toont vanaf 80% een teller en verstuurt niets boven de grens; `maxLength` (twee keer het maximum) vangt alleen absurd grote plakacties af. Opgeslagen gesprekken (`history`) vallen buiten de grens, zodat een oud gesprek altijd te heropenen is. De historie zelf is sinds #500 begrensd op `HISTORY_MAX_CHARS` tekens in totaal (zie S15).

---

### S8 — CORS staat standaard op `*` ✅ Opgelost

**Was:** de CORS-origins vielen terug op `*` als `CORS_ORIGINS` niet was ingesteld.  
**Fix (#421):**
- `config.py`: `CORS_ORIGINS` heeft als standaard `""`, dus zonder instelling staat geen enkele cross-origin toe.
- `Config.validate()` gooit een `ConfigError` als een origin in `CORS_ORIGINS` ergens een `*` bevat, dus ook bij `*` zelf en bij een patroon als `https://*.nl` of `*.example.nl`; de melding noemt die origins en de server start niet (#506). Een patroon zou nooit werken: de `CORSMiddleware` krijgt alleen `allow_origins` en vergelijkt een origin letterlijk, dus zo'n instelling faalde eerder stil. Wildcard-matching ondersteunen we bewust niet, omdat `allow_credentials` aan staat.
- `server.py` geeft `Config.get_parsed_cors_origins()` aan de `CORSMiddleware`.
- `manifests/{development,test,playground,production}/values.yaml` noemen elk één expliciete `https://`-origin voor de eigen omgeving.

Test: `tests/test_config_cors.py`.

---

### S9 — JWT in localStorage ℹ️ Geaccepteerd

**Locatie:** `frontend/src/auth.js`  
**Probleem:** localStorage is toegankelijk via JavaScript (XSS-vector). Alternatieven zoals `httpOnly` cookies zijn robuuster.  
**Waarom geaccepteerd:** Een `httpOnly` cookie-oplossing vereist significante refactor en introduceert CSRF-risico's. Acceptabel risico voor de huidige doelgroep (interne gebruikers).  
**Voorbehoud:** de CSP beperkt XSS maar ten dele: `script-src` staat `'unsafe-inline'` toe (zie S13).  
**Heroverwegen bij:** publieke toegang of gevoeliger data.

---

### S10 — Sessieduur 24 uur ✅ Opgelost

**Locatie:** `core/auth.py` (`SESSION_TTL`, `SESSION_MAX`, `make_token`), `routes/auth.py` (`POST /api/auth/refresh`)  
**Probleem:** de geldigheid van een token stond vast op 24 uur (`_TOKEN_TTL`) en was niet via een environment variable in te stellen. Met OIDC gaf `POST /api/auth/refresh` voor een geldig token een nieuw token van 24 uur, zonder grens aan de totale sessieduur.  
**Fix (#479):** een token geldt `SESSION_TTL_HOURS` (standaard 8). Het token bevat het inlogmoment; verversen houdt dat vast en geeft nooit een token voorbij `SESSION_MAX_HOURS` (standaard 24) na inloggen. Daarna geeft `/api/auth/refresh` 401 en moet de gebruiker opnieuw inloggen. Een ongeldige of niet-positieve waarde laat de server niet starten.

**Instellen via env var:**
```
SESSION_TTL_HOURS=8
SESSION_MAX_HOURS=24
```
Test: `tests/test_auth.py`, `tests/test_token_intrekking.py`. Intrekking bij uitloggen: zie S14.

---

### S11 — Tool-enumeratie en modelcode in `run_analysis` ℹ️ Geaccepteerd

**Aangetroffen in:** quickscan A3  
**Bevinding:** Het LLM beantwoordt vragen als "welke tools heb je?" met een accurate lijst van beschikbare functies.  
**Beoordeling:** De toolnamen en beschrijvingen zijn niet geheim; ze staan ook in de open source repository. Geaccepteerd.  
**Modelcode:** het LLM roept alleen de aangeboden tools aan, maar één daarvan, `run_analysis`, voert door het model geschreven Python uit (#410, #62). Het model kan dus willekeurige Python laten uitvoeren; wat die code doet, bepaalt het model, en daarmee ook wie het model via een vraag of via opgehaalde data stuurt. De afscherming beperkt wat die code kan:
- een AST-controle vooraf (`tools/scriptcontrole.py`) die onder meer imports, namen en attributen met `__`, frame-attributen en functies als `exec`, `eval`, `open` en `getattr` weigert;
- een apart proces (`tools/sandbox.py` start `tools/sandbox_kind.py` met `python -I`) met een eigen lege werkmap, een omgeving zonder geheimen (alleen `HOME`, `LANG` en thread-instellingen) en een time-out van 10 seconden waarna het proces wordt gestopt;
- in dat proces resourcelimieten (CPU-tijd, geheugen, geen bestanden schrijven, geen nieuwe processen), alleen een handvol builtins, en een audit hook die onder meer netwerk, subprocessen, schrijven en lezen buiten de Python-installatie weigert.

**Restrisico:** die lagen beperken de schade, maar zijn geen beveiligingsgrens. De AST-controle en de audit hook draaien in Python zelf; er is geen kernelgrens zoals seccomp, een container of een aparte gebruiker (#443). Een ontsnapping, bijvoorbeeld via een fout in de interpreter of in pandas of numpy, draait als dezelfde gebruiker als de server.  
**Waarom geaccepteerd, ernst Laag:** misbruik vraagt eerst een ontsnapping uit de sandbox; de audit achter #443 vond er geen, maar sluit er ook geen uit. Het risico is geaccepteerd en wordt gevolgd in #443 (sterkere isolatie zodra onvertrouwde gebruikers toegang krijgen). Dashboard-refresh kan `run_analysis` sinds #505 niet meer aanroepen (S17).

---

### S12 — Dependency-kwetsbaarheden ⚠️ Te verifiëren

**Was beschreven als:** een GitHub Actions-workflow met `pip-audit` en `npm audit`. Die workflow bestaat niet meer: `.github/workflows/` bevat alleen `docs.yml`, en `.gitlab-ci.yml` roept `pip-audit` noch `npm audit` aan.  
**Wel aanwezig:**
- `.gitlab-ci.yml` neemt de CI-component `surf-internal/sdp/components/base/security` op. Wat die component scant, staat niet in deze repository en is niet nagegaan.
- Renovate (`renovate.json`) stelt dependency-updates voor.

**Te doen:** vaststellen welke dependency-scan in CI draait en of een bevinding de pipeline blokkeert: #506.

---

### S13 — CSP staat `'unsafe-inline'` en WebSocket naar elke host toe ⚠️ Deels opgelost

**Locatie:** `server.py` — middleware `security_headers`  
**Probleem:** `script-src 'self' 'unsafe-inline'` en `connect-src 'self' wss: ws:`.
- De CDN-hosts zijn weg (#486): Plotly voor de HTML van rapporten en dashboards komt van de eigen server (`frontend/src/plotlyBron.js`, als asset onder `/assets`), oude opgeslagen HTML met `cdn.plot.ly` wordt bij het tonen herschreven, en de download krijgt Plotly inline. `cdn.jsdelivr.net` werd door de app niet gebruikt. Een test (`tests/test_security_headers.py`) houdt `script-src` zonder derde partij.
- `'unsafe-inline'` laat inline scripts toe, waardoor de CSP XSS maar ten dele afvangt.
- `wss:` en `ws:` in `connect-src` staan WebSocket-verbindingen naar elke host toe. Een script dat toch draait, kan zo gegevens uit de browser, zoals het token in localStorage (S9), naar buiten sturen.

**Vervolg:** `'unsafe-inline'` apart beoordelen (nonce of hash; het rapport-iframe is `sandbox="allow-scripts"`) en #506 voor `connect-src`.

---

### S14 — Token blijft na uitloggen geldig ✅ Opgelost

**Locatie:** `core/auth.py` (`verify_token`, `revoke_token`), `routes/auth.py` (`POST /api/auth/logout`), tabel `revoked_tokens` (`persistence/db.py`)  
**Probleem:** het token is een ondertekende tekst met gebruikersnaam en verloopmoment. De backend kende geen intrekking: na uitloggen bleef een token geldig tot het verliep, en met OIDC was het via `POST /api/auth/refresh` zonder grens te verlengen (S10), ook een buitgemaakt token.  
**Fix (#479):**
- Uitloggen (`handleLogout` in `frontend/src/App.jsx` roept `POST /api/auth/logout` aan) zet `sha256(token)` tot de vervaltijd van het token op een denylist in de database. Die denylist is gedeeld door alle replica's. Verlopen rijen worden bij elke intrekking en bij het opstarten opgeruimd.
- REST-routes, de WebSocket-connect (`/api/chat`), `POST /api/dashboard/refresh` en `POST /api/auth/refresh` weigeren een ingetrokken token.
- De database bewaart alleen de hash, nooit het token. De logs bevatten geen van beide.
- Een databasestoring bij de controle geeft 500, geen 401, zodat een storing niet als "sessie voorbij" geldt.

**Restrisico:**
- Een al open WebSocket blijft na uitloggen open tot de browser (of een andere client) hem sluit, ook voorbij de vervaltijd van het token. De server controleert het token alleen bij het verbinden.
- Uitloggen trekt alleen het meegestuurde token in. Andere tokens uit dezelfde sessie, zoals eerdere resultaten van `/api/auth/refresh`, blijven geldig en zijn te verversen tot `SESSION_MAX_HOURS` na inloggen. Wie zo'n token heeft buitgemaakt, houdt dus tot dat moment toegang.
- De frontend wacht niet op het antwoord van `POST /api/auth/logout`. Komt het verzoek niet aan, dan blijft het token geldig tot het verloopt.

Test: `tests/test_token_intrekking.py`.

---

### S15 — `history`-actie omzeilt de invoerlimiet ✅ Opgelost

**Locatie:** `routes/chat.py` (`_parse_history`), `core/config.py` (`HISTORY_MAX_CHARS`)  
**Probleem:** zie S7. De actie nam tot `MAX_HISTORY` (40) door de client aangeleverde beurten van willekeurige lengte aan; die gingen bij de volgende vraag naar het model. Een handgemaakte client kon zo de kostenaanval uitvoeren die S7 moest sluiten.  
**Fix (#500):** de hele aangeleverde historie is begrensd op `HISTORY_MAX_CHARS` tekens (standaard `MAX_HISTORY × MAX_MESSAGE_CHARS` = 160.000). Boven de cap vallen de oudste beurten af — dezelfde strategie als `MAX_HISTORY` — en een enkele beurt groter dan de cap wordt afgekapt in plaats van geweigerd, zodat bestaande gesprekken blijven openen.

---

### S16 — Geen privacy-informatie bij opslag van gesprekken ❌ Open

**Wat wordt opgeslagen:**
- Server-side, per gebruikersnaam (`persistence/db.py`): gesprekken (`conversations`), rapporten en dashboards (`workbooks`), feedback (`feedback`, `answer_feedback`) en data-recepten (`data_recipes`).
- In de browser: gesprekken en het lopende gesprek in localStorage (`frontend/src/conversationStore.js`).

**Probleem:** de app (`frontend/src`), `README.md` en `docs/` bevatten geen privacy-informatie: privacy, AVG of persoonsgegevens worden nergens genoemd. De gebruiker leest dus niet wat er wordt bewaard.  
**Na uitloggen:** `handleLogout` in `frontend/src/App.jsx` wist het token en via `clearLocalSessionData()` de gesprekken (incl. het lopende gesprek), de werkboeken en de dashboard-chat (berichten en figuren: `STORAGE_DC_MESSAGES`, `STORAGE_DC_FIGURES`) uit localStorage; de lijst staat in `SESSION_DATA_KEYS` (`frontend/src/constants.js`). Het effect in `frontend/src/pages/ChatPage.jsx` dat het lopende gesprek bewaart (`persistCurrentChat`), controleert niet of de sessie intussen is beëindigd, en lopende fetches kunnen ook nog terugschrijven. Zo kunnen gegevens van de vorige gebruiker na het wissen weer in de browser staan (#507).  
**Vervolg:** #477 (privacy-informatie), #507 (browseropslag na uitloggen).

---

### S17 — Dashboard-refresh voert tool-aanroepen van de client uit ✅ Opgelost

**Locatie:** `routes/chat.py` (`POST /api/dashboard/refresh` en de WebSocket-actie `refresh_dashboard`), `agent/replay.py` (`replay_data_calls()`)  
**Probleem:** de client stuurt het recept van het dashboard mee: toolnamen en argumenten. `replay_data_calls()` gaf elke naam en elk argument direct aan `tools.dispatch()`. Een client die de API mag gebruiken, kon zo elke tool aanroepen, ook `run_analysis` met eigen code, zonder dat het model eraan te pas komt.  
**Fix (#505):** `replay_data_calls()` herhaalt alleen tools uit `REPLAYABLE_TOOLS` — de drie load-tools (`get_duo_data`, `get_cbs_data`, `get_rio_data`) waaruit de server zelf recepten bouwt (`_build_recipe`). Elke andere toolnaam wordt geweigerd en gelogd; `run_analysis` is via refresh niet aan te roepen. De scopecontrole (#355) zit in de tools zelf en geldt daarmee ook voor dit pad.

---

### S18 — `/info` gaf zonder inloggen databasetype en omgeving prijs ✅ Opgelost

**Locatie:** `server.py` (`GET /info`)  
**Probleem:** het eindpunt is zonder token bereikbaar en gaf naast de naam en of OIDC aan staat ook het databasetype (`PostgreSQL`/`SQLite`) en een omgevingslabel terug. Geen secret, maar details die een aanvaller helpen. De frontend gebruikt het eindpunt niet.  
**Fix (#518):** `/info` geeft alleen nog de naam en of OIDC aan staat. `/version` blijft bewust commit en catalogusrevisies publiceren (transparantie en controle van de deployment).

---

### S19 — `LOG_LEVEL=DEBUG` zet gesprekstekst in het log ℹ️ Gedocumenteerd

**Locatie:** `agent/run.py` (DEBUG-logregels), `server.py` (opstartcontrole), `docs/configuratie/index.md`  
**Situatie:** sinds #475 staan vraag en antwoord op INFO alleen als lengte en hash; de letterlijke tekst staat op DEBUG. Wie `LOG_LEVEL=DEBUG` zet, krijgt gesprekstekst — en dus eventuele persoonsgegevens — in de logaggregatie, met de bewaartermijn daarvan.  
**Maatregel (#516):** de server logt bij het opstarten een WARNING als het niveau DEBUG is, en de configuratiedocumentatie waarschuwt het niveau niet te gebruiken op test of productie met echte gebruikers. Vervolg van de logging-restpunten in #502.

---

## Aanbevelingen voor volgende stap

1. **S5** — berichtlimiet voor de chat per verbinding of gebruiker (#444); het ingress-subnet vaststellen en `FORWARDED_ALLOW_IPS` zetten zodat de limiter het echte client-adres ziet (restrisico #504)
2. **S13** — Plotly self-hosten en CDN-hosts uit de CSP (#486); `connect-src` beperken (#506)
3. **S16** — privacy-informatie in app en docs (#477); geen browseropslag meer na uitloggen (#507)
4. **S12** — vaststellen welke dependency-scan in CI draait (#506); `nh3` opruimen (S1) en de CORS-validatie aanscherpen (S8) zijn gedaan
5. **Grondiger pentest** (aanbeveling Alan Berg punt 6) — met focus op: WebSocket aanvalsoppervlak, prompt-injection via datapayloads, uitgebreidere ZAP-scan van geauthenticeerde sessie
