# Stage 1: Build React Frontend
FROM node:24-alpine@sha256:50c8e8ca1d27439048670df5883f32d57cf81cff6233222c893fd0d9884cbd81 AS frontend-builder

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/src ./src
COPY frontend/index.html ./
COPY frontend/vite.config.js ./
COPY frontend/eslint.config.js ./

RUN npm run build

# Stage 2: Python Backend with Frontend
FROM python:3.14-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6

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
# hadolint ignore=DL3013
RUN pip install --no-cache-dir uv && \
    uv sync --frozen --no-dev --no-install-project --extra postgres

COPY server.py ./
COPY app.py ./
COPY config.py ./
COPY health.py ./
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

# Copy built frontend from Stage 1
COPY --from=frontend-builder /frontend/dist ./frontend/dist

RUN useradd --create-home --uid 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD [".venv/bin/uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
