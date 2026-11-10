### Een vervolgantwoord houdt zijn bronregels ook na heropenen (#987)
- Na heropenen van een opgeslagen gesprek kreeg een vervolgantwoord zonder toolaanroep dat de data van de vorige
  databeurt noemde ("het DUO-bestand") geen bronregels meer zodra de server die data niet meer in het geheugen had (een
  herstart, de bovengrens of de actualiteitstermijn): geen DUO-regel, geen versie en verplichte zin van LCSK. De
  bronregels van de geladen tabellen worden nu bij het laden vastgelegd en bewaard in de rij van het antwoord
  (`beurtbewijs`, nieuwe kolom `bronnen`, op SQLite en PostgreSQL vanzelf toegevoegd bij de start). Na heropenen komen
  ze daaruit; een gesprek van vóór deze wijziging valt terug op wat de server nog weet.
- De export van "Mijn gegevens" en de privacytekst noemen de bronregels bij het bewijs per antwoord. Het zijn alleen
  bronlabels en de regels die al onder een antwoord staan: geen data, geen vraagtekst.
