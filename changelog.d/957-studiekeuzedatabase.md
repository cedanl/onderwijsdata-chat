### Opleidingen in het hbo en wo uit de Studiekeuzedatabase van LCSK, op test en playground (#957)
- Nieuwe tool `get_studiekeuze`: per opleiding van een hogeschool of universiteit het oordeel van studenten (NSE) naast
  het landelijke oordeel over dezelfde studie, doorstroom naar jaar 2, diplomarendement en numerus fixus met
  capaciteit; per landelijke studie de arbeidsmarkt van de SOI-rubriek en het ROA-opleidingstype; de
  numerus-fixuslijst; en de doorstroom van mbo-4 naar hbo en van bachelor naar master. Selecteren, sorteren, afronden en
  het landelijke oordeel doet de code; sorteren kan alleen op naam, NSE-oordeel of doorstroom naar jaar 2, en zo'n
  sortering heet altijd een rangorde op één cijfer, nooit een kwaliteitsoordeel. De verantwoording daarvan staat in de
  documentatie (Databronnen).
- Weergave `toelating`: per opleiding de wettelijke vooropleidingseisen voor havo, vwo en mbo (uit de regeling RATHO,
  via LCSK), met de instellingen die dezelfde eisen noemen. Een vraag als "Welk profiel heb ik met havo nodig voor
  Verpleegkunde?" krijgt daarom niet meer de vaste uitleg dat po en vo buiten het profiel vallen.
- Volgens de afspraken over de leidende bron (#878) geeft de tool geen aantallen studenten en eerstejaars (daarvoor
  blijft DUO de bron), geen wettelijk collegegeld (`get_collegegeld`), geen accreditatie (`get_accreditatie`) en geen
  aansluiting studie-baan (ROA). Bij de NSE-thema's zegt het antwoord dat het aantal respondenten per thema onbekend is.
- Alleen hbo en wo: een vraag over een mbo-instelling krijgt een vaste melding. Een leeg veld blijft leeg (geen 0); bij
  minder dan 30 respondenten noemt het antwoord het oordeel onzeker.
- Elke uitkomst noemt onder het antwoord de verplichte bronvermelding van LCSK (leveringsvoorwaarden v25.1), met het
  versienummer van de export, het NSE-jaar, de oorspronkelijke bron van de cijfers (zoals 1cijferHO, CBS-microdata,
  RATHO of Studielink) en een link naar lcsk.nl/over-ons/studiekeuzedata-raadplegen.
- Alleen waar de sleutel `STUDIEKEUZEDATABASE_API_KEY` staat (test en playground); daar ook vier suggestievragen op het
  startscherm (categorie Studiekeuze) en een rij LCSK in het databronnenvenster. Development en productie zien de bron
  niet.
- Pakket `onderwijsbronnen`: nieuwe bron `skdb` (`skdb.load`, `skdb.lees`, `skdb.haal_op` en de overzichten, waaronder
  `skdb.toelating`) die de dagexport met de eigen sleutel van de gebruiker ophaalt; er staat geen data van LCSK in de
  repo of het pakket. Het ID `skdb:studiekeuzedatabase` staat in het ID-contract en, waar de sleutel staat, in de
  zoekcatalogus van de chat.
