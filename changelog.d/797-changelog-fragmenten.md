### Changelog-items als fragment per MR, zodat MR's niet meer op CHANGELOG.md botsen (#797)
- Een MR zet zijn changelog-item niet meer in `CHANGELOG.md`, maar in een eigen bestand
  `changelog.d/<issuenummer>-<onderwerp>.md`, met het kopje en de bullets zoals voorheen. Elke merge zette open MR's
  met een changelog-regel op conflict, en in de merge train viel de tweede MR met zo'n regel eruit.
- Bij een release zet `scripts/changelog.py X.Y.Z` de fragmenten onder `## X.Y.Z — <datum>` (hoogste issuenummer
  bovenaan), met daaronder de items die nog onder "Niet uitgebracht" staan, en verwijdert de fragmenten. `--droog`
  toont de versiesectie zonder iets te schrijven (`docs/promoten.md`, stap 0).
- Een test controleert in elke MR de naam en de vorm van de fragmenten (`tests/test_changelog.py`).
