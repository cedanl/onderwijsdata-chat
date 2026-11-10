### De meldingen van de controles staan niet meer in het bewijs per antwoord (#983)
- De kolom `controle` in `beurtbewijs` (#876) is weg. Alleen de feedbacktrace las haar, en die is verwijderd.
  `init_db` haalt de kolom bij de start weg: op PostgreSQL met `DROP COLUMN IF EXISTS`, op SQLite met `DROP COLUMN`
  als de kolom er nog is. Dat is idempotent.
- De chatroute geeft de meldingen van `message_end` niet meer door aan de rij, en de export van "Mijn gegevens" heeft
  bij `beurtbewijs` geen `controle` meer. De meldingen zelf blijven gewoon onder het antwoord staan.
- De rij met de tekst-hash blijft: na heropenen telt een eerder antwoord alleen als bewijs voor de getalcontrole als
  het zo'n rij heeft.
- De privacytekst (app en `docs/privacy.md`), `docs/api.md` en ADR-009 zijn bijgewerkt.
