### API: een POST, PUT, PATCH of DELETE op een onbekend pad geeft een 404 (#1156)
- Met een gebouwde frontend (productie) gaf elke niet-GET op een pad dat niet bestaat een `405` met `Allow: GET`,
  omdat de catch-alls GET-routes zijn. Een client dacht dan dat het eindpunt bestond, zoals het in #983 verwijderde
  `/api/answer-feedback`. Nu geeft elke methode op een onbekend pad de JSON-404 "Niet gevonden"; een pad dat wel
  bestaat (`POST /health`, `DELETE /api/config`) houdt zijn 405.
- `tests/test_antwoordfeedback_weg.py` bouwt de app nu expliciet zonder en met een gebouwde frontend, zodat de test
  niet meer afhangt van of `frontend/dist` er staat.
