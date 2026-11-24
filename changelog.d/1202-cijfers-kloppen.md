### Cijfers die kloppen: het diploma-gemiddelde, de ROA-editie en de publicatieregel (#1202: #1073, #1091, #1092)
- De arbeidsmarktmatch middelt de gediplomeerden per sector nu over alle drie diplomajaren: een jaar zonder diploma's
  in een sector telt als 0. Eerder deelde het gemiddelde alleen door de jaren met diploma's, zodat de Hogeschool
  Utrecht voor Taal en cultuur op 64 per jaar kwam in plaats van 43 (52 en 76 in twee van de drie jaar). Sectoren die
  er niet elk jaar zijn, krijgen daardoor een lager aanbod en een hogere verhouding (#1073).
- `get_maat` en de MCP-tools `aantallen_per_jaar` en `vergelijk_instellingen` geven bij de publicatieregel nu ook door
  wat het geladen bestand ervan zegt, zoals `get_duo_data` dat al deed: `publicatieregel_status` (bijv. `conflict`
  bij een bestand zonder 4-cellen maar met -1-cellen), `publicatieregel_melding` en `publicatieregel_waargenomen`.
  Zo leest een client de regel '1-4 gepubliceerd als 4' niet meer als waar waar het bestand hem tegenspreekt (#1092).
- De dashboards Arbeidsmarkt en Mijn instelling, `get_roa_benchmark` en de ROA-snippet laden nu de editie van ROA AIS
  2030 die de catalogus de nieuwste noemt: editie 2026 in plaats van 2025. Het SIS-jaar ("SIS 2025") en het thema van
  de prognose komen uit het geladen bestand in plaats van vaste tekst; een editie zonder herkend thema geeft een
  melding in plaats van een lege tabel. Het bronblok van de dashboards, de bronregel in de chat en het venster
  Databronnen noemen dezelfde editie en hetzelfde SIS-jaar. Door editie 2026 verschuiven cijfers, zo is de prognose
  voor bachelors landelijk "redelijk" (was "matig"). In het resultaat van `get_roa_benchmark` heet
  `schoolverlaters_sis_2024` nu `schoolverlaters`, met `editie` en `sis` erbij (#1091).
