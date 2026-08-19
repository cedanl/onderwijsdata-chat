# Multi-stage build for onderwijsdata-chat
# Stage 1: Frontend build (Node.js)
# Stage 2: Python runtime

# ── Stage 1: Frontend build ──────────────────────────────────────────────
FROM node:20-alpine AS frontend

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./

RUN npm ci && npm run build

# ── Stage 2: Python runtime ─────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# System dependencies for psycopg2 + build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies
COPY pyproject.toml uv.lock ./

# Install uv and dependencies
RUN pip install --no-cache-dir uv && \
    uv sync --frozen --no-dev --no-install-project

# Copy built frontend
COPY --from=frontend /app/frontend/dist ./frontend/dist

# Copy application code
COPY server.py ./
COPY routes/ ./routes/
COPY persistence/ ./persistence/
COPY data/ ./data/
COPY tools/ ./tools/
COPY agent/ ./agent/
COPY prompts/ ./prompts/
COPY public/ ./public/
COPY core/ ./core/

# Create non-root user
RUN useradd --create-home --uid 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
