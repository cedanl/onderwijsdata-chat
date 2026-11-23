### API: een tijdstempel buiten 64 bit geeft een 422 in plaats van een 500 (#1129)
- Een `timestamp` in `PUT /api/conversations/{id}` of een `before_ts` in `GET /api/conversations` buiten het bereik
  van een 64-bits geheel getal gaf een `OverflowError` bij de databasebinding en dus een kale 500. Beide hebben nu die
  grens (-2^63 tot en met 2^63 - 1) en krijgen daarbuiten de Nederlandse 422 van #637. Een gewone tijdstempel in
  milliseconden blijft werken.
