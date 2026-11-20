### Tokenbudget per gebruiker (#678)
- Elke vraag, verduidelijking en elk rapport telt mee voor een dag- en een maandbudget per gebruiker, gewogen naar wat
  het model kost (nieuwe invoer x1, uit de cache gelezen x0,1, cache geschreven x1,25, uitvoer x5). Standaard rond de
  75 typische vragen per dag (`TOKENBUDGET_DAG=1500000`) en tien keer zoveel per maand (`TOKENBUDGET_MAAND`); `0` zet
  een grens uit.
- Boven het budget krijgt de gebruiker een melding wanneer het weer kan, en start er geen modelaanroep. Gesprekken en
  rapporten blijven gewoon te openen.
- De telling staat in de database (`tokengebruik`, per dag, onder een hash van de accountnaam, 62 dagen), gedeeld door
  alle pods. Faalt de database, dan gaat het chatten door.
