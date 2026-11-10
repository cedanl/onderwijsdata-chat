### De tijdslimieten tellen in Postgres, zodat meerdere pods één limiet delen (#984, stap 1)
- Login-, bericht-, feedback- en `/mcp`-limiet (`core/rate_limit.py`) tellen in de tabel `rate_limit_hits` in plaats van
  in het geheugen van de pod. Twee pods vormen zo samen één limiet, en een herstart zet niemand op nul. De sleutel (een
  gebruikersnaam of adres) staat er alleen als sha256 in; verlopen pogingen worden bij het opstarten en eens per venster
  opgeruimd.
- Is de database niet bereikbaar, dan telt de limiet tijdelijk per pod (met een waarschuwing in het log, hooguit eens per
  minuut per limiet) in plaats van dat niemand meer kan inloggen of chatten. Zonder Postgres (lokaal op SQLite) blijft
  alles in het geheugen.
- Nog per pod: de gelijktijdigheidstellers (`core/gelijktijdig.py`), de SRAM-gebruikerscache en de herlaadvlag; dat zijn
  de volgende stappen van #984. Opschalen naar twee pods kan pas als die ook gedeeld zijn.
