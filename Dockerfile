# Stage 1: Build React Frontend
FROM node:26-alpine@sha256:8996bb5821d62a8fd9bb27c1cb07462f3fdce6e47d640c6a881ead0b064ce216 AS frontend-builder

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
FROM python:3.14-slim@sha256:930e1abba7c4e8f96ed93e8012c35d174d7732752731bbd5e8e757d7ec6f3966 AS python-builder

# uv gepind op versie en digest, zodat de build reproduceerbaar is; Renovate werkt hem bij.
COPY --from=ghcr.io/astral-sh/uv:0.13.7@sha256:96f40d3904aad8d0bd010539001d36c8e2188b981e1334471a90c4a1d93bb490 /uv /usr/local/bin/uv

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
FROM python:3.14-slim@sha256:930e1abba7c4e8f96ed93e8012c35d174d7732752731bbd5e8e757d7ec6f3966

WORKDIR /app

COPY --from=python-builder /app/.venv ./.venv

COPY server.py ./
COPY config.py ./
COPY health.py ./
COPY frontend_static.py ./
COPY logging_config.py ./
COPY routes/ ./routes/
COPY persistence/ ./persistence/
COPY data/ ./data/
COPY tools/ ./tools/
COPY agent/ ./agent/
COPY auth/ ./auth/
COPY prompts/ ./prompts/
COPY public/ ./public/
COPY core/ ./core/
COPY scripts/antwoordfeedback.py ./scripts/

# Copy built frontend from Stage 1
COPY --from=frontend-builder /frontend/dist ./frontend/dist

RUN useradd --create-home --uid 1000 appuser && \
    chown -R appuser:appuser /app

# Commit voor /version (#231) en de installatieregel van snippets (#888); CI geeft de volledige CI_COMMIT_SHA mee via build_args.
ARG GIT_COMMIT
ENV GIT_COMMIT=$GIT_COMMIT

USER appuser

EXPOSE 8000

# --timeout-graceful-shutdown: lopende HTTP-verzoeken krijgen 45 s na SIGTERM, binnen terminationGracePeriodSeconds
# van de chart (60 s, #675).
CMD [".venv/bin/uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header", "--timeout-graceful-shutdown", "45", "--ws-max-size", "4194304"]
