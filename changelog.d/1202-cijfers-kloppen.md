### Cijfers die kloppen: het diploma-gemiddelde, de ROA-editie en de publicatieregel (#1202: #1073, #1091, #1092)
- De arbeidsmarktmatch middelt de gediplomeerden per sector nu over alle drie diplomajaren: een jaar zonder diploma's
  in een sector telt als 0. Eerder deelde het gemiddelde alleen door de jaren met diploma's, zodat de Hogeschool
  Utrecht voor Taal en cultuur op 64 per jaar kwam in plaats van 43 (52 en 76 in twee van de drie jaar). Sectoren die
  er niet elk jaar zijn, krijgen daardoor een lager aanbod en een hogere verhouding (#1073).
- `get_maat` en de MCP-tools `aantallen_per_jaar` en `vergelijk_instellingen` geven bij de publicatieregel nu ook door
  wat het geladen bestand ervan zegt, zoals `get_duo_data` dat al deed: `publicatieregel_status` (bijv. `conflict`
  bij een bestand zonder 4-cellen maar met -1-cellen), `publicatieregel_melding` en `publicatieregel_waargenomen`.
  Zo leest een client de regel '1-4 gepubliceerd als 4' niet meer als waar waar het bestand hem tegenspreekt (#1092).
