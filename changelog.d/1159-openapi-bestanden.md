### Bestandseindpunten staan in het OpenAPI-schema met hun echte mediatype (#1159)
- `GET /api/data/csv` staat in `/api/openapi.json` nu als `text/csv` en `POST /api/workbooks/{wb_id}/docx` als het
  Word-mediatype (`application/vnd.openxmlformats-officedocument.wordprocessingml.document`), niet meer als
  `application/json`. `GET /api/mijn-gegevens/export` blijft `application/json`, want dat stuurt de route echt, maar
  staat nu als bijlage (binair, met de header `Content-Disposition`) en niet als JSON-object zonder schema. Een
  gegenereerde client probeert het antwoord daardoor niet meer als JSON te lezen.
