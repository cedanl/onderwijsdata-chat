# Stage 1: Build React Frontend
FROM node:26-alpine@sha256:c6ad9e9c1d80f6eb607c26b4b0a132ff7a2344fad1c78ea3baa2a7d4c8de6d94 AS frontend-builder

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
FROM python:3.14-slim@sha256:cd89c30eda26ee911a4611b18680086e0ea42e6f5f8cbe653d07fa7958c9cec8 AS python-builder

# uv gepind op versie en digest, zodat de build reproduceerbaar is; Renovate werkt hem bij.
COPY --from=ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 /uv /usr/local/bin/uv

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
FROM python:3.14-slim@sha256:cd89c30eda26ee911a4611b18680086e0ea42e6f5f8cbe653d07fa7958c9cec8

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
