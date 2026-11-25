### De SRAM-gegevens in de privacytekst, de export en het verwijderen (#1230, #1209)
- De privacypagina zegt waar naam, organisatie en instelling uit SRAM staan: in de database van de server, ten hoogste
  de sessieduur (standaard 24 uur), en eerder weg bij uitloggen of als je al je gegevens verwijdert. Er stond nog "in
  het geheugen van de server" (#1230).
- "Exporteer al mijn gegevens" bevat nu ook het bewaarde SRAM-profiel: de nieuwe sleutel `oidc_gebruiker`, één rij met
  `gegevens` en `expires_at`, zonder het pseudoniem; zonder (geldige) rij een lege lijst. `schema_version` blijft 1
  (#1209).
- "Verwijder al mijn gegevens" wist het SRAM-profiel in dezelfde transactie als de rest, en `verwijderd` telt het mee
  (`oidc_gebruiker`). Faalt de transactie, dan blijft ook het profiel staan en blijven de sessies geldig; eerder ging
  het er pas na de transactie apart af (#1209).
