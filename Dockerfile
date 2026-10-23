# Stage 1: Build React Frontend
FROM node:24-alpine@sha256:06d7adf3e0ef61a13f1d28682726366f97a15aa1888c934d3ecec86c33918b53 AS frontend-builder

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/src ./src
COPY frontend/index.html ./
COPY frontend/public ./public
COPY frontend/vite.config.js ./
COPY frontend/eslint.config.js ./

RUN npm run build

# Stage 2: Python-afhankelijkheden. Compiler en git (voor de git-afhankelijkheden riodata en onderwijsdata) staan
# alleen hier; het runtime-image krijgt alleen de .venv (#681).
FROM python:3.14-slim@sha256:0514bc76712d64f8bb48adcb95b1ab0d88c69fee95d62fe4c18ee948bee9b1e1 AS python-builder

# uv gepind op versie en digest, zodat de build reproduceerbaar is; Renovate werkt hem bij.
COPY --from=ghcr.io/astral-sh/uv:0.12.5@sha256:e85be844203885286c60ffad8a858d48afb6c5a5c237ca0e67f12e74b8f174b1 /uv /usr/local/bin/uv

WORKDIR /app

# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

# --extra postgres: every SDP deployment target (test/playground/production)
# configures a real POSTGRES_URI; psycopg2-binary needs to be present in the
# image even though it's an optional extra (kept lean for local/Azure SQLite use).
# UV_PYTHON_DOWNLOADS=never: de .venv hoort bij de python van dit base-image, dezelfde als in stage 3.
RUN UV_PYTHON_DOWNLOADS=never uv sync --frozen --no-dev --no-install-project --extra postgres

# Stage 3: runtime, zonder compiler, git, pip-uv of uv (#681)
FROM python:3.14-slim@sha256:0514bc76712d64f8bb48adcb95b1ab0d88c69fee95d62fe4c18ee948bee9b1e1

WORKDIR /app

COPY --from=python-builder /app/.venv ./.venv

COPY server.py ./
COPY app.py ./
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

# Commit voor /version (#231); CI geeft CI_COMMIT_SHORT_SHA mee via build_args.
ARG GIT_COMMIT
ENV GIT_COMMIT=$GIT_COMMIT

USER appuser

EXPOSE 8000

# --timeout-graceful-shutdown: lopende HTTP-verzoeken krijgen 45 s na SIGTERM, binnen terminationGracePeriodSeconds
# van de chart (60 s, #675).
CMD [".venv/bin/uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header", "--timeout-graceful-shutdown", "45", "--ws-max-size", "4194304"]
