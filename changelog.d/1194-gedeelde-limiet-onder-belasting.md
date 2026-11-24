### Een gedeelde limiet telt een poging niet meer dubbel (#1194)
- Faalde het opruimen van verlopen pogingen nadat een poging al in de database telde (inloggen, berichten, feedback,
  Word-export, `/mcp`), dan telde die poging ook nog in het geheugen van de pod. Dat gebeurt niet meer.
- Een vergrendelde SQLite-database (alleen lokaal en in de tests) is geen storing meer: de poging gaat tot twee keer
  opnieuw, samen hooguit 0,3 s wachten, in plaats van meteen per pod te tellen.
- Is de database echt weg, dan telt elke limiet zoals voorheen tijdelijk per pod: liever een ruimere limiet dan geen
  inlog of bericht meer voor iedereen.
