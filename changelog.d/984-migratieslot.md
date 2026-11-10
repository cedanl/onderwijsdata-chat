### Twee pods die samen starten migreren om de beurt (#984, stap 1)
- `init_db` neemt op Postgres een advisory-lock (sessie-niveau) rond het aanmaken van het schema en de migraties. Een tweede
  pod die tegelijk start, wacht tot de eerste klaar is en vindt dan alles al op orde. Eerder konden `CREATE TABLE` en
  `ALTER TABLE` van twee pods door elkaar lopen en de start laten crashen.
- Duurt het wachten langer dan 120 s, dan faalt de start met een duidelijke melding. Mislukt het loslaten van het slot, dan
  gaat de verbinding dicht, zodat Postgres het slot zelf vrijgeeft. Op SQLite (één proces) verandert er niets.
