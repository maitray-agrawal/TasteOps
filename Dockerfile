# ==============================================================================
# TasteOps Cultural Intelligence OS - Production Container
# ==============================================================================
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first for optimal Docker layer caching
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Copy application source code
COPY src ./src
COPY README.md ./

# Install application package into virtual environment
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ==============================================================================
# Production Runtime Stage
# ==============================================================================
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PORT=8000 \
    ENVIRONMENT=production \
    TASTEOPS_STORAGE_DIR=/app/storage/workflows

# Install curl for container healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Run as dedicated non-root user
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/storage/workflows /home/appuser/storage/workflows && \
    chown -R appuser:appuser /app /home/appuser && \
    chmod -R 777 /app/storage /home/appuser/storage

WORKDIR /app

# Copy virtual environment and source code with proper ownership
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appuser /app/src /app/src

USER appuser

# Healthcheck targeting fast liveness endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:${X_ZOHO_CATALYST_LISTEN_PORT:-${PORT:-8000}}/health || exit 1

# Supports Render ($PORT), Zoho Catalyst AppSail ($X_ZOHO_CATALYST_LISTEN_PORT), or default (8000).
CMD ["sh", "-c", "cd /app && exec uvicorn tasteops.api.main:app --host 0.0.0.0 --port ${X_ZOHO_CATALYST_LISTEN_PORT:-${PORT:-8000}} --workers 1"]
