### Geen lege Swagger UI en ReDoc meer (#1161)
- Lokaal, op development en op test bleven `/api/docs` en `/redoc` leeg: ze laadden hun scripts van
  `cdn.jsdelivr.net`, die de CSP blokkeert. De pagina's zijn weg; het OpenAPI-schema blijft op `/api/openapi.json`
  in die omgevingen en is in elke viewer te openen. De CSP is niet versoepeld.
