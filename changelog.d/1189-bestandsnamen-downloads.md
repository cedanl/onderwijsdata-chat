### Downloads: eigen bestandsnamen en een eerlijke fout (#1120, #1124, #1125, #1126)
- Twee tabellen uit één dataset onder één antwoord kregen dezelfde CSV-naam, waarna de browser er `(1)` achter zette. Een
  selectie heet nu na de dataset naar haar groepering ("per STUDIEJAAR", anders "selectie") en een korte code van haar
  selectie; de ruwe lading houdt haar naam (#1120).
- De naam van een rapportdownload (HTML, Markdown en Word) is hoogstens 120 tekens, ingekort op een woord. Een titel van
  270 tekens gaf een naam van 281 tekens, die het bestandssysteem bij het opslaan weigerde (#1124).
- Browser en server gebruiken één regel voor die naam: "Commerciële opleidingen" is overal `Commerciele_opleidingen`
  (voorheen `Commerci_le` in de browser), en een emoji geeft één underscore in plaats van twee. Een gedeeld testbestand
  (`tests/fixtures/bestandsnamen.json`) houdt de twee kanten gelijk (#1125).
- Een CSV van een dataset die niet meer in de catalogus staat (of buiten het profiel valt) geeft een 404 met "Deze dataset
  staat niet meer in de catalogus", niet langer een 502 met "DUO gaf de data niet opnieuw". Een echte storing bij de bron
  houdt de 502, en het herstellen van een gesprek stopt niet meer bij zo'n weggevallen dataset (#1126).
