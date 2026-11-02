### `bron:ping` controleert elke dataset, en de ijkwaarden hebben een eigen geplande job (#869)
- Naast de zes pings loopt `bron:ping` nu elke CBS-tabel, elk DUO-bestand en elk RIO-register langs die de chat kan
  opvragen: CBS-status en `Modified` tegen de catalogus, de kolommen van elk DUO-bestand tegen de schema-snapshot, en
  één record per RIO-register. Een afwijking staat als waarschuwing in de log en in het artefact
  `bronping-sweep.json`; de job wordt er niet rood van.
- Nieuwe CI-job `ijkwaarden:ververs` draait `scripts/ijkwaarden.py` in een eigen schema (variabele
  `IJKWAARDEN_VERVERS=1`) en zet bij een verschil een aanwijzing in de log. Het schema zelf maakt de beheerder aan
  (`docs/operatie.md`).
