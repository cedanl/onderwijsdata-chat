# Security bevindingen

Overzicht van bekende en mogelijke beveiligingsproblemen. Gebaseerd op de quickscan van Alan Berg (30-06-2026) en aanvullende code-review. Op 09-10-2026 nagelopen tegen de code op `main` (#484).

---

## Status overzicht

| # | Bevinding | Ernst | Status |
|---|---|---|---|
| S1 | HTML-injectie in geëxporteerde rapporten | Hoog | ✅ Opgelost (escaping in de frontend) |
| S2 | Lodash kwetsbare versie op loginpagina | Hoog | ✅ Opgelost (Chainlit verwijderd) |
| S3 | Ontbrekende HTTP security headers | Gemiddeld | ✅ Opgelost (middleware); `'unsafe-inline'` blijft een restpunt in S13 |
| S4 | Foutmeldingen lekken interne exceptie-tekst | Gemiddeld | ✅ Opgelost (#404, #503) |
| S5 | Geen rate limiting op login of chat | Gemiddeld | ⚠️ Gedeeltelijk — login beperkt per gebruikersnaam + adres (#504, restrisico hieronder); chat per gebruiker of verbinding (#444) |
| S6 | JWT-token in query parameter (WebSocket) | Laag–Gemiddeld | ✅ Opgelost (`bearer`-subprotocol, #103) |
| S7 | Geen maximale inputlengte op chatberichten | Laag | ✅ Opgelost (`MAX_MESSAGE_CHARS` voor nieuwe invoer; `HISTORY_MAX_CHARS` voor de historie, zie S15) |
| S8 | CORS staat op `*` als env var ontbreekt | Gemiddeld | ✅ Opgelost (standaard dicht, #421; elke origin met een `*`, ook een patroon als `https://*.nl`, geweigerd bij het opstarten, #506) |
| S9 | JWT opgeslagen in localStorage | Laag | ℹ️ Geaccepteerd — zie S9; CSP-voorbehoud in S13 (#486) |
| S10 | Sessieduur 24 uur, niet instelbaar | Laag | ✅ Opgelost (8 u per token via `SESSION_TTL_HOURS`, max. 24 u na inloggen via `SESSION_MAX_HOURS`, #479) |
| S11 | Tool-enumeratie via LLM; `run_analysis` voert modelcode uit | Laag | ℹ️ Geaccepteerd — het model kan via `run_analysis` willekeurige Python laten uitvoeren; de sandbox beperkt de schade maar is geen beveiligingsgrens (#443) |
| S12 | Dependency-kwetsbaarheden | Variabel | ✅ Gescand in CI, informatief (`audit:python`, `audit:npm`, #506) |
| S13 | CSP staat `'unsafe-inline'` toe | Laag–Gemiddeld | ⚠️ Deels opgelost (CDN-hosts weg, #486; `connect-src` alleen de eigen server, #506) |
| S14 | Token blijft na uitloggen geldig | Gemiddeld | ✅ Opgelost (denylist bij uitloggen, #479); restrisico — zie S14 |
| S15 | `history`-actie omzeilt de invoerlimiet | Laag | ✅ Opgelost (#500) — tekencap op de hele historie |
| S16 | Geen privacy-informatie bij opslag van gesprekken | Gemiddeld | ❌ Open (#477); browseropslag na uitloggen (#507) |
| S17 | Dashboard-refresh voert tool-aanroepen van de client uit | Gemiddeld | ✅ Opgelost (#505) — allowlist van load-tools |
| S18 | `/info` gaf zonder inloggen databasetype en omgeving prijs | Laag | ✅ Opgelost (#518) |
| S19 | `LOG_LEVEL=DEBUG` zet gesprekstekst in het log | Laag | ℹ️ Gedocumenteerd (#516) — waarschuwing bij opstarten en in de docs |
| S20 | `/version` zonder inloggen geeft versie en commit prijs | Laag | ℹ️ Geaccepteerd (#552) — blijft open voor de deploycontrole; restrisico hieronder |
| S21 | SRAM-e-mailadres als sleutel van de gebruikersdata; `CHAT_USERS`-wachtwoorden in platte tekst | Laag–Gemiddeld | ℹ️ Bekend, bewust uitgesteld (#487, 19-10-2026) — de SRAM-gebruikerscache is al begrensd; voorwaarde voor productie hieronder |
| S22 | Opgeslagen rapport-HTML draaide met dialogen en pop-ups in de viewer en ongesandboxt in de download | Gemiddeld | ⚠️ Deels opgelost (#634) — viewer alleen `allow-scripts`, policy in frame en download; de server controleert de HTML niet (restpunt, voorwaarde voor productie hieronder) |
| S23 | Openbare oppervlakte: API-documentatie en dashboard-data zonder inloggen, geen `Permissions-Policy` | Laag | ⚠️ Deels opgelost (#636) — dashboard-eindpunten achter login en vlag, `Permissions-Policy` gezet; API-documentatie alleen buiten productie, maar geen omgeving in `manifests/` geldt nu als productie (restpunt hieronder) |

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
- `Content-Security-Policy` — beperkt script-, style-, img-, worker- en font-bronnen; `connect-src` staat alleen de eigen server toe (`'self'` plus de `wss://`-origin uit `SERVER_URL`, #506); `worker-src 'self' blob:` omdat de kaart (maplibre) zijn worker vanaf een `blob:`-URL start (#632). Restpunt `'unsafe-inline'`: zie S13
- `X-Frame-Options: DENY` en CSP `frame-ancestors 'none'` — voorkomt clickjacking
- `Strict-Transport-Security` — dwingt HTTPS af
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=()` — de app gebruikt die browserfuncties niet, dus ook geen ingesloten frame of geïnjecteerd script mag ze vragen (#636)
- Geen `Server`-header — uvicorn start met `--no-server-header` (`Dockerfile`), dus antwoorden noemen de serversoftware niet. De middleware zet zelf geen lege `Server`-header meer: die kwam naast `Server: uvicorn` te staan in plaats van die te vervangen (#534)

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
- een AST-controle vooraf (`tools/scriptcontrole.py`) die onder meer imports, namen en attributen met `__`, frame-attributen, functies als `exec`, `eval`, `open` en `getattr` en een stdlib-module achter een bibliotheekobject (`pd.io.common.os`) weigert, ook in een pandas-expressie als `df.eval('@pd.io.common.os.getpid()')` (#443);
- een apart proces (`tools/sandbox.py` start `tools/sandbox_kind.py` met `python -I`) met een eigen lege werkmap, een omgeving zonder geheimen (alleen `HOME`, `LANG` en thread-instellingen) en een time-out van 10 seconden waarna het proces wordt gestopt;
- in dat proces resourcelimieten (CPU-tijd, geheugen, geen bestanden schrijven, geen nieuwe processen), alleen een handvol builtins, en een audit hook die onder meer netwerk, subprocessen, schrijven en lezen buiten de Python-installatie weigert.

**Restrisico:** die lagen beperken de schade, maar zijn geen beveiligingsgrens. De AST-controle en de audit hook draaien in Python zelf; de pod draait als niet-root met `seccompProfile: RuntimeDefault` en zonder capabilities, maar die grens omsluit server en kindproces samen: tussen die twee staat geen eigen container, seccomp-profiel of aparte gebruiker (#443). Een ontsnapping, bijvoorbeeld via een fout in de interpreter of in pandas of numpy, draait als dezelfde gebruiker als de server. De geheugenlimiet van het kindproces (1 GiB) past in de pod-limieten (`manifests/<omgeving>/values.yaml`: 2 GiB op test en playground, 4 GiB op productie), zodat een zwaar script het kindproces stopt en niet de server.  
**Waarom geaccepteerd, ernst Laag:** misbruik vraagt eerst een ontsnapping uit de sandbox; de audit achter #443 vond er geen, maar sluit er ook geen uit. Het risico is geaccepteerd en wordt gevolgd in #443 (sterkere isolatie zodra onvertrouwde gebruikers toegang krijgen). Dashboard-refresh kan `run_analysis` sinds #505 niet meer aanroepen (S17).

---

### S12 — Dependency-kwetsbaarheden ✅ Gescand in CI (informatief)

**Was beschreven als:** een GitHub Actions-workflow met `pip-audit` en `npm audit` (beide met `|| true`). Die workflow verdween met de Azure-infrastructuur (`19f1af6`) en had geen opvolger in GitLab.  
**Nagegaan (#506):** de CI-component `surf-internal/sdp/components/base/security@0.10.10` neemt alleen GitLab's Secret-Detection- en SAST-templates op (semgrep, kubesec), geen dependency-scan. Die jobs draaien op branchpipelines, niet in MR-pipelines, en blokkeren niets.  
**Nu:** twee eigen jobs in `.gitlab-ci.yml`, op `main` en in elke MR:
- `audit:python` — `pip-audit` op de gelockte versies uit `uv.lock` (`uv export`), zonder installatie. De git-dependencies `riodata` en `onderwijsdata` staan niet in de PyPI-advisorydatabase en vallen erbuiten.
- `audit:npm` — `npm audit --audit-level=high` op `frontend/package-lock.json`.

Beide staan op `allow_failure: true`: een nieuwe CVE kleurt de job geel maar blokkeert geen MR die er niets mee te maken heeft. Renovate (`renovate.json`) stelt de update voor. Bij het invoeren (13-10-2026) vonden beide niets.

---

### S13 — CSP staat `'unsafe-inline'` toe ⚠️ Deels opgelost

**Locatie:** `server.py` — middleware `security_headers`  
**Probleem:** `script-src 'self' 'unsafe-inline'`.
- De CDN-hosts zijn weg (#486): Plotly voor de HTML van rapporten en dashboards komt van de eigen server (`frontend/src/plotlyBron.js`, als asset onder `/assets`), oude opgeslagen HTML met `cdn.plot.ly` wordt bij het tonen herschreven, en de download krijgt Plotly inline. `cdn.jsdelivr.net` werd door de app niet gebruikt. Een test (`tests/test_security_headers.py`) houdt `script-src` zonder derde partij.
- `connect-src` stond `wss:` en `ws:` toe, dus WebSocket-verbindingen naar elke host; een script dat toch draaide, kon zo gegevens uit de browser (zoals het token in localStorage, S9) naar buiten sturen. Nu alleen de eigen server (#506): `'self'` plus de `wss://`-origin uit `SERVER_URL` (`server.connect_src`). Die origin staat er expliciet bij omdat oudere Safari-versies `'self'` niet op `wss:` laten slaan; zonder `SERVER_URL` (lokaal) alleen `'self'`. De chat opent zijn WebSocket naar `location.host` (`frontend/src/auth.js`).
- `'unsafe-inline'` laat inline scripts toe, waardoor de CSP XSS maar ten dele afvangt.
- `worker-src 'self' blob:` (#632): maplibre, waarmee Plotly de kaart van `create_choropleth_map` tekent, start zijn web-worker vanaf een `blob:`-URL. Zonder `worker-src` viel dat terug op `script-src`, werd de worker geblokkeerd en bleef de kaart leeg. `blob:` staat alleen in `worker-src`, niet in `script-src`: een script dat al draait kan zo een worker uit een blob starten, maar geen blob als script laden. Dat is smaller dan wat `'unsafe-inline'` al toestaat. Een test houdt `worker-src` op precies `'self' blob:` en `script-src` zonder `blob:`.

**Vervolg:** `'unsafe-inline'` apart beoordelen (nonce of hash; het rapport-iframe is `sandbox="allow-scripts"` met een eigen policy, S22).

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

### S16 — Geen privacy-informatie bij opslag van gesprekken ⚠️ Deels opgelost

**Wat wordt opgeslagen:**
- Server-side, per gebruikersnaam (`persistence/db.py`): gesprekken (`conversations`), rapporten en dashboards (`workbooks`), feedback (`feedback`, `answer_feedback`) en data-recepten (`data_recipes`).
- In de browser: gesprekken en het lopende gesprek in localStorage (`frontend/src/conversationStore.js`).
- Gesprek verwijderen wist `conversations` en `data_recipes`. Feedback per antwoord (`answer_feedback`) van dat gesprek blijft voor het team, met vraag, antwoord en stappen maar zonder gebruikersnaam en gesprek-id (#476); de 👎-vorm zegt dat.

**Probleem:** de app (`frontend/src`), `README.md` en `docs/` bevatten geen privacy-informatie: privacy, AVG of persoonsgegevens worden nergens genoemd. De gebruiker leest dus niet wat er wordt bewaard.  
**Na uitloggen:** `handleLogout` in `frontend/src/App.jsx` wist het token en via `clearLocalSessionData()` de gesprekken (incl. het lopende gesprek), de werkboeken en de dashboard-chat (berichten en figuren: `STORAGE_DC_MESSAGES`, `STORAGE_DC_FIGURES`) uit localStorage; de lijst staat in `SESSION_DATA_KEYS` (`frontend/src/constants.js`). Het effect in `frontend/src/pages/ChatPage.jsx` dat het lopende gesprek bewaart (`persistCurrentChat`), controleert niet of de sessie intussen is beëindigd, en lopende fetches kunnen ook nog terugschrijven. Zo kunnen gegevens van de vorige gebruiker na het wissen weer in de browser staan (#507).  
**Stand (14-10-2026, #477):** de app heeft een pagina `/privacy` (`frontend/src/pages/PrivacyPage.jsx`), ook zonder sessie bereikbaar, met links op de loginpagina, in de voettekst van de startpagina, onder het invoerveld en in de instellingen; dezelfde tekst staat in `docs/privacy.md`. Zij beschrijft wat naar de AI-dienst gaat, wat server en browser bewaren, het log en wat de gebruiker zelf kan doen. Nog open, en zo benoemd op de pagina: verwerkersovereenkomst en regio van de AI-aanbieder, bewaartermijn (#485) en DPIA. De verwerkingsverantwoordelijke is besloten (19-10-2026, #553): de deelnemende instelling, en daar gaat ook een privacyvraag heen.  
**Vervolg:** #553 (open punten), #485 (bewaartermijn), #507 (browseropslag na uitloggen).

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

### S20 — `/version` zonder inloggen geeft versie en commit prijs ℹ️ Geaccepteerd

**Locatie:** `server.py` (`GET /version`, ook als `GET /api/version`)  
**Situatie:** het eindpunt is zonder token bereikbaar. Het geeft de release, de commit waaruit het image is gebouwd, de meegebouwde versie en commit van de catalogus-packages (met de CBS-catalogusrevisie) en de dataversie van UWV en ROA. Geen persoonsgegevens en geen secrets.  
**Besluit (#552):** open laten. Na elke deploy en promotie wordt met `curl …/version` gecontroleerd welke release en commit draaien (`CLAUDE.md`, `Agents.md`, `docs/promoten.md`), met een kale `curl` zonder token. Achter een token zetten vraagt dat al die controles er een meesturen.  
**Restrisico:** fingerprinting: met de exacte versie en commit kan een aanvaller gericht zoeken naar bekende kwetsbaarheden in die versie. Beperkt doordat `/info` niets meer over database of omgeving zegt (S18) en de dependency-scan in CI nieuwe CVE's meldt (S12). Opnieuw bekijken als de app buiten de demofase breder bereikbaar wordt.

---

### S21 — SRAM-e-mailadres als sleutel; `CHAT_USERS`-wachtwoorden in platte tekst ℹ️ Bekend, bewust uitgesteld

**Aangetroffen in:** privacy-review, bevindingen M4 en L4 (testronde 9 okt 2026; uit code-review, niet live gereproduceerd)  
**Locatie:** `routes/auth.py` (`oidc_callback`, `_oidc_user_cache`), `core/auth.py` (`parse_users`, `check_credentials`), `persistence/db.py`  
**Situatie:**
- **E-mailadres als sleutel:** na inloggen met SURF SRAM is de gebruikersnaam `userinfo.get("email") or userinfo.get("sub")` (`oidc_callback`): het e-mailadres, en alleen zonder e-mail het pseudonieme `sub`. Die gebruikersnaam is de sleutel van `conversations`, `workbooks`, `feedback`, `answer_feedback` (tot het gesprek wordt verwijderd, #476), `algemene_feedback` en `data_recipes` (`persistence/db.py`). Ook de auteur van een rapport komt uit het account: de chatpagina stuurt de naam uit SRAM mee, of zonder naam die gebruikersnaam; zonder auteur valt `routes/chat.py` terug op de gebruikersnaam, en `frontend/src/reportHtml.js` zet de auteur in het rapport. Elke rij en elk rapport van een SRAM-gebruiker is zo direct identificerend. `/privacy` en `docs/privacy.md` ("Wat de server bewaart") noemen het e-mailadres als accountnaam (S16).
- **Wachtwoorden in platte tekst:** `CHAT_USERS` (`gebruiker:wachtwoord,…`) staat ongehasht in de omgeving. `parse_users` leest de waarde in, `check_credentials` vergelijkt met `hmac.compare_digest` (timing-safe), en login is beperkt tot 5 pogingen per minuut per gebruikersnaam + adres (S5). `manifests/{test,playground,production}/values.yaml` laden `CHAT_USERS` uit de secret; test en playground zetten daarnaast `OIDC_PROVIDER=SRAM`, productie niet.
- **Al opgelost: de SRAM-gebruikerscache.** `_oidc_user_cache` in `routes/auth.py` (naam, e-mail, organisatie en instelling per gebruiker, in het geheugen van het proces) is begrensd (#487, `ac07d2e`): een rij vervalt na `SESSION_MAX` (`SESSION_MAX_HOURS`, standaard 24 uur), en boven `_OIDC_CACHE_MAX` (1000) gebruikers gaat de langst niet gebruikte eruit. Test: `tests/test_oidc_cache.py`.

**Besluit (#487, 19-10-2026):** in de demofase wordt niets gebouwd. De sleutel en de wachtwoorden blijven zoals ze zijn; beide zijn bekend en bewust uitgesteld.  
**Restrisico:** wie de database kan lezen, ziet bij elke rij van een SRAM-gebruiker het e-mailadres, en een rapport noemt de naam of het e-mailadres als auteur. Wie de omgevingsvariabelen van de pod of de ontsleutelde secret kan lezen, kent de wachtwoorden van alle `CHAT_USERS`-accounts.  
**Voorwaarde voor productie:**
- De sleutel wordt het pseudonieme `sub`, met het e-mailadres alleen als weergavenaam, en een migratie van de bestaande rijen in de tabellen hierboven.
- Productie alleen via SRAM of met gehashte wachtwoorden; niet met `CHAT_USERS` in platte tekst, zoals `manifests/production/values.yaml` nu.

---

### S22 — Opgeslagen rapport-HTML ⚠️ Deels opgelost

**Aangetroffen in:** robuustheidsronde 19-10-2026 (M-1, live bevestigd op build `60e0526`)  
**Locatie:** `routes/persistence.py` (`PUT /api/workbooks/{id}`), `frontend/src/components/WorkbookViewer.jsx`, `frontend/src/components/WorkbookDownload.jsx`, `frontend/src/rapportSandbox.js`  
**Was:** de server bewaart `html_content` byte voor byte, dus ook `<script>` en `onerror`. De viewer toonde het rapport met `sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox allow-modals"`: een opgeslagen rapport kon `alert`, `confirm` en een geloofwaardige `prompt("Log opnieuw in…")` tonen en een tab naar elke host openen. "Download als HTML" leverde hetzelfde bestand zonder sandbox. Het frame had wel een opaque origin: het bereikte het token, de app en haar opslag niet. Op het gedeelde demo-account opent elke tester rapporten van anderen (#488).  
**Nu (#634):**
- Het viewerframe heeft alleen `allow-scripts`: geen dialogen, geen pop-ups. Een link in het rapport gaat als bericht naar de app, die alleen een `http(s)`-adres opent, met `noopener,noreferrer`, en alleen direct na een klik van de gebruiker (`navigator.userActivation`).
- "Opslaan als PDF" (#622) heeft `allow-modals` nodig voor `print()`. Dat krijgt alleen een eigen, onzichtbaar printframe dat de knop maakt, zonder `allow-popups`, en daarin bestaan `alert`, `confirm` en `prompt` niet (niet te overschrijven; een kindframe om ze terug te halen houdt `frame-src 'none'` tegen). Het printbericht telt alleen als het van de app komt (`event.source === parent`).
- Een `Content-Security-Policy`-meta vooraan in het frame én in de download: scripts alleen inline en (in het frame) van de eigen server, geen `connect-src`, `form-action`, `frame-src` of `base-uri`, beelden en fonts alleen als `data:`. Een gedownload rapport dat van schijf draait, kan zo niets versturen.
- De voorbeeldtegels hadden al `sandbox=""` (#427).

Tests: `frontend/src/__tests__/rapportSandbox.test.js`, `rapportPdf.test.js`, `workbookViewerFallback.test.js`, `workbookDownload.test.js`; live gemeten in de MR van #634.  
**Restpunt (bewust):** de server controleert of bouwt `html_content` niet. Rapport-HTML wordt in de browser gemaakt (`buildReportHtml`), en de spec waaruit het komt wordt niet bewaard, dus de server kan een rapport niet opnieuw opbouwen; een HTML-filter op de server zou de grafiekscripts van elk echt rapport ook moeten toelaten. Een opgeslagen rapport kan dus nog willekeurige scripts draaien, binnen de grenzen hierboven.  
**Voorwaarde voor productie:** een eigen account per gebruiker (niet het gedeelde demo-account van #488), zodat een kwaadaardig rapport alleen zijn eigen maker raakt; of de server bewaart de spec en bouwt de HTML zelf.

---

### S23 — Openbare oppervlakte ⚠️ Deels opgelost

**Aangetroffen in:** robuustheidsronde 19-10-2026 (#636)  
**Locatie:** `server.py` (`FastAPI(...)`, `security_headers`), `routes/instellingen.py` (`GET /api/dashboard/*`), `frontend/src/api.js` (`fetchDashboardData`), `frontend/src/components/dashboards/shared/hooks.js`  
**Was:**
- `/api/docs` (Swagger UI), `/redoc` en `/api/openapi.json` waren zonder token bereikbaar: het schema somt elke route op, en Swagger UI en ReDoc laden hun scripts van `cdn.jsdelivr.net`.
- `GET /api/dashboard/{instroom,regio,nationaal,rendement,arbeidsmarktmatch}` laadden en rekenden DUO- en CBS-data voor iedereen, ook met login aan en ook met `ENABLE_DASHBOARDS=false`. De frontend haalde ze op zonder token.
- Geen `Permissions-Policy`-header.

**Nu (#636):**
- De API-documentatie bestaat alleen buiten productie. "Productie" is `Config.is_production()`: `POSTGRES_URI` én `SESSION_SECRET` gezet. Daar geven `/api/docs` en `/api/openapi.json` 404, en `/redoc` bestaat niet (met de gebouwde frontend krijgt het pad, zoals elk onbekend pad, `index.html` van de SPA). Er wordt dan geen documentatiepagina en geen Swagger- of ReDoc-script geserveerd.
- De vijf dashboard-eindpunten vragen met login aan een geldig token (anders 401), en geven met `ENABLE_DASHBOARDS=false` dezelfde 403 als `POST /api/dashboard/refresh` (`{"error": "Dashboards zijn niet beschikbaar"}`), zonder data te laden. Zonder login (lokaal) werken ze zoals voorheen voor `gast`. De frontend stuurt het token mee en beëindigt de sessie bij een 401, zoals bij de andere API-aanroepen.
- `Permissions-Policy` op elk antwoord, zie S3.
- Al gedekt, geen wijziging: het printbericht van een rapport telt alleen als het van de app komt (`event.source === parent`, `PRINT_JS` in `frontend/src/reportHtml.js`; #634, zie S22).

Tests: `tests/test_openbare_oppervlakte.py`, `tests/test_security_headers.py`, `frontend/src/__tests__/dashboardFetch.test.js`.  
**Restpunt (docs):** geen omgeving in `manifests/` zet `SESSION_SECRET` (de app leest die variabele alleen in `Config.is_production()`), dus test, playground en productie gelden niet als productie en tonen de API-documentatie nog. Pas als een omgeving `SESSION_SECRET` (naast `POSTGRES_URI`) krijgt, gaat de documentatie daar uit; dat is een wijziging in de manifests en de secrets, voor de ontwikkelaar.  
**Bewust open:** `/api/instellingen`, `/api/catalog/counts` en `/api/feedback/questions` blijven zonder token bereikbaar. De app en de loginpagina vragen `/api/instellingen` op vóór het inloggen; over de andere twee wordt later besloten (#636).

---

## Aanbevelingen voor volgende stap

1. **S5** — berichtlimiet voor de chat per verbinding of gebruiker (#444); het ingress-subnet vaststellen en `FORWARDED_ALLOW_IPS` zetten zodat de limiter het echte client-adres ziet (restrisico #504)
2. **S13** — `'unsafe-inline'` vervangen door nonces of hashes; CDN-hosts (#486) en `connect-src` (#506) zijn gedaan
3. **S16** — privacy-informatie in app en docs (#477); geen browseropslag meer na uitloggen (#507)
4. **S12** — de gele `audit:*`-jobs volgen; een dependency-scan in CI (#506), `nh3` opruimen (S1) en de CORS-validatie (S8) zijn gedaan
5. **S21** — vóór productie: sleutel naar `sub` met e-mail alleen als weergavenaam en een migratie van de bestaande rijen; productie alleen via SRAM of gehashte wachtwoorden (#487). In de demofase bewust niet gebouwd; de SRAM-cache is al begrensd
6. **S22** — vóór productie: eigen account per gebruiker, of de server bewaart de rapportspec en bouwt de HTML zelf (#634)
7. **S23** — `SESSION_SECRET` zetten op de omgevingen die als productie moeten gelden, zodat de API-documentatie daar uit gaat; besluiten of `/api/instellingen`, `/api/catalog/counts` en `/api/feedback/questions` open blijven (#636)
8. **Grondiger pentest** (aanbeveling Alan Berg punt 6) — met focus op: WebSocket aanvalsoppervlak, prompt-injection via datapayloads, uitgebreidere ZAP-scan van geauthenticeerde sessie
