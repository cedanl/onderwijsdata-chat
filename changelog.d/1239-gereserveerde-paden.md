### Gereserveerde paden geven een JSON-404 in plaats van de app (#1239)
- `/docs`, `/openapi.json`, `/status`, `/session` en `/user` (en alles eronder) gaven met een gebouwde frontend
  `index.html` met 200, alsof daar iets stond. Zonder echte route geven ze nu 404 `{"detail": "Niet gevonden"}`, net als
  een onbekend pad onder `/api` en `/mcp`. `HEAD` geeft dezelfde 404 zonder body.
- De lijst staat op één plek (`GERESERVEERDE_PADEN` in `frontend_static.py`); `docs/routing.md` noemt de paden en de
  uitzondering van de dashboards (200 met `gevonden: false` voor een onbekende instelling).
