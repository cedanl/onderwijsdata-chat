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
- **Ladder test → playground:** test volgt main; playground pint een release en gaat via promotie-MR (`docs/promoten.md`)
- Secrets management (SOPS encryption, LLM boundaries)
- CI/CD pipeline (stages, environments)

**Ladder promotion (Flux-based):**
- Main push → test auto-deploy via CI (open range `>=0.0.1-0.0`)
- Tag `X.Y.Z` (zonder `v`) → publiceert alleen chart + GitHub-mirror, deployt niets
- `chore/promote-playground` MR → pin in `manifests/playground/helmrelease.yaml` → Flux installeert die release
- development en production doen niet mee

## Deploy & Verificatie

Na een promotie-MR reconcilet Flux playground op de gepinde versie.

```bash
curl https://<environment-url>/health   # {"status":"ok"}
curl https://<environment-url>/version  # {"version":"x.y.z"}
```

## Data Context

- **UWV Open Match**: Frozen snapshot May 2023 (no live vacancy data)
- **DUO sector classification**: HO uses `ONDERDEEL`, MBO uses `HOOFDGROEP NAAM`
- **CBS versioning**: Preliminary figures can be revised; check `_laatste_update`
