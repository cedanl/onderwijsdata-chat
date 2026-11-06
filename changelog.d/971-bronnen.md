### Snippets, bronblok en licentie (#971)
- Snippets: de installatieregel in de kop installeert `onderwijsbronnen[analyse]` (pandas en openpyxl) en, bij een
  grafiek, plotly. Zonder die extras faalde een snippet bij `import pandas`, en de financiën van DUO bij het lezen van
  de Excel-bestanden.
- Studiekeuzedatabase: een instellingsnaam zoekt op het begin van een woord, zoals de opleidingsnaam (#960): "school"
  vindt niet meer elke hogeschool.
- Dashboards: het bronblok noemt titel en link ook bij SBB, RIO en de Inspectie; het leest het dataset-ID uit dezelfde
  lijst als de rest van de chat (#967).
- Licentie: voor elke DUO-bron geldt CC0 1.0, volgens de hergebruikverklaring van DUO; ook de accreditatiedatums
  noemen nu CC0 in plaats van CC-BY.
- Pakket `onderwijsbronnen` 0.11.2: de CREBO-cache staat in `~/.cache/onderwijsbronnen` (`ONDERWIJSBRONNEN_CACHE`);
  `RIODATA_CACHE` en `~/.cache/riodata` werken nog.
