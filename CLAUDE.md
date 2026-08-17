# CLAUDE.md

Richtlijnen voor AI-sessies in deze repository.

## Project

EDUdata is een AI-assistent voor open onderwijsdata. Gebruikers stellen vragen over instellingen, studenten en arbeidsmarkt; de app haalt data op via DUO en UWV en genereert dashboards. De app bevindt zich in een demo-fase voor externe gebruikers — geen Entra ID, geen IP-restricties.

## Stack

- **Backend**: FastAPI (`server.py`), routes in `routes/`, data-logica in `data/`, tools in `tools/`, agent-logica in `agent/`
- **Frontend**: React (`frontend/src/`), WebSocket-verbinding met backend
- **Communicatie**: WebSocket per sessie — sessiestate is per verbinding en stateless bij reconnect
- **Database**: SQLite voor persistentie (`persistence/`)

## Werkwijze

- Modulair en onderhoudbaar — geen tactical tornado, geen god-functies
- Geen hardcoded waarden — gebruik constanten en config
- Ruim dode code en dode elementen op bij aanraken van een bestand
- TDD waar van toepassing; tests staan in `tests/`
- Commits zijn beknopt en in het Engels; `fixes #<nr>` in de body bij bugfixes

## Grenzen

- Lees nooit env var values — controleer alleen existence
- Raak `frontend/package.json` versienummer niet aan; `pyproject.toml` is de enige versiebron
- Geen force push naar `main`

## Deploy & verificatie

Push naar `main` triggert de GitHub Action die bouwt en deployt naar Azure Web App `onderwijsdata-chat` (resource group `cedanl`).

Verifieer na deploy:

```bash
curl https://onderwijsdata-chat.azurewebsites.net/health   # {"status":"ok"}
curl https://onderwijsdata-chat.azurewebsites.net/version  # {"version":"x.y.z"}
```

## Data-context

- **UWV Open Match**: bevroren momentopname mei 2023 — geen actuele vacaturedata beschikbaar
- **DUO sector-indeling**: HO gebruikt `ONDERDEEL` (bv. ECONOMIE, TECHNIEK), MBO gebruikt `HOOFDGROEP NAAM` — deze verschillen zijn relevant bij arbeidsmarkt- en sectorvragen
