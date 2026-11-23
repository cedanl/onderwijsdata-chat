### SQLite: verwijderde gesprekstekst staat ook niet meer op schijf (#1116)
- Na het verwijderen van een gesprek, van al je gegevens of na de nachtelijke opschoning stond de volledige berichtenlijst
  nog leesbaar in het SQLite-bestand: SQLite maakt vrijgekomen pagina's niet leeg. Dat is alleen de lokale terugval (SDP
  draait op PostgreSQL), maar wie de app op een laptop draait en gegevens "definitief" verwijdert, hield ze op schijf.
- Elke SQLite-verbinding zet nu `PRAGMA secure_delete=ON`, en na elke wijziging leegt de app het `-wal`-bestand (zonder te
  wachten op een lezer die nog bezig is). Een test zoekt de tekst als bytes in het databasebestand en de `-wal`, ook met
  een tweede verbinding open.
- De privacytekst in `docs/privacy.md` zegt wat de app doet; de back-ups van de beheerder blijven erbuiten.
