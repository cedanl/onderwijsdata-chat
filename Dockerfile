# Stage 1: Build React Frontend
FROM node:22-alpine AS frontend-builder

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/src ./src
COPY frontend/index.html ./
COPY frontend/vite.config.js ./
COPY frontend/eslint.config.js ./

RUN npm run build

# Stage 2: Python Backend with Frontend
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

RUN pip install --no-cache-dir uv && \
    uv sync --frozen --no-dev --no-install-project

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

CMD ["uv", "run", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
