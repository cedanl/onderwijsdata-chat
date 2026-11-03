### Log-hardening, laatste restpunten van #502: ook de data-, login- en zoekfouten zonder traceback op INFO+ (#819)
- De meldingen "… niet beschikbaar" van de arbeidsmarkt- en dashboarddata (`data/dashboard.py`), het
  instellingsregister en de adreslijst, een onleesbare sectormapping, een mislukte OIDC-uitwisseling bij het
  inloggen en een fout in `search_catalog` noemen op WARNING en ERROR alleen het type en een kenmerk
  (`fout_len=… fout_hash=…`). De traceback, die de request-URL of de zoekvraag kan citeren, staat op DEBUG.
- Een test houdt alle productiecode aan die regel: geen `exc_info` of `logger.exception` op INFO en hoger, en geen
  uitzondering zelf in een logregel. De bewuste uitzonderingen staan in de test, met de reden.
