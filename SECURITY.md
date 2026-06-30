# Security bevindingen

Overzicht van bekende en mogelijke beveiligingsproblemen. Gebaseerd op de quickscan van Alan Berg (30-06-2026) en aanvullende code-review. Bijgewerkt na v1.0.0.

---

## Status overzicht

| # | Bevinding | Ernst | Status |
|---|---|---|---|
| S1 | HTML-injectie in geëxporteerde rapporten | Hoog | ✅ Opgelost (nh3 sanitizer) |
| S2 | Lodash kwetsbare versie op loginpagina | Hoog | ✅ Opgelost (Chainlit verwijderd) |
| S3 | Ontbrekende HTTP security headers | Gemiddeld | ✅ Opgelost (middleware) |
| S4 | Foutmeldingen lekken interne exceptie-tekst | Gemiddeld | ⚠️ Gedeeltelijk — zie S4 |
| S5 | Geen rate limiting op login of chat | Gemiddeld | ❌ Open |
| S6 | JWT-token in query parameter (WebSocket) | Laag–Gemiddeld | ❌ Open |
| S7 | Geen maximale inputlengte op chatberichten | Laag | ❌ Open |
| S8 | CORS staat op `*` als env var ontbreekt | Gemiddeld | ❌ Open (configuratie) |
| S9 | JWT opgeslagen in localStorage | Laag | ℹ️ Geaccepteerd — zie S9 |
| S10 | Sessie-timeout 24 uur | Laag | ℹ️ Instelbaar via env |
| S11 | Tool-enumeratie via LLM | Laag | ℹ️ By design |
| S12 | Dependency-kwetsbaarheden | Variabel | ✅ Scanning in CI |

---

## Details

### S1 — HTML-injectie in rapporten ✅ Opgelost

**Aangetroffen in:** quickscan A1  
**Was:** `md.markdown(llm_output)` injecteerde raw `<script>` tags in geëxporteerde HTML-bestanden.  
**Fix:** `nh3.clean()` sanitiseert de HTML-output van markdown-conversie in `export/report.py` en `export/dashboard.py`.

---

### S2 — Kwetsbare lodash ✅ Opgelost

**Aangetroffen in:** quickscan A2  
**Was:** lodash 4.17.21 op de Chainlit loginpagina (CVE-2026-2950, CVE-2025-13465, CVE-2026-4800).  
**Fix:** Chainlit verwijderd; eigen React-frontend gebruikt lodash niet.

---

### S3 — Ontbrekende HTTP security headers ✅ Opgelost

