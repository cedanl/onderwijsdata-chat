### Opleidingen in het hbo en wo uit de Studiekeuzedatabase van LCSK, op test en playground (#957)
- Nieuwe tool `get_studiekeuze`: per opleiding van een hogeschool of universiteit het oordeel van studenten (NSE) naast
  het landelijke oordeel over dezelfde studie, studenten en eerstejaars, doorstroom naar jaar 2, diplomarendement,
  numerus fixus met capaciteit en wettelijk collegegeld; per landelijke studie de arbeidsmarkt van de SOI-rubriek; de
  numerus-fixuslijst; en de doorstroom van mbo-4 naar hbo en van bachelor naar master. Selecteren, sorteren, afronden en
  het landelijke oordeel doet de code; een sortering op een cijfer heet altijd een rangorde op één cijfer, nooit een
  kwaliteitsoordeel. De verantwoording daarvan staat in de documentatie (Databronnen).
- Alleen hbo en wo: een vraag over een mbo-instelling krijgt een vaste melding. Een leeg veld blijft leeg (geen 0); bij
  minder dan 30 respondenten noemt het antwoord het oordeel onzeker.
- Elke uitkomst noemt onder het antwoord de verplichte bronvermelding van LCSK, met het versienummer van de export en
  een link naar studiekeuze123.nl/studiekeuzedata.
- Alleen waar de sleutel `STUDIEKEUZEDATABASE_API_KEY` staat (test en playground); daar ook vier suggestievragen op het
  startscherm (categorie Studiekeuze) en een rij LCSK in het databronnenvenster. Development en productie zien de bron
  niet.
- Pakket `onderwijsbronnen`: nieuwe bron `skdb` (`skdb.load`, `skdb.lees`, `skdb.haal_op` en de overzichten) die de
  dagexport met de eigen sleutel van de gebruiker ophaalt; er staat geen data van LCSK in de repo of het pakket. Het ID
  `skdb:studiekeuzedatabase` staat in het ID-contract en, waar de sleutel staat, in de zoekcatalogus van de chat.
