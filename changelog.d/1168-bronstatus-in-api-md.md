### `GET /api/bronstatus` staat in de API-referentie (#1168)
- `docs/api.md` noemt nu `GET /api/bronstatus` (openbaar, antwoord `{"niet_live": [...]}` met per bron `bron`, `naam`,
  `tekst` en `laatst_live`) en de alias `/api/version` naast `/version`. Een test legt elk pad uit het OpenAPI-schema
  naast `docs/api.md`, zodat een nieuw eindpunt niet weer ontbreekt.
