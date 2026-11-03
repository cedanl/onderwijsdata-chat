### Onder een tabel met "niet beschikbaar"-cellen staat wat die cellen zijn (#811)
- Toonde een antwoord alleen een tabel op een DUO-selectie met onderdrukte cellen, zonder totaal in de tekst, dan
  stond nergens waarom cellen "niet beschikbaar" waren: de Ondergrens-regel in het Telling-blok verschijnt alleen als
  een getal in de tekst op zo'n selectie rust. Nu zet de app direct onder elke tabel met een lege cel een vaste
  voetnoot uit code: "Niet beschikbaar: in het DUO-bestand staat hier -1 (onderdrukte cel: DUO publiceert kleine
  aantallen niet, geen telwaarde)." Bij een lege CBS-cel staan er de woorden van CBS. Zonder onderdrukte cel in de
  data van de beurt komt er geen noot.
