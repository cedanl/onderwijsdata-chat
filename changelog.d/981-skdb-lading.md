### Studiekeuzedatabase: welke export de app las, in bronregel, CSV en snippet (#981)
- Bij elke lading van de Studiekeuzedatabase legt de app versie, exportdatum, laaddatum en de sha256 van het
  opgehaalde bestand vast. De bronregel onder het antwoord en op het dashboard Opleidingen noemt ze ("export van
  2026-11-06, opgehaald op 2026-11-09, sha256 …"); de CSV-kop en het manifest noemen de volle sha256, zoals de md5
  van een DUO-bestand.
- De snippet leest nog steeds de export van vandaag (LCSK levert geen oudere), maar zijn kop noemt nu de export die de
  app las, en hij waarschuwt als hij een andere leest: dan kunnen de cijfers afwijken.
- Nog open: of de snippet een export mag lezen die de gebruiker zelf bewaarde, zodat hij dezelfde cijfers geeft.
