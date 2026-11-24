### Dashboards: kaart, voorbeeldinstelling, waardentabel en meldingen bij een onbekende instelling (#1079, #1098, #1101, #1102, #1166)
- De kaart "Locaties in de regio" heeft provinciegrenzen als ondergrond, dus ook een uitsnede binnen het land laat zien
  waar de punten liggen. Instellingen in dezelfde plaats zijn één grotere stip met het aantal ernaast; de tooltip en de
  tekst voor schermlezers noemen ze allemaal, en de ster noemt de andere instellingen in haar plaats. De legenda staat
  onder de kaart en de naam van de eigen instelling past op een telefoon binnen het beeld.
- Zonder gekozen instelling zeggen de dashboards (de galerij en elk vast dashboard) dat Hogeschool Utrecht een voorbeeld
  is, met een knop die Instellingen opent. Met een gekozen instelling, of een instelling in de link, verdwijnt de melding.
- "Toon de waarden" bij de tijdreeksen met procentuele verandering (ingeschrevenen, eerstejaars en gediplomeerden per jaar)
  zet de eenheid achter elke waardekolom ("% verandering ten opzichte van het startjaar"), zodat een gekopieerde tabel in
  een spreadsheet niet voor aantallen doorgaat. Een waarde die op nul afrondt staat in elke waardentabel als "0", niet
  als "-0".
- Een instelling die niet in het DUO-bestand van een dashboard staat (zoals Horizon College), krijgt de melding dat ze
  niet in dat bestand staat en dat de naam daarom niet fout hoeft te zijn. Suggesties komen alleen nog bij een tikfout,
  niet meer met namen die alleen het woord "college" delen.
- Een dashboardlading die langer duurt dan 5 seconden (`DASHBOARD_TRAAG_S`) staat met eindpunt en duur in het log. De
  eerste lading na een start duurt zo'n 10-16 s; een opwarmstap is nog niet gebouwd, de afweging staat in
  `docs/dashboards.md`.
