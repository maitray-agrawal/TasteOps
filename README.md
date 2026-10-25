# TasteOps — Cultural Intelligence Operating System for Physical Spaces

[![CI Quality Gates](https://github.com/maitray-agrawal/TasteOps/actions/workflows/ci.yml/badge.svg)](https://github.com/maitray-agrawal/TasteOps/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Render](https://img.shields.io/badge/Deploy-Render-46E3B7.svg)](https://render.com)

> Autonomous Cultural Intelligence & Venue Activation Engine for Physical Spaces. Powered by Qloo Taste AI™, deterministic multi-agent orchestration, and human-in-the-loop governance.

---

## 1. What TasteOps Is

**TasteOps** is an autonomous Cultural Intelligence Operating System designed for physical venues—boutique hotels, vinyl listening bars, specialty restaurants, and experiential retail spaces. It transforms high-level creative briefs and demographic intents into cohesive, multi-sensory physical venue activations: curating music programming, literature selections, design aesthetics, and brand collaborations grounded in real cultural affinity data.

---

## 2. The Problem It Solves

Curating the cultural vibe of a physical space is notoriously difficult:
- **Disjointed Guesswork:** Venue curators rely on subjective intuition or fragmented playlists, resulting in generic or clashing brand identities.
- **Cross-Domain Silos:** A venue's soundtrack, interior literature, brand partnerships, and local venue associations rarely share a coherent cultural lineage.
- **Execution Friction:** Bridging strategic creative concepts with operational activations requires coordinating multiple domain specialists without a unified ledger or governance layer.

TasteOps solves this by turning creative briefs into **provenance-verified execution specifications** through mathematically rigorous cultural intelligence.

---

## 3. Why Qloo Is Essential

TasteOps is built on **Qloo's Taste AI™**. Qloo is the indispensable cultural intelligence engine of TasteOps because:
- **Cross-Category Affinity:** Qloo connects disparate cultural domains (artists, literature, films, fashion brands, culinary destinations) through high-dimensional affinity graphs without demographic bias.
- **Geographic Precision:** Qloo enables spatial radius filtering (`POINT(lon lat)` with radial meters) to anchor cultural recommendations in local physical reality.
- **Anti-Hallucination Grounding:** Rather than generating synthetic recommendations with an LLM, TasteOps grounds every cultural insight in verified Qloo entities (`ent_...`) and taxonomy tags (`tag_...`) with strict confidence thresholds.

---

## 4. Core Workflow

TasteOps enforces a strict **13-state deterministic pipeline**:

```text
CREATED
   │
   ▼
INTENT_PARSED ──────────► Formulates structured brief & demographic signals
   │
   ▼
CULTURAL_TWIN_CREATED ──► Derives target audience, vibe positioning, spatial bounds
   │
   ▼
QLOO_RESOLVED ──────────► Resolves anchors & tags against Qloo API (threshold ≥ 0.50)
   │
   ▼
CULTURAL_MATRIX_READY ──► Queries 6 domains in parallel via Qloo Insights API
   │
   ▼
AGENTS_RUNNING ─────────► 4 specialized agents synthesize activation strategies
   │
   ▼
PLAN_GENERATED ─────────► Assembles unified CulturalActivationPlan with task DAG
   │
   ▼
VALIDATED ──────────────► Enforces Pydantic contracts, provenance, and confidence
   │
   ▼
AWAITING_APPROVAL ──────► Human-in-the-loop review gate (SHA-256 fingerprinting)
   │
   ├──────────────────────┬──────────────────────┐
   ▼ (Approve)            ▼ (Reject)             ▼ (Timeout)
APPROVED                FAILED                 FAILED
   │
   ▼
EXECUTING ──────────────► Dispatches dispatch-ready activation tasks with idempotency keys
   │
   ▼
COMPLETED ──────────────► Emits immutable audit trail & session ledger
```

---

## 5. System Architecture

```text
┌────────────────────────────────────────────────────────┐
│                   Frontend Client                      │
│               Vercel / React / Next.js                 │
└───────────────────────────┬────────────────────────────┘
                            │ HTTPS + JSON (CORS)
                            ▼
┌────────────────────────────────────────────────────────┐
│             FastAPI Backend (tasteops.api)             │
│                  Render Web Service                    │
│   GET /health    GET /ready    POST /api/v1/sessions   │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│           Orchestrator Facade (TasteOpsOrchestrator)   │
│               src/tasteops/workflows/                  │
└─────────────┬───────────────────────────┬──────────────┘
              │                           │
              ▼                           ▼
┌───────────────────────────┐ ┌──────────────────────────┐
│  Deterministic Engine     │ │   State Persistence      │
│     (WorkflowEngine)      │ │   (FileStateStore)       │
│   13 Validated States     │ │   Snapshots & Audit Logs │
└─────────────┬─────────────┘ └──────────────────────────┘
              │
              ▼
┌────────────────────────────────────────────────────────┐
│             Agent Orchestration Layer                  │
│                                                        │
│  ┌───────────────────────┐   ┌──────────────────────┐  │
│  │  Cultural Strategist  │   │ Experience Architect │  │
│  └──────────┬────────────┘   └──────────┬───────────┘  │
│             │                           │              │
│  ┌──────────▼────────────┐   ┌──────────▼───────────┐  │
│  │   Partnership Agent   │   │   Governance Agent   │  │
│  └───────────────────────┘   └──────────────────────┘  │
└───────────────────────────┬────────────────────────────┘
                            │ Tool Invocations
                            ▼
┌────────────────────────────────────────────────────────┐
│         Model Context Protocol (FastMCP Server)        │
│                    src/tasteops/mcp/                   │
└───────────────────────────┬────────────────────────────┘
                            │ Service Abstractions
                            ▼
┌────────────────────────────────────────────────────────┐
│             Cultural Intelligence Services             │
│                                                        │
│  ┌───────────────────────┐   ┌──────────────────────┐  │
│  │    EntityResolver     │   │     TagResolver      │  │
│  └──────────┬────────────┘   └──────────┬───────────┘  │
│             │                           │              │
│  ┌──────────▼────────────┐   ┌──────────▼───────────┐  │
│  │    InsightsService    │   │ CulturalMatrixService│  │
│  └───────────────────────┘   └──────────────────────┘  │
└───────────────────────────┬────────────────────────────┘
                            │ Isolated HTTP Client
                            ▼
┌────────────────────────────────────────────────────────┐
│           QlooClient (Async HTTP + In-Memory TTL)      │
│  - Exponential Backoff Retries (429, 500)              │
│  - Non-retry for Auth Errors (401, 403)                │
│  - SecretStr Masking (***REDACTED***)                  │
└───────────────────────────┬────────────────────────────┘
                            │ Signed REST API (X-Api-Key)
                            ▼
┌────────────────────────────────────────────────────────┐
│            Qloo Hackathon Cultural API™                │
│             https://hackathon.api.qloo.com             │
└────────────────────────────────────────────────────────┘
```

---

## 6. Key Features

- **Strict Upstream Client Isolation:** HTTP transport (`httpx`) is completely isolated to `src/tasteops/client.py`. No domain agent or service bypasses the client.
- **Zero Hallucination Guarantee:** Anchor entity and tag resolvers reject sub-threshold candidates. If Qloo returns 0 results, the system never invents synthetic entity IDs or fabricated affinities.
- **Deterministic 13-State Machine:** State transitions are strictly validated. Direct execution without passing the `AWAITING_APPROVAL` gate is rejected at the domain boundary.
- **Cryptographic Plan Gating:** Approval records bind the SHA-256 fingerprint of the plan to ensure that human operators approve the exact generated specification.
- **Idempotency & Duplicate Execution Protection:** Each executable task generates a deterministic idempotency key (`task_id:plan_hash:attempt`). Duplicate execution calls return cached results without re-triggering actions.
- **Model Context Protocol (MCP) Interface:** A standards-compliant FastMCP server exposing 10 typed tools for AI agent tool calling with strict Pydantic schemas.
- **Production-Ready Serving:** Render-ready health (`/health`) and readiness (`/ready`) endpoints, request correlation (`X-Request-ID`), structured logging, and non-root Docker deployment.

---

## 7. Tech Stack

- **Runtime:** Python 3.12+
- **Package Management:** [Astral uv](https://github.com/astral-sh/uv)
- **API Framework:** [FastAPI](https://fastapi.tiangolo.com/) with [Uvicorn](https://www.uvicorn.org/)
- **Data Modeling & Validation:** [Pydantic v2](https://docs.pydantic.dev/) & [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- **Agent Protocol:** [FastMCP](https://github.com/jlowin/fastmcp)
- **HTTP Transport:** [HTTPX](https://www.python-httpx.org/) (Async Client)
- **Testing & Quality:** [pytest](https://pytest.org/), [respx](https://lundberg.github.io/respx/), [Ruff](https://astral.sh/ruff), [Mypy](https://mypy-lang.org/)
- **Containerization & Hosting:** Docker (multi-stage build), Render Web Service

---

## 8. Local Setup

### Prerequisites

- [uv](https://github.com/astral-sh/uv) (recommended) or Python 3.12+
- A valid **Qloo Hackathon API Key**

### Installation

```bash
# Clone the repository
git clone https://github.com/maitray-agrawal/TasteOps.git
cd TasteOps

# Install dependencies using uv
uv sync --frozen

# Configure environment variables
cp .env.example .env
# Edit .env and supply your QLOO_API_KEY
```

### Running the API Server

```bash
# Development mode with auto-reload
uv run uvicorn tasteops.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Running the MCP Server

```bash
uv run tasteops-mcp
```

---

## 9. Environment Variables

| Variable | Type | Default | Description |
|---|---|---|---|
| `QLOO_API_KEY` | `SecretStr` | *Required* | Qloo Hackathon API key (masked in logs and representations). |
| `QLOO_BASE_URL` | `str` | `https://hackathon.api.qloo.com` | Base URL for Qloo Hackathon Gateway. |
| `QLOO_TIMEOUT_SECONDS` | `float` | `15.0` | Timeout in seconds for upstream HTTP requests. |
| `QLOO_MAX_RETRIES` | `int` | `3` | Maximum retry attempts for transient errors (429, 5xx). |
| `QLOO_RETRY_BACKOFF_FACTOR` | `float` | `0.5` | Exponential backoff factor (seconds). |
| `QLOO_CACHE_ENABLED` | `bool` | `true` | Enables in-memory async TTL cache. |
| `QLOO_CACHE_TTL_SECONDS` | `int` | `3600` | TTL in seconds for cached GET requests. |
| `ENVIRONMENT` | `str` | `development` | Deployment environment (`development` / `production`). |
| `HOST` | `str` | `0.0.0.0` | Host interface for server binding. |
| `PORT` | `int` | `8000` | Port for server binding (overridden by Render via `$PORT`). |
| `CORS_ORIGINS` | `str` | `http://localhost:3000,...` | Comma-separated list of allowed CORS origins. |
| `TASTEOPS_STORAGE_DIR` | `str` | `storage/workflows` | Filesystem path for session snapshots and audit logs. |
| `LOG_LEVEL` | `str` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |

---

## 10. Running Tests & Quality Gates

Run all quality checks before committing:

```bash
# 1. Lint checking
uv run ruff check src tests

# 2. Format checking
uv run ruff format --check src tests

# 3. Static type analysis
uv run mypy src

# 4. Full test suite execution (192 tests)
uv run pytest -v
```

---

## 11. Running with Docker

### Build Container

```bash
docker build -t tasteops-backend .
```

### Run Container Locally

```bash
docker run -d --name tasteops \
  -p 8000:8000 \
  -e ENVIRONMENT=production \
  -e QLOO_API_KEY="your_qloo_hackathon_api_key_here" \
  -e PORT=8000 \
  tasteops-backend
```

### Verify Container Health

```bash
# Liveness probe (<5ms, zero upstream calls)
curl -f http://localhost:8000/health

# Readiness probe (verifies key & storage)
curl -f http://localhost:8000/ready
```

---

## 12. Render Deployment

TasteOps is pre-configured for **Render Web Service** deployment via [`render.yaml`](render.yaml):

1. Connect this repository to your **Render Dashboard**.
2. Select **Blueprints** → **New Blueprint Instance**.
3. Render automatically provisions the service using the multi-stage [`Dockerfile`](Dockerfile).
4. Supply your secret `QLOO_API_KEY` under the service environment variables.
5. Render's health check path is configured to `/health`.

For full manual deployment instructions, see [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

---

## 13. Documentation & API Reference

- **[System Architecture](docs/ARCHITECTURE.md):** Complete architectural pillars, security isolation, and state machine graph.
- **[Backend API Contract](docs/API.md):** Detailed endpoint specifications, request/response models, TypeScript types, and cURL examples.
- **[Production Deployment Guide](docs/DEPLOYMENT.md):** Render deployment and environment configuration manual.
- **[Application Contracts (Member 3)](docs/API_CONTRACT.md):** 16 typed contracts for physical spaces, briefs, cultural matrices, and execution tasks.

---

## 14. Live Demonstration & Deployment Links

| Resource | Target URL | Status |
|---|---|---|
| **Backend API** | `https://tasteops-backend.onrender.com` | *Deployable via Blueprint* |
| **API Documentation** | `https://tasteops-backend.onrender.com/docs` | *Swagger UI* |
| **Frontend UI** | `https://<frontend-subdomain>.vercel.app` | *Member 3 Integration Active* |

---

## 15. License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
