### Definities en bronvergelijking onder het antwoord (#1271)
- **Andere definities (#1256).** Onder een vaste maat staat het getal ook onder de gangbare andere definities:
  personen of inschrijvingen, alleen voltijd, met of zonder extranei. "Hoeveel mbo-studenten waren er in 2024/25?" krijgt
  "**Andere definities:** in 2024/25 telt dit antwoord 475.460; zonder extranei 465.820 (-2,0%)." Elk getal komt uit een
  eigen stap van code, met een citatie; wijkt geen alternatief meer dan 1% af, dan zegt de regel dat andere definities
  hetzelfde beeld geven.
- **Wijkt af van je eigen cijfer? (#1258).** Onder een antwoord met één hoofdgetal kan je een eigen getal invullen. De
  app zet het naast het onze, met het verschil en de bekende redenen uit de teldefinitie, met hun grootte als die uit
  open data volgt. Een reden die de andere kant op werkt (ons getal telt extranei al mee, jouw getal ligt hoger), staat
  er wel, maar verklaart niets. Een punt mag alleen tussen groepen van drie cijfers (475.460): 1.5 wordt geweigerd, geen
  15. Je getal is invoer: het telt nergens als bron.
- **Ter controle met een tweede bron (#1259).** Voor mbo-studenten landelijk zet de app ook het DUO-getal onder het
  CBS-getal, met het verschil en de bekende redenen. Welke maten een paar zijn, staat in een vaste tabel
  (`data/bronparen.toml`); het model kiest geen paar.
- **De vergelijkingsgroep van het dashboard in de chat (#1267).** "Vergelijk met vergelijkbare instellingen" gebruikt de
  groep van Mijn instelling, met dezelfde peers, terugval en hetzelfde gemiddelde; onder het antwoord staat de groep in
  één zin. Een eigen groep kan, en dan zegt het antwoord dat het niet de dashboardgroep is.
- Alle regels staan ook in de export van het gesprek, in het bewijs van de beurt en "Bewijs (JSON)" (de regel in
  `antwoord`, haar stap in `toolstappen`, haar getallen in `citaties`) en (andere definities en kruiscontrole) in het
  definitieblok van het rapport. Het label "Vaste maat" blijft onder zo'n antwoord staan.
