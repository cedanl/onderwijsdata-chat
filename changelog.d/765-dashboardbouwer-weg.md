### De dashboardbouwer is weg (#765)
- Besluit A van 30-10: de LLM-gestuurde dashboardbouwer gaat eruit. Weg zijn de bouwer op `/dashboards` ("Nieuw
  dashboard", `DashboardCreator`, `useDashboardChat`), het gegenereerde dashboard (`GeneratedDashboard`,
  `dashboardHtml.js`), de WebSocket-acties `generate_dashboard` en `refresh_dashboard`, `POST /api/dashboard/refresh`,
  `agent/dashboard.py`, `prompts/dashboard.md`, en verversen en reproduceren (`agent/replay.py`,
  `agent/figuurverschil.py`). Wat het rapport ervan gebruikte, staat nu in `agent/datasetcontext.py`.
- De drie vaste dashboards (Mijn instelling, Arbeidsmarkt, Landelijk), `data/dashboard.py`, de vijf
  `GET /api/dashboard/*` en `ENABLE_DASHBOARDS` blijven zoals ze waren: aan op test, uit op playground en productie.
- Een opgeslagen dashboard uit de bouwer wordt niet weggegooid, maar opent niet meer. Op `/dashboards` staat het in een
  lijst om los te verwijderen, en een oude link zegt dat het niet meer opent. Het zit nog in de export van je gegevens
  en valt onder de gewone bewaartermijn.
- Een oude frontend die `generate_dashboard` of `refresh_dashboard` stuurt, krijgt de melding voor een onbekende actie.
