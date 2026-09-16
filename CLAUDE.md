# CLAUDE.md

Richtlijnen voor werk aan deze repository. **Zie `Agents.md` voor alle werkwijze-richtlijnen.**

## Project Context

**EDUdata** is een AI-assistent voor open Nederlandse onderwijsdata (CBS, DUO, RIO). Gebruikers stellen vragen, de app haalt data op en genereert dashboards. Demo-fase: geen Entra ID, geen IP-restricties.

## Tech Stack

- **Backend**: FastAPI, WebSocket per sessie, SQLite persistentie
- **Frontend**: React, WebSocket-connection
- **Tools**: CBS (StatLine), DUO (onderwijs), RIO (arbeidsmarkt)

## Werkwijze & richtlijnen

**→ Zie `Agents.md`** voor:
- Feature development (TDD, modularity, narrative commits)
- Git workflow (cherry-pick to GitHub, remote management)
- Deployment & versioning (tag promotion: vX.0.0 → playground/prod)
- Secrets management (SOPS encryption, LLM boundaries)
- CI/CD pipeline (stages, environments)

## Deploy & Verificatie

Push naar `main` → Azure Web App build + deploy.

```bash
curl https://onderwijsdata-chat.azurewebsites.net/health   # {"status":"ok"}
curl https://onderwijsdata-chat.azurewebsites.net/version  # {"version":"x.y.z"}
```

## Data Context

- **UWV Open Match**: Frozen snapshot May 2023 (no live vacancy data)
- **DUO sector classification**: HO uses `ONDERDEEL`, MBO uses `HOOFDGROEP NAAM`
- **CBS versioning**: Preliminary figures can be revised; check `_laatste_update`
