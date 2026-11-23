### Een mislukte databasestart noemt de oorzaak in het log (#1155)
- De ERROR-regel `Failed to initialize database` noemde alleen het type en een hash, dus een pod in CrashLoopBackOff
  vroeg om `LOG_LEVEL=DEBUG` (dat zet ook vraag- en antwoordtekst in het log). Nu staat er een vaste, veilige oorzaak:
  `psycopg2 ontbreekt: installeer het met uv sync --extra postgres`, verbinding geweigerd, time-out, hostnaam onbekend,
  authenticatie mislukt, database bestaat niet, ongeldige URI, TLS-verbinding mislukt, of bij SQLite het pad dat niet
  te openen of te beschrijven is. Host, poort, gebruiker, wachtwoord en databasenaam staan er nooit in; de fouttekst
  zelf blijft op DEBUG. Een fout zonder herkenbare categorie houdt type en kenmerk.
