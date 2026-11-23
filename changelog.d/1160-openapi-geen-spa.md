### De SPA-route staat niet meer in het OpenAPI-schema (#1160)
- De route die `index.html` voor elk ander pad geeft, stond als `GET /{full_path}` ("Serve Spa") in
  `/api/openapi.json` en in `/api/docs`. Het is geen API-eindpunt en staat er niet meer in; de app-shell blijft op elk
  onbekend GET-pad `index.html` geven.
