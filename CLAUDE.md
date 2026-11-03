# CLAUDE.md

Richtlijnen voor werk aan deze repository. **Zie `Agents.md` voor alle werkwijze-richtlijnen.**

## Project Context

**EDUdata** is een AI-assistent voor open Nederlandse onderwijsdata (CBS, DUO, RIO). Gebruikers stellen vragen, de app haalt data op, beantwoordt met bronnen en maakt op verzoek een rapport; daarnaast zijn er vaste dashboards (mijn instelling, arbeidsmarkt, landelijk). Demo-fase: geen Entra ID, geen IP-restricties.

## Tech Stack

- **Backend**: FastAPI, WebSocket per sessie, PostgreSQL persistentie (SQLite alleen als lokale terugval zonder `POSTGRES_URI`)
- **Frontend**: React, WebSocket-connection
- **Tools**: CBS (StatLine), DUO (onderwijs), RIO (register van instellingen en opleidingen); arbeidsmarkt via UWV en ROA
- **Bronpakketten**: `packages/onderwijsdata` (CBS) en `packages/riodata` (RIO, DUO, UWV, ROA, Inspectie, SBB) als uv-workspace in deze repo (epic #883); één `uv.lock`, na een wijziging aan `packages/` of `pyproject.toml` opnieuw `uv sync`

## Werkwijze & richtlijnen

**→ Zie `Agents.md`** voor:
- Feature development (TDD, modularity, narrative commits)
- Git workflow (GitLab canoniek, GitHub automatische spiegel, remote management)
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
- **Scope**: mbo/hbo/wo only; po/so/vo fail closed, except the ten `VO_CONTEXT` vo sources (9 CBS tables + DUO `voprognoses`), returned by `search_catalog` only when the user's question is about vervolgonderwijs: it names ho (hbo/wo/ho/hogeschool/universiteit, not havo/vwo), or a vo level with mbo/roc or a doorstroom word (vmbo → mbo, "havisten na hun diploma"), or vsv returning to school (`ho_markers.opent_vo_context`); outside the chat the search term decides, and a direct dataset ID loads without it. Labelled "vo-context voor vervolgonderwijs" (epic #554, #877; see `tools/scopeprofiel.py`, `docs/databronnen.md` for the known limits). The mixed CBS tables (`CBS_SECTORFILTER`) load their vo rows, and the typed RIO registers accept vo/vavo types (`SECTORFILTER_VO_CONTEXT`), only when the question also names a vo level or vsv (`ho_markers.vo_deel_poort`, #879, #880); the load keeps that in `KeyMeta.vo_context` and its recipe
