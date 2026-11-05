### Het ongebruikte eindpunt `/api/dashboard/instroom` is weg (#930)
- Geen dashboard riep het aan, en wat het gaf (ingeschrevenen, sectoren, eerstejaars, gediplomeerden, geslacht) staat
  ook in `/api/dashboard/regio`, dat de pagina Mijn instelling gebruikt. Elke aanroep laadde wel DUO-bestanden. Ook de
  MCP-server en de rapporten gebruikten het niet.
- Weg zijn de route, de lader (`load_dashboard`, `load_dashboard_ho`, `load_dashboard_mbo`), de nepdata in
  `demo/record.mjs` en de regels in `docs/api.md` en `docs/dashboards.md`. De tests van die lader toetsen nu het
  regiodashboard.
