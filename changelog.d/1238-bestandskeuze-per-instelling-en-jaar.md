### Chat en dashboard geven per instelling en jaar hetzelfde DUO-getal (#1238)
- Voor ingeschrevenen, eerstejaars, inschrijvingen en gediplomeerden in het hbo en wo (DUO p01hoinges, p02ho1ejrs,
  p03hoinschr en p04hogdipl) kiezen de vaste maat in de chat (get_maat) en de dashboards nu per instelling en jaar
  hetzelfde bestand: het bestand met de minste onderdrukte cellen (-1), bij een gelijk aantal het hoogste totaal en bij
  een nog gelijk totaal het eerste bestand van de groep. Tot nu toe nam de chat het opleidingsvorm-bestand over alle
  jaren en telde het dashboard de geslacht-bestanden, met de meeste onderdrukte cellen; voor dezelfde instelling en
  hetzelfde jaar gaven ze zo een ander getal (besluit #1214). De vergelijkingsgroep in de chat (#1267) rekent de eigen
  ingeschrevenen en het peergemiddelde met dezelfde keuze.
- Getallen op de dashboards en in de chat kunnen daardoor een paar studenten verschuiven, meestal omhoog: er tellen
  minder onderdrukte cellen niet mee. Komt een reeks uit meer bestanden, dan noemt de chat het bestand per schooljaar
  onder het antwoord, en het dashboard noemt de gebruikte bestanden in zijn bronblok. Met een opleidingsvorm (voltijd,
  deeltijd, duaal) blijft het opleidingsvorm-bestand de enige keuze: alleen dat bestand heeft die kolom.
- De verdeling naar geslacht op het dashboard komt uit het geslacht-bestand, het enige met geslacht; haar som kan een
  paar studenten van het totaal afwijken.
