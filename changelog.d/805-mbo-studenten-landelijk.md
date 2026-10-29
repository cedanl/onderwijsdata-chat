### Het landelijke aantal mbo-studenten komt elke keer uit dezelfde tabel (#805)
- "Hoeveel mbo-studenten waren er in 2024/25?" gaf in één sessie 474.963 (DUO, het bestand per sectorkamer) en 475.460
  (CBS 85354NED, ook 85353NED): beide juist, met een andere definitie, maar de bron koos het model. Nu is het de vaste
  maat `mbo_studenten_landelijk`: CBS 85354NED, met de leerweg volgens de extranei-standaard (#653, #658) of bol/bbl.
  Onder het antwoord staat de regel "Bron en definitie" met DUO "Mbo-studenten per instelling" als alternatief.
- Een instelling bij een landelijke maat is nu een melding die naar de maat per instelling wijst. Bij
  `deelnemers_ho_landelijk` werd ze stil genegeerd: een aanroep met een hogeschool gaf het landelijke getal terug.
