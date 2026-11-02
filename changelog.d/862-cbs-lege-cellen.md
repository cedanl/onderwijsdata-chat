### Een lege CBS-cel telt als onderdrukt, net als DUO -1 (#862)
- CBS publiceert een onderdrukte of ontbrekende cel als `.`; die kwam als leeg binnen en viel stil weg, terwijl
  alleen DUO-cellen met -1 een melding kregen. Nu legt de app bij het laden van een CBS-tabel haar lege cellen vast
  en reizen ze mee met elke selectie: de tool-output telt ze per jaar, en het Telling-blok onder het antwoord en de
  kop van de CSV-export noemen een totaal over zo'n selectie een ondergrens, in de woorden van CBS. Kolommen met een
  teken (mutatie, saldo, groei) tellen niet mee, zoals bij DUO.
