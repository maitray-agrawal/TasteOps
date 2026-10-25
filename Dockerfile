# syntax=docker/dockerfile:1.4
# Multi-stage secure Dockerfile for TasteOps API & Cultural Intelligence Core
# Enforces non-root execution, minimal attack surface, and zero secret embedding.

# --- Stage 1: Build & Dependency Resolution ---
FROM python:3.13-slim-bookworm AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        curl && \
    rm -rf /var/lib/apt/lists/*

# Install uv for rapid, reproducible dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency specifications
COPY pyproject.toml uv.lock ./

# Install project dependencies into virtualenv without dev dependencies
ENV UV_PROJECT_ENVIRONMENT="/opt/venv"
RUN uv sync --frozen --no-dev --no-install-project

# --- Stage 2: Hardened Runtime Container ---
FROM python:3.13-slim-bookworm AS runner

# Security: Set read-only environment flags and disable Python byte compilation
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    ENVIRONMENT=production

WORKDIR /app

# Create unprivileged system user and group (UID/GID 10001)
RUN groupadd -g 10001 tasteops && \
    useradd -u 10001 -g tasteops -s /bin/bash -m appuser

# Copy virtual environment from builder
COPY --from=builder --chown=appuser:tasteops /opt/venv /opt/venv

# Copy application source code
COPY --chown=appuser:tasteops pyproject.toml ./
COPY --chown=appuser:tasteops src/ ./src/

# Install application package in non-editable mode
RUN /opt/venv/bin/pip install --no-deps -e .

# Create persistent storage directory with correct unprivileged ownership
RUN mkdir -p /app/storage && chown -R appuser:tasteops /app/storage

# Switch to non-root unprivileged user
USER 10001:10001

# Expose API port
EXPOSE 8000

# Healthcheck probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/ready', timeout=4)" || exit 1

# Start Uvicorn production server
CMD ["uvicorn", "tasteops.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--no-access-log"]
