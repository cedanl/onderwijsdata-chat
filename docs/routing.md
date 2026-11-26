---
icon: lucide/route
---

# Routing: app-shell of JSON

Met een gebouwde frontend (`frontend/dist`) serveert de server ook de React-app. Een pad dat geen eigen route heeft,
krijgt `index.html` met 200: de app kiest dan zelf de pagina (`/chat`, `/rapporten`, `/dashboards/landelijk`). Dat staat
in `frontend_static.py`.

## Gereserveerde paden

Een paar paden geven nooit de app-shell (`GERESERVEERDE_PADEN` in `frontend_static.py`, #482, #1239). Zonder echte
route antwoorden ze met 404 en `{"detail": "Niet gevonden"}`, ook alles eronder:

| Pad | Waarom gereserveerd |
|---|---|
| `/api` en `/api/…` | De REST-API ([API](api.md)): een typfout in een API-pad hoort een fout te geven, geen HTML (#482) |
| `/mcp` en `/mcp/…` | De MCP-server ([MCP](mcp.md#over-http-mcp-in-de-app)); `/mcp` en `/mcp/` hebben een eigen route in `server.py`, ook als MCP uit staat (dan JSON-404, #1215) |
| `/docs` | Hier zoeken clients Swagger UI; die is er niet (#1161) |
| `/openapi.json` | Hier zoeken clients het schema; dat staat onder `/api/openapi.json` |
| `/status`, `/session`, `/user` | Namen die op een API lijken; scanners en clients die ze proberen, horen geen 200 |

Wat er voor alle gereserveerde paden geldt:

- `HEAD` geeft dezelfde 404, zonder body.
- Een andere methode (`POST`, `PUT`, `PATCH`, `DELETE`) geeft ook 404, geen 405 (#1156).
- Een echte route op zo'n pad wint: de router neemt de eerste route die past, en de gereserveerde paden staan pas na alle
  routes van de app. Zo geeft een app met het schema op `/openapi.json` gewoon het schema.
- Alleen het hele segment telt: `/apidocs`, `/users` of `/statusbalk` zijn gewone paden van de app-shell.

De frontend heeft geen pagina met een van deze namen. Komt er een, kies dan een andere naam of haal het pad uit de lijst
(met een test in `tests/test_frontend_static.py`).

## Uitzondering: dashboards met een onbekende instelling

De dashboard-eindpunten onder `/api/dashboard/` geven voor een instelling die ze niet kennen geen 404, maar 200 met
`gevonden: false` (bij `regio` en `opleidingen` met suggesties in `beschikbare_instellingen`). Het pad bestaat; alleen
de gevraagde instelling niet, en het dashboard toont dan de suggesties. Zie [Dashboards](dashboards.md). Een bron die niet laadt, geeft 503.
