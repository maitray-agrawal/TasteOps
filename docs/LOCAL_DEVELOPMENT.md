# TasteOps Local Development & Operator Guide

## 1. Overview
TasteOps is a Cultural Intelligence Operating System that orchestrates real-world taste telemetry (music, design, literature, hospitality) into experiential venue blueprints and deterministic physical execution plans.

This guide provides instructions for configuring, launching, developing, and testing TasteOps locally.

---

## 2. Prerequisites
- **Python**: Version 3.13 or 3.14 (managed via `uv` or system Python)
- **uv**: Astral's package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh` or `winget install astral-sh.uv`)
- **Docker & Docker Compose**: Optional for containerized deployment
- **Qloo API Key**: Hackathon API key from Qloo Developer Portal

---

## 3. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Edit `.env` and set your Qloo API key:
```env
QLOO_API_KEY=your_real_qloo_key
ENVIRONMENT=development
TASTEOPS_AUTH_ENFORCED=false
```

When `TASTEOPS_AUTH_ENFORCED=false`, dev-curator headers are accepted without cryptographic API key tokens for rapid local iteration.

---

## 4. Installation & Dependency Sync
Install all dependencies and development tools using `uv`:
```bash
uv sync --all-extras
```

This installs FastAPI, Uvicorn, Pydantic, HTTPX, Pytest, Pytest-Cov, Ruff, Mypy, and Respx.

---

## 5. Database Initialization & Migrations
TasteOps uses an atomic relational SQLite schema in local development (with full schema compatibility for PostgreSQL):
```bash
uv run python -c "from tasteops.persistence.database import Database; db = Database('storage/tasteops.db'); print('Database initialized at storage/tasteops.db')"
```

DDL definitions in `src/tasteops/persistence/schema.py` create all tables idempotently:
- `spaces`, `space_briefs`
- `workflow_sessions`, `state_transitions`, `audit_events`
- `cultural_twins`, `cultural_matrices`, `experience_blueprints`, `execution_plans`
- `approvals`, `execution_tasks`, `idempotency_keys`

---

## 6. Running the Application Locally
Launch the FastAPI development server:
```bash
uv run uvicorn tasteops.api.app:app --host 127.0.0.1 --port 8000 --reload
```

Access the Operator Workspace in your browser:
- **Dashboard & Physical Space Registration**: `http://localhost:8000/dashboard`
- **Interactive OpenAPI Specification**: `http://localhost:8000/docs`
- **Liveness Probe**: `http://localhost:8000/health`
- **Readiness Probe**: `http://localhost:8000/ready`

---

## 7. Running Quality Checks & Tests
Execute the full behavioral test suite (348+ tests):
```bash
uv run pytest -v
```

Execute with test coverage reporting (target >= 85%):
```bash
uv run pytest --cov=src/tasteops --cov-report=term-missing
```

Run static linting and formatting checks:
```bash
uv run ruff check src tests
uv run ruff format --check src tests
```

Run static type checking with Mypy:
```bash
uv run mypy src
```

---

## 8. Docker & Docker Compose
To build and run the hardened production container locally:
```bash
docker compose build
docker compose up -d
```

Verify container operation:
```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

Stop the container environment:
```bash
docker compose down
```

---

## 9. Troubleshooting
- **Missing QLOO_API_KEY**: Ensure `QLOO_API_KEY` is present in `.env` or set as an environment variable. In automated tests, mock providers are used automatically.
- **Port 8000 in use**: Specify an alternative port using `--port 8080`.
- **Database lock on Windows**: SQLite uses connection locking; ensure test suites use isolated temporary databases (`tmp_path`) which is already configured in `conftest.py`.
