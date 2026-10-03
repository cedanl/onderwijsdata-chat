# UX-audit 2026-10-03T14:00:14.374Z

- omgeving: https://onderwijsdata-chat.test.sdp.surf.nl
- stappen: undefined ok / undefined fout
- findings: undefined · console-errors: undefined

## Stappen
- ✅ **server-endpoints** (1531 ms)
- ✅ **inlogscherm-laden** (3125 ms)
- ✅ **inloggen-verkeerd-wachtwoord** (430 ms)
- ❌ **inloggen** (20071 ms) — page.waitForSelector: Timeout 20000ms exceeded. | Call log: |   - waiting for locator('.navbar') to be visible
- ✅ **onboarding-modal** (60010 ms)
- ❌ **profiel-instellen** (30006 ms) — page.click: Timeout 30000ms exceeded. | Call log: |   - waiting for locator('button[title="Instellingen"]')
- ✅ **startpagina** (1478 ms)
- ❌ **chat-verbinden** (15003 ms) — page.waitForSelector: Timeout 15000ms exceeded. | Call log: |   - waiting for locator('textarea[aria-label="Chatbericht"]') to be visible
- ❌ **vraag: Hoeveel studenten zijn er?** (30003 ms) — page.fill: Timeout 30000ms exceeded. | Call log: |   - waiting for locator('textarea[aria-label="Chatbericht"]')

## Findings
- **[laag] ui** — Geen favicon
- **[hoog] auth** — Geen inlogformulier gevonden op / — URL: https://onderwijsdata-chat.test.sdp.surf.nl/
- **[middel] inloggen** — Stap faalde — page.waitForSelector: Timeout 20000ms exceeded. | Call log: |   - waiting for locator('.navbar') to be visible
- **[middel] profiel-instellen** — Stap faalde — page.click: Timeout 30000ms exceeded. | Call log: |   - waiting for locator('button[title="Instellingen"]')
- **[middel] chat-verbinden** — Stap faalde — page.waitForSelector: Timeout 15000ms exceeded. | Call log: |   - waiting for locator('textarea[aria-label="Chatbericht"]') to be visible
- **[middel] vraag: Hoeveel studenten zijn er?** — Stap faalde — page.fill: Timeout 30000ms exceeded. | Call log: |   - waiting for locator('textarea[aria-label="Chatbericht"]')