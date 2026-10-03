# UX-audit

Playwright-script dat als een gebruiker door de app klikt en per stap vastlegt
wat er gebeurt: screenshots, console-fouten, netwerkfouten, WebSocket-frames,
downloads en timings. Elke stap is zacht — een mislukte stap wordt genoteerd en
de audit loopt door, zodat één kapotte feature de rest niet verbergt.

## Lokaal

```bash
cd audit
npm install
npx playwright install --with-deps chromium

AUDIT_BASE_URL=https://onderwijsdata-chat.test.sdp.surf.nl \
AUDIT_USER=demo \
AUDIT_PASS=... \
  node run-audit.mjs
```

Uitvoer in `audit/out/` (niet in git):

| Bestand | Inhoud |
|---|---|
| `report.json` | Alle stappen, findings, endpoints, console- en netwerkfouten, metrics |
| `shots/*.png` | Eén screenshot per stap |
| `downloads/` | Wat de app liet downloaden (CSV, …) |
| `network.har` | Alle HTTP-verkeer |
| `trace.zip` | Playwright-trace (`npx playwright show-trace audit/out/trace.zip`) |

## In CI

`.github/workflows/ux-audit.yml` draait hetzelfde script op een runner (die wél
bij de testomgeving kan) en publiceert de uitvoer als artifact
`ux-audit-resultaten`. Benodigde secrets: `AUDIT_BASE_URL`, `AUDIT_USER`,
`AUDIT_PASS`.

## Wat het afloopt

Inlogscherm (ook met fout wachtwoord) → inloggen → onboarding → profiel
(instelling, functie, thema) → startpagina → chat: vage vraag (scopevraag),
specifieke vraag, redeneerkaart en snippets, CSV-export, kopieerknop, stoppen,
vraag tijdens een lopend antwoord (`busy`) → suggestievragen, model-picker,
gespreksgeschiedenis (hernoemen, heropenen na reload) → rapport genereren,
feedback geven (en dubbel versturen) → rapportenpagina → dashboards (vast,
genereren, verwijderen) → databronnen-modal → 404 → thema → mobiel viewport →
a11y-sweep → uitloggen → login-rate-limit.