**Aangetroffen in:** ZAP-scan (16 alerts waaronder CSP, X-Frame-Options, HSTS, X-Content-Type-Options)  
**Fix:** middleware in `server.py` zet:
- `Content-Security-Policy` — beperkt script/style/connect bronnen
- `X-Frame-Options: DENY` en CSP `frame-ancestors 'none'` — voorkomt clickjacking
- `Strict-Transport-Security` — dwingt HTTPS af
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Server: ""` — verbergt serverversie

---

### S4 — Foutmeldingen lekken interne tekst ⚠️ Gedeeltelijk

**Locatie:** `errors.py` regel 17  
**Probleem:** De fallback-branch van `friendly_error()` stuurt de ruwe Python-exceptie naar de browser:
```python
return f"❌ Er is een fout opgetreden: {exc}"
```
Bekende LiteLLM-fouttypen worden netjes afgevangen, maar onbekende exceptions (bijv. uit datatools) lekken interne details zoals bestandspaden, modulenamen of stacktrace-fragmenten.  
**Aanbeveling:** Fallback veranderen naar een generieke tekst; de exception loggen naar server-stderr:
```python
import logging
logger = logging.getLogger(__name__)
logger.exception("Unhandled error in agent run")
return "❌ Er is een onverwachte fout opgetreden."
```

---

### S5 — Geen rate limiting op login en chat ❌ Open

**Locatie:** `POST /api/auth/login`, WebSocket `/api/chat`  
**Probleem:** Geen beperking op het aantal loginpogingen (brute force wachtwoord) en geen limiet op chatberichten per sessie (LLM-kosten misbruik). Op Azure App Service is er geen ingebouwde WAF geconfigureerd.  
**Aanbeveling:**
- Login: `slowapi` of Azure Front Door rate limiting; account-lockout na N mislukte pogingen
- Chat: max N berichten per minuut per WebSocket-verbinding; max berichtlengte

---

### S6 — JWT-token zichtbaar in query parameter ❌ Open

**Locatie:** `server.py` — `chat_websocket(token: str | None = Query(...))`  
**Probleem:** Browsers sturen WebSocket-verbindingen als HTTP Upgrade; custom headers zijn niet toegestaan in de browser WebSocket API. Daardoor wordt het token als `?token=...` meegegeven. Query parameters verschijnen in:
- Azure App Service access logs
- Reverse proxy access logs
- Browsertabs van teamleden die screenshots delen

**Aanbeveling (medium termijn):** Na verbinding openen een eerste `{"action": "auth", "token": "..."}` bericht sturen in plaats van query param. Vereist aanpassing in `useChat.js` en `useDashboardChat.js` én in de server-side WebSocket handler.

---

### S7 — Geen maximale inputlengte op chatberichten ❌ Open

**Locatie:** `server.py` regel 348 — `content = msg.get("content", "").strip()`  
**Probleem:** Een gebruiker kan een bericht van willekeurige lengte sturen. Een extreem lang bericht (bijv. 500k tokens) leidt tot hoge LLM-kosten en trage respons.  
**Aanbeveling:** Begrenzing op bijv. 4000 tekens:
```python
content = msg.get("content", "").strip()[:4000]
```

---

### S8 — CORS staat standaard op `*` ❌ Open (configuratie)

**Locatie:** `server.py` — `os.getenv("CORS_ORIGINS", "*")`  
**Probleem:** Als `CORS_ORIGINS` niet is ingesteld (bijv. lokale dev of verse Azure-deploy), accepteert de API cross-origin verzoeken van elke website.  
**Actie voor productie:** Stel in Azure App Service → Configuration:
```
CORS_ORIGINS=https://onderwijsdata-chat.azurewebsites.net
```
Voor lokale dev: `CORS_ORIGINS=http://localhost:5173`

---

### S9 — JWT in localStorage ℹ️ Geaccepteerd

**Locatie:** `frontend/src/auth.js`  
**Probleem:** localStorage is toegankelijk via JavaScript (XSS-vector). Alternatieven zoals `httpOnly` cookies zijn robuuster.  
**Waarom geaccepteerd:** De CSP-header (`script-src 'self' 'unsafe-inline'`) beperkt XSS sterk. Een `httpOnly` cookie-oplossing vereist significante refactor en introduceert CSRF-risico's. Acceptabel risico voor de huidige doelgroep (interne gebruikers).  
**Heroverwegen bij:** publieke toegang of gevoeliger data.

---

### S10 — Sessie-timeout 24 uur ℹ️ Instelbaar

**Locatie:** `auth.py` — `_TOKEN_TTL = 24 * 3600`  
**Instellen via env var:**
```
SESSION_TTL_HOURS=8
```
24u is redelijk voor een intern professioneel tool. Verkort naar 8u (werkdag) bij strengere beveiligingseisen.

---

### S11 — Tool-enumeratie via LLM ℹ️ By design

**Aangetroffen in:** quickscan A3  
**Bevinding:** Het LLM beantwoordt vragen als "welke tools heb je?" met een accurate lijst van beschikbare functies.  
**Beoordeling:** De toolnamen en beschrijvingen zijn niet geheim; ze staan ook in de open source repository. Het LLM beperkt zich tot de aangeboden tools en kan geen willekeurige code uitvoeren. Geaccepteerd.

---

### S12 — Dependency-kwetsbaarheden ✅ Scanning in CI

**Fix:** GitHub Actions workflow voert bij elke deploy uit:
- `pip-audit -r requirements.txt` — Python packages
- `npm audit --audit-level=high` — npm packages

Beide zijn informational (blokkeren deploy niet). Output is zichtbaar in Actions logs. Bij een nieuwe bevinding: updaten of expliciet supprimeren met documentatie.

---

## Aanbevelingen voor volgende stap

1. **S4 oplossen** — generieke fallback + server-side logging (klein, hoge waarde)
2. **S5 aanpakken** — rate limiting op login en max berichtlengte (S7)
3. **S8 instellen** — CORS_ORIGINS in Azure App Service production config
4. **Grondiger pentest** (aanbeveling Alan Berg punt 6) — na bovenstaande fixes, met focus op: WebSocket aanvalsoppervlak, prompt-injection via datapayloads, uitgebreidere ZAP-scan van geauthenticeerde sessie
