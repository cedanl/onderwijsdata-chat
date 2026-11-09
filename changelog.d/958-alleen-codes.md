### `koppelbaar_via` noemt alleen codes; een naam in `relatie` draagt een waarschuwing (#958)
- `search_catalog` en `dataset_details` noemen in `koppelbaar_via` alleen codesleutels (brin, croho, crebo, gemeente,
  provincie, schooljaar, …). `instellingsnaam` en `gemeentenaam` staan er niet meer in: op een naam plant het model
  geen koppeling tussen bronnen. Het catalogusrecord houdt ze wel in `_sleutels`.
- `relatie` mag nog op een naam koppelen, als zwakke sleutel. Elke sleutelkolom en koppelkandidaat op een naam heeft
  een `waarschuwing`: de spelling verschilt per bron en na een fusie of naamswijziging past een oude naam niet meer.
  Koppel liever op een code; koppel je toch op naam, controleer dan welke rijen geen match hebben.
- Pakket `onderwijsbronnen`: `Sleutel.op_naam` markeert de twee namen.
