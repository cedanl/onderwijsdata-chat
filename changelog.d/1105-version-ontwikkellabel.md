### Een lokale build meldt zich niet meer als de release (#1105)
- Zonder `APP_VERSION` (lokaal, `make dev`, de MCP-server via stdio) gaf `/version` de versie uit `pyproject.toml`, dus
  code die honderden commits na de laatste tag lag heette "2.8.0", net als playground. Het label is nu
  `<pyproject>+dev.<korte commit>` (`2.8.0+dev.5e29298b`; zonder git of repo `2.8.0+dev`). Met `APP_VERSION` verandert
  er niets: `version` blijft de chartversie = de tag, `commit` de gebouwde commit en `catalogus` de volledige commit.
- MCP `serverInfo.version` (HTTP en stdio) en het `app`-veld in het manifest van een rapport gebruiken hetzelfde label,
  via één functie (`core/appversie.py`) in plaats van drie kopieën van de pyproject-terugval.
