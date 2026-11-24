### Het OpenAPI-schema noemt de echte versie (#1157)
- `info.version` in `/api/openapi.json` was de FastAPI-standaard `0.1.0`; het is nu de versie die `/version` geeft (de
  release uit het chart, anders `pyproject.toml`). Die versie komt uit één functie, `core.appversie.app_versie`, die ook
  het manifest en de MCP-server gebruiken in plaats van elk een eigen kopie van de leesregel.
