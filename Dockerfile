# Stage 1: Build React Frontend
FROM node:26-alpine@sha256:6bd9ab43c0ec0190ca7b2d193906cb8b7edf6e7f4afa43ddeccd6452710bffb5 AS frontend-builder

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/src ./src
COPY frontend/index.html ./
COPY frontend/public ./public
COPY frontend/vite.config.js ./
COPY frontend/eslint.config.js ./

RUN npm run build

# Stage 2: Python-afhankelijkheden. De compiler staat alleen hier; het runtime-image krijgt alleen de .venv (#681).
# git is er niet meer bij nodig: het bronpakket onderwijsbronnen staat als workspace-lid in packages/ en komt
# niet meer als git-afhankelijkheid van GitHub (#885, #910).
FROM python:3.14-slim@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f AS python-builder

# uv gepind op versie en digest, zodat de build reproduceerbaar is; Renovate werkt hem bij.
COPY --from=ghcr.io/astral-sh/uv:0.13.8@sha256:5cc1805e2426484abca4ad46ea783bab281fdb225fd82d8ce6d66a81254bac85 /uv /usr/local/bin/uv

WORKDIR /app

# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
# De workspace-leden vóór uv sync: zonder packages/ vindt uv de leden uit uv.lock niet. De catalogusdata (±14 MB JSON en
# YAML) zit in src/ van elk pakket en gaat met de wheel de .venv in.
COPY packages/ ./packages/

# --extra postgres: every SDP deployment target (test/playground/production)
# configures a real POSTGRES_URI; psycopg2-binary needs to be present in the
# image even though it's an optional extra (lokaal draait de app zonder POSTGRES_URI op SQLite).
# UV_PYTHON_DOWNLOADS=never: de .venv hoort bij de python van dit base-image, dezelfde als in stage 3.
# --no-editable: de workspace-leden komen als gewone pakketten in de .venv. Editable zou naar /app/packages wijzen, en
# stage 3 neemt alleen de .venv mee, niet packages/ (#885).
# mcp is een gewone dependency (#938), geen extra: litellm importeert hem bij elke aanroep met tools, en /mcp (#706)
# draait erop. De import erachter laat de build falen als het image hem mist.
RUN UV_PYTHON_DOWNLOADS=never uv sync --frozen --no-dev --no-install-project --no-editable --extra postgres \
    && .venv/bin/python -c "import mcp.types"

# Stage 3: runtime, zonder compiler, git, pip-uv of uv (#681)
FROM python:3.14-slim@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f

# De gebruiker eerst, zodat elke COPY hieronder de bestanden meteen aan hem geeft (--chown). Een `chown -R /app`
# aan het eind deed er op de CI-runner 11 minuten over (650 s van een build van 13,5 min) en zette elk bestand
# nog eens in een eigen laag. /app zelf (WORKDIR maakt hem als root) krijgt hij zonder -R: dat kost niets.
RUN useradd --create-home --uid 1000 appuser && mkdir -p /app && chown appuser:appuser /app

WORKDIR /app

COPY --chown=appuser:appuser --from=python-builder /app/.venv ./.venv

COPY --chown=appuser:appuser server.py ./
COPY --chown=appuser:appuser config.py ./
COPY --chown=appuser:appuser health.py ./
COPY --chown=appuser:appuser frontend_static.py ./
COPY --chown=appuser:appuser logging_config.py ./
COPY --chown=appuser:appuser mcp_server.py ./
COPY --chown=appuser:appuser routes/ ./routes/
COPY --chown=appuser:appuser persistence/ ./persistence/
COPY --chown=appuser:appuser data/ ./data/
COPY --chown=appuser:appuser tools/ ./tools/
COPY --chown=appuser:appuser agent/ ./agent/
COPY --chown=appuser:appuser auth/ ./auth/
COPY --chown=appuser:appuser prompts/ ./prompts/
# Het Word-sjabloon van "Download als Word" (#1038, tools/rapport_docx/render.py).
COPY --chown=appuser:appuser templates/ ./templates/
COPY --chown=appuser:appuser public/ ./public/
COPY --chown=appuser:appuser core/ ./core/

# Copy built frontend from Stage 1
COPY --chown=appuser:appuser --from=frontend-builder /frontend/dist ./frontend/dist

# Commit voor /version (#231) en de installatieregel van snippets (#888); CI geeft de volledige CI_COMMIT_SHA mee via build_args.
ARG GIT_COMMIT
ENV GIT_COMMIT=$GIT_COMMIT

USER appuser

EXPOSE 8000

# --timeout-graceful-shutdown: lopende HTTP-verzoeken krijgen 45 s na SIGTERM, binnen terminationGracePeriodSeconds
# van de chart (60 s, #675).
CMD [".venv/bin/uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header", "--timeout-graceful-shutdown", "45", "--ws-max-size", "4194304"]
