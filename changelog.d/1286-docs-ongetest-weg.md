### Documentatie: claims die nog niet door een mens of derde partij zijn getest, staan niet meer op de site
- Weg als pagina: MCP-server, EduGenAI-koppeling en AI-verordening. De MCP-server zelf (`/mcp`, `mcp_server.py`) blijft in de code.
- Niet meer gepubliceerd, wel in de repository (de app, scripts en tests lezen ze): `docs/privacy.md`,
  `docs/product/privacy.md`, `docs/incidenten.md`, `docs/betrouwbaarheid.md` en `docs/product/betrouwbaarheid.md`
  (`exclude_docs` in `mkdocs.yml`). De privacytekst blijft in de app op `/privacy`.
- Uit de overige pagina's: het hoofdstuk Beveiligingsmaatregelen, de secties "Voor auditors", de zin over ONS en
  Statistics Canada, "geen biometrie" en "geen besluit over een persoon", en de verwijzingen naar al het bovenstaande.
- Bijbehorende test `tests/test_docs_mcp_tools.py` weg.

### Documentatie: correcties uit de externe audits van 27-11-2026
- Quickstart: `npm ci` voor de frontend staat erbij, met de waarschuwing dat `make dev` eerst `pkill -f` draait.
- Geen absolute claims meer over snippets ("bij elke tool-aanroep") en getalcontrole ("elk getal"), in docs, README en
  de MCP-vervolgtekst (`VERVOLG_TEKST`).
- `product/over.md` noemt de optionele gelicentieerde bronnen; `hosting.md` beschrijft de `CHAT_USERS`-fallback als
  platte tekst, SQLite als meerlezer/éénschrijver en Node 26; het Gemini-voorbeeld is een plaatshouder.
- Verouderde stempels weg: `Stand: release 2.5.0` en de voorbeeldtag 2.5.0; Inspectie-tellingen als orde van grootte.
- ADR-011 markeert de SRAM-cache als situatie vóór #984; `MAX_HISTORY` is als UI-limiet beschreven.
- Niet-gepubliceerde `privacy.md` en `incidenten.md`: verwijderen is niet "op schijf definitief" (best effort per opslaglaag), het beurtbewijs kan toch persoonsgegevens bevatten en de 72-uurstermijn loopt vanaf kennisname van de instelling.
