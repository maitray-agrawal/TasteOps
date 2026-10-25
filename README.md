# TasteOps
### AI-Powered Cultural Intelligence & Activation Engine

[![CI Quality Gates](https://github.com/maitray-agrawal/TasteOps/actions/workflows/ci.yml/badge.svg)](https://github.com/maitray-agrawal/TasteOps/actions/workflows/ci.yml)
[![Tests: 192 Passed](https://img.shields.io/badge/Tests-192%20Passed-brightgreen.svg)](tests/)
[![Python: 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Astral uv](https://img.shields.io/badge/Package%20Manager-uv-purple.svg)](https://github.com/astral-sh/uv)
[![Code Style: Ruff](https://img.shields.io/badge/Code%20Style-Ruff-000000.svg)](https://astral.sh/ruff)
[![Type Checked: Mypy](https://img.shields.io/badge/Type%20Checked-Mypy-blue.svg)](https://mypy-lang.org/)
[![Deploy: Render](https://img.shields.io/badge/Deploy-Render-46E3B7.svg)](https://render.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Transform a creative brief into a culturally grounded activation plan using Qloo cultural intelligence, deterministic orchestration, specialized agents, governance, human approval, and auditable execution.**

---

## Table of Contents

1. [Hero & Project Summary](#1-hero--project-summary)
2. [Live Backend & Status](#2-live-backend--status)
3. [The Problem](#3-the-problem)
4. [The Solution](#4-the-solution)
5. [Why TasteOps? (Why Qloo is Essential)](#5-why-tasteops-why-qloo-is-essential)
6. [Key Capabilities](#6-key-capabilities)
7. [System Architecture](#7-system-architecture)
8. [End-to-End Workflow (13-State Pipeline)](#8-end-to-end-workflow-13-state-pipeline)
9. [Qloo Integration](#9-qloo-integration)
10. [Cultural Matrix](#10-cultural-matrix)
11. [Agent Architecture & MCP Layer](#11-agent-architecture--mcp-layer)
12. [Human Approval Gate](#12-human-approval-gate)
13. [Governance and Provenance](#13-governance-and-provenance)
14. [Audit Ledger & Persistence](#14-audit-ledger--persistence)
15. [API Endpoints & Contracts](#15-api-endpoints--contracts)
16. [Tech Stack](#16-tech-stack)
17. [Local Setup](#17-local-setup)
18. [Environment Variables](#18-environment-variables)
19. [Docker Deployment](#19-docker-deployment)
20. [Render Production Deployment](#20-render-production-deployment)
21. [Testing & Quality Verification](#21-testing--quality-verification)
22. [Security & Isolation](#22-security--isolation)
23. [Hackathon Context](#23-hackathon-context)
24. [Roadmap](#24-roadmap)
25. [Contributors](#25-contributors)
26. [License](#26-license)

---

## 1. Hero & Project Summary

**TasteOps** is an autonomous Cultural Intelligence Operating System for physical venues—boutique hotels, vinyl listening bars, specialty restaurants, and experiential retail spaces. 

Instead of relying on subjective human guesswork or ungrounded generative LLM hallucinations, TasteOps binds mathematical cultural affinity data from **Qloo's Taste AI™** to a **deterministic 13-state multi-agent pipeline**. It accepts venue briefs, resolves high-confidence cultural anchors, builds cross-domain affinity matrices, orchestrates domain-specialist agents, enforces a cryptographic human-approval gate, and outputs an auditable, idempotent execution ledger.

---

## 2. Live Backend & Status

TasteOps is architected with a decoupled backend-first model. The backend is fully containerized, tested, and deployable to Render:

| Component | Target URL / Reference | Status |
| :--- | :--- | :--- |
| **Live Backend Service** | [`https://tasteops-backend.onrender.com`](https://tasteops-backend.onrender.com) | **Verified Production Ready** |
| **Interactive API Docs (Swagger)** | [`https://tasteops-backend.onrender.com/docs`](https://tasteops-backend.onrender.com/docs) | **Operational** |
| **Liveness Probe** | [`https://tasteops-backend.onrender.com/health`](https://tasteops-backend.onrender.com/health) | **Operational (<5ms response)** |
| **Readiness Probe** | [`https://tasteops-backend.onrender.com/ready`](https://tasteops-backend.onrender.com/ready) | **Operational (Key & Disk check)** |
| **Frontend Web App** | `https://<frontend-domain>.vercel.app` | *Under Active Development (`feature/member-3-tasks`)* |

> **Note on Live Demo:** The backend HTTP API and MCP server are 100% operational. The interactive React/Next.js frontend UI is currently being finalized on branch `feature/member-3-tasks` and will consume this stable backend contract upon merge.

---

## 3. The Problem

Curating the cultural identity and live activations of physical spaces faces critical operational challenges:
- **Disjointed Guesswork:** Curators rely on subjective personal tastes or fragmented playlists, resulting in disjointed brand identities and inconsistent guest experiences.
- **Cross-Category Silos:** A venue's soundscape, literature, wine list, design aesthetic, and brand pop-ups rarely share a mathematically coherent cultural lineage.
- **LLM Hallucinations:** Generic generative AI invents plausible-sounding cultural pairings that have zero actual correlation with target demographic audiences.
- **Lack of Governance & Auditability:** Real-world venue operations require signed human approval, budgetary limits, and immutable execution records before physical resources are committed.

---

## 4. The Solution

TasteOps solves this by turning creative briefs into **provenance-verified execution specifications**:
1. Ingests spatial parameters (location coordinates, venue category, square footage, vibe keywords, target demographics).
2. Queries Qloo's cultural knowledge graph to resolve verified entities and taxonomy tags with confidence scores $\ge 0.50$.
3. Constructs a 6-domain **Cultural Matrix** across Music, Literature, Dining, Fashion, Cinema, and Visual Art.
4. Orchestrates four domain agents via typed **Model Context Protocol (MCP)** tools to draft a unified activation plan.
5. Locks the plan behind a **cryptographic SHA-256 Human Approval Gate**.
6. Emits an immutable, idempotent execution ledger ready for real-world operations.

---

## 5. Why TasteOps? (Why Qloo is Essential)

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Why TasteOps & Qloo?                            │
├────────────────────────────────┬───────────────────────────────────────┤
│ Without Qloo (Generic AI)      │ With TasteOps (Qloo Cultural AI)      │
├────────────────────────────────┼───────────────────────────────────────┤
│ ❌ Subjective vibe guesswork   │ ✅ Real cultural affinity correlation  │
│ ❌ Hallucinated entity names   │ ✅ Verified Qloo entity & tag IDs     │
│ ❌ Siloed category assumptions │ ✅ 6-domain cross-cultural matrices   │
│ ❌ Unchecked automated actions │ ✅ Mandatory SHA-256 human approval   │
│ ❌ No audit trail or lineage   │ ✅ Immutable cryptographic audit logs │
└────────────────────────────────┴───────────────────────────────────────┘
```

**Qloo is the indispensable cultural engine of TasteOps:**
- **Real Cultural Affinity:** Qloo connects disparate cultural domains through high-dimensional affinity graphs without demographic bias.
- **Entity & Tag Grounding:** Every cultural anchor is mapped to an authoritative Qloo entity (`ent_...`) or taxonomy tag (`tag_...`).
- **Grounded Agent Actions:** Agents never make arbitrary recommendations; every suggestion is directly bound to Qloo affinity scores.
- **Spatial Radius Filtering:** Qloo enables spatial radius filtering (`POINT(lon lat)` with radial meters) to anchor cultural recommendations in local physical reality.
- **Strict Provenance & Verification:** Every recommendation contains its source entity, tag, confidence score, and query lineage.

---

## 6. Key Capabilities

- **Zero-Hallucination Threshold:** Anchor entity and tag resolvers enforce strict $\ge 0.50$ confidence thresholds. If Qloo returns sub-threshold matches, TasteOps degrades safely rather than inventing synthetic entities.
- **Deterministic 13-State Machine:** State transitions are strictly validated. No task can execute without progressing sequentially through the pipeline.
- **Cryptographic Plan Gating:** Approval records bind the SHA-256 fingerprint of the plan to ensure that human operators approve the exact generated specification.
- **Idempotent Task Execution:** Each executable task generates a deterministic idempotency key (`task_id:plan_hash:attempt`). Duplicate execution calls return cached results without re-triggering operations.
- **Model Context Protocol (FastMCP):** A standards-compliant FastMCP server exposes 10 typed tools for AI agent tool calling with strict Pydantic schemas.
- **Sub-5ms Health Probes:** Lightweight `/health` liveness probe guarantees zero upstream Qloo queries, preventing Render deployment timeouts.
- **Persistent State Store:** File-based state persistence (`FileStateStore`) stores full session state snapshots and audit trails.

---

## 7. System Architecture

The following diagram illustrates the complete end-to-end TasteOps architecture from client interfaces down to the Qloo Cultural API:

```mermaid
graph TD
    Client["Client / Frontend<br/>(React / Next.js / CLI)"]
    
    subgraph TasteOps_Core ["TasteOps Application Core"]
        FastAPI["FastAPI Web Service<br/>(src/tasteops/api)"]
        Orchestrator["Workflow Orchestrator<br/>(TasteOpsOrchestrator)"]
        Engine["Deterministic Engine<br/>(13 Validated States)"]
        Store["State Persistence<br/>(FileStateStore / Snapshots)"]
        
        subgraph Agent_Layer ["Specialized Agent Layer"]
            A1["Cultural Strategist"]
            A2["Experience Architect"]
            A3["Partnership Agent"]
            A4["Governance Agent"]
        end
        
        MCP["FastMCP Tool Server<br/>(10 Typed Tools)"]
        
        subgraph Services ["Cultural Intelligence Services"]
            S1["EntityResolver"]
            S2["TagResolver"]
            S3["InsightsService"]
            S4["CulturalMatrixService"]
        end
        
        ClientWrapper["QlooClient<br/>(Async HTTP + TTL Cache + Retries)"]
    end
    
    QlooAPI[("Qloo Hackathon Cultural API<br/>https://hackathon.api.qloo.com")]

    Client -->|HTTP / JSON| FastAPI
    FastAPI --> Orchestrator
    Orchestrator --> Engine
    Orchestrator --> Store
    Engine --> Agent_Layer
    Agent_Layer -->|Tool Invocations| MCP
    MCP --> Services
    Services --> ClientWrapper
    ClientWrapper -->|Signed REST API (X-Api-Key)| QlooAPI
```

---

## 8. End-to-End Workflow (13-State Pipeline)

TasteOps implements a strict 13-state deterministic workflow. Skipping states or circumventing the approval gate is physically impossible at the domain layer:

```mermaid
stateDiagram-v2
    [*] --> CREATED
    CREATED --> INTENT_PARSED: Ingest creative brief
    INTENT_PARSED --> CULTURAL_TWIN_CREATED: Derive target audience & spatial bounds
    CULTURAL_TWIN_CREATED --> QLOO_RESOLVED: Resolve anchors & tags (threshold >= 0.50)
    QLOO_RESOLVED --> CULTURAL_MATRIX_READY: Build cross-domain affinity matrix
    CULTURAL_MATRIX_READY --> AGENTS_RUNNING: Dispatch 4 specialized agents
    AGENTS_RUNNING --> PLAN_GENERATED: Assemble unified activation plan
    PLAN_GENERATED --> VALIDATED: Validate contracts & provenance
    VALIDATED --> AWAITING_APPROVAL: Compute SHA-256 fingerprint & lock

    state AWAITING_APPROVAL {
        [*] --> PendingReview
        PendingReview --> Approved: Operator Sign-off
        PendingReview --> Rejected: Operator Rejection
        PendingReview --> TimedOut: 24h Expiry
    }

    AWAITING_APPROVAL --> APPROVED: Operator approves
    AWAITING_APPROVAL --> FAILED: Operator rejects / timeout
    APPROVED --> EXECUTING: Dispatch idempotent execution tasks
    EXECUTING --> COMPLETED: Finalize immutable audit ledger
    COMPLETED --> [*]
    FAILED --> [*]
```

### Detailed State Transitions

1. **`CREATED`**: Session initialized with unique `session_id` and raw creative brief.
2. **`INTENT_PARSED`**: Structured brief extracted, identifying venue category, vibe keywords, and geographic location.
3. **`CULTURAL_TWIN_CREATED`**: Target demographic profiles, spatial coordinates, and venue boundaries formalized.
4. **`QLOO_RESOLVED`**: Entity and tag resolvers query Qloo. Anchor entities must score $\ge 0.50$ confidence.
5. **`CULTURAL_MATRIX_READY`**: Parallel Qloo Insights queries populate the 6-domain cultural affinity matrix.
6. **`AGENTS_RUNNING`**: Domain agents synthesize music curation, literature selections, design aesthetics, and brand pop-ups.
7. **`PLAN_GENERATED`**: Aggregated into a unified `CulturalActivationPlan` with an executable task DAG.
8. **`VALIDATED`**: Pydantic contracts and provenance references verified.
9. **`AWAITING_APPROVAL`**: Plan hashed with SHA-256; workflow pauses for mandatory human review.
10. **`APPROVED`**: Authorized operator submits signed approval matching the exact plan hash.
11. **`EXECUTING`**: Tasks dispatched with idempotency keys (`task_id:plan_hash:attempt`).
12. **`COMPLETED`**: All tasks executed; session snapshot and audit ledger sealed.
13. **`FAILED`**: Error, validation rejection, or operator decline recorded with structured error context.

---

## 9. Qloo Integration

TasteOps interacts with Qloo through a dedicated, isolated HTTP layer (`src/tasteops/client.py`) that strictly adheres to the Hackathon API contracts:

- **Isolated Client Architecture:** All HTTP transport is encapsulated within `QlooClient`. No domain agent or service directly calls `httpx`.
- **API Key Protection:** The key is stored as a Pydantic `SecretStr`, preventing leakage in logs, stack traces, or string representations.
- **Exponential Backoff & Retries:** Automatic retries on HTTP `429` (rate limit) and `5xx` server errors with configurable exponential backoff (`QLOO_RETRY_BACKOFF_FACTOR=0.5`).
- **Non-Retriable Auth Errors:** HTTP `401` and `403` fail fast without wasteful retries.
- **In-Memory TTL Caching:** Deterministic GET queries are cached in memory (default TTL: 3600 seconds), ensuring low latency and respecting API limits.
- **Parallel Domain Fetching:** `CulturalMatrixService` issues concurrent `asyncio.gather` requests across all 6 cultural categories.

---

## 10. Cultural Matrix

The **Cultural Matrix** is the quantitative foundation of every venue activation. It represents cross-domain affinity scores between the venue's cultural twin and 6 distinct lifestyle domains:

| Domain | Entity / Tag Types | Example Activation Output |
| :--- | :--- | :--- |
| **Music** | Artists, Genres, Record Labels | Soundscape programming, vinyl curation, DJ sets |
| **Literature** | Authors, Publications, Genres | Reading room selection, library curation |
| **Dining** | Culinary Styles, Chefs, Wine Regions | Curated beverage menu, culinary collaborations |
| **Fashion** | Designers, Apparel Brands | Staff uniform aesthetics, merchandise capsules |
| **Cinema** | Directors, Movements, Cinematography | Ambient visual projections, screening series |
| **Visual Art** | Artists, Movements, Galleries | Wall art curation, sculpture placement |

```json
{
  "matrix_id": "mat_8f1a2c",
  "anchor_entity": {
    "entity_id": "ent_blue_note_records",
    "name": "Blue Note Records",
    "confidence": 0.94
  },
  "affinities": {
    "music": [
      {"entity_id": "ent_miles_davis", "name": "Miles Davis", "affinity_score": 0.96},
      {"entity_id": "ent_john_coltrane", "name": "John Coltrane", "affinity_score": 0.93}
    ],
    "literature": [
      {"entity_id": "ent_jack_kerouac", "name": "Jack Kerouac", "affinity_score": 0.84}
    ]
  }
}
```

---

## 11. Agent Architecture & MCP Layer

TasteOps leverages four specialized domain agents orchestrated through the **Model Context Protocol (FastMCP)**:

```
┌────────────────────────────────────────────────────────┐
│                   Agent Specializations                │
├───────────────────────┬────────────────────────────────┤
│ Agent                 │ Primary Responsibility         │
├───────────────────────┼────────────────────────────────┤
│ Cultural Strategist   │ Analyzes demographic affinity  │
│ Experience Architect  │ Curates music, lighting, decor │
│ Partnership Agent     │ Sources brand collaborations   │
│ Governance Agent      │ Validates provenance & budget  │
└───────────────────────┴────────────────────────────────┘
```

### The 10 MCP Tools (`src/tasteops/mcp/`)

Agents interact with the system via typed MCP tools:
1. `resolve_entities`: Maps search queries to verified Qloo entity IDs.
2. `resolve_tags`: Maps descriptive tags to Qloo taxonomy IDs.
3. `get_insights`: Fetches affinity graphs for specific entities.
4. `build_cultural_matrix`: Synthesizes 6-domain affinity matrices.
5. `calculate_affinity`: Computes pairwise affinity between entities.
6. `verify_provenance`: Validates entity confidence thresholds.
7. `audit_plan_budget`: Ensures activation costs remain within constraints.
8. `generate_activation_dag`: Generates dependency-ordered execution tasks.
9. `compute_plan_fingerprint`: Computes SHA-256 fingerprint for approval gating.
10. `verify_idempotency_key`: Validates task execution idempotency.

---

## 12. Human Approval Gate

To prevent rogue agent actions and enforce accountability, TasteOps implements a **Cryptographic Approval Gate**:

1. Once the `CulturalActivationPlan` is assembled, TasteOps generates a SHA-256 fingerprint of the plan payload:
   $$\text{Fingerprint} = \text{SHA-256}(\text{Canonical JSON}(\text{Plan}))$$
2. The workflow enters state `AWAITING_APPROVAL` and pauses.
3. The human operator reviews the plan via `POST /api/v1/sessions/{id}/approve` or `POST /api/v1/sessions/{id}/reject`.
4. The approval request **must** provide the matching `plan_fingerprint`. If the plan was altered or corrupted, approval is rejected.
5. Execution without an approved gate record is blocked at the domain boundary.

---

## 13. Governance and Provenance

Every recommendation in TasteOps carries strict **data provenance**:
- **Source Verification:** Every recommended artist, author, or brand includes its Qloo entity ID (`ent_...`) or taxonomy tag ID (`tag_...`).
- **Confidence Scoring:** Entities below a $0.50$ confidence threshold are rejected during initial resolution.
- **Affinity Thresholding:** Activation recommendations cite the exact quantitative affinity score from Qloo.
- **Audit Trails:** Governance agents flag ungrounded suggestions and block invalid plans during the `VALIDATED` state.

---

## 14. Audit Ledger & Persistence

TasteOps records every state change, agent action, approval decision, and task execution in an immutable audit ledger:
- **`FileStateStore`**: Persists session states as JSON files under `storage/workflows/{session_id}.json`.
- **Audit Trail Entries**: Each log entry records:
  - Timestamp (ISO 8601 UTC)
  - State transition (`from_state` $\rightarrow$ `to_state`)
  - Actor (`system`, `agent:<name>`, or `user:<id>`)
  - Cryptographic payload fingerprint
  - Success status and error metadata (if applicable)

---

## 15. API Endpoints & Contracts

The FastAPI backend exposes clean, fully typed endpoints:

| Method | Endpoint | Description | Health/Auth |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Liveness probe (<5ms, zero upstream calls) | Public |
| `GET` | `/ready` | Readiness probe (verifies key & storage writability) | Public |
| `GET` | `/api/v1/config` | Safe public configuration (masked secrets) | Public |
| `POST` | `/api/v1/sessions` | Initialize a new workflow session from a brief | Public |
| `GET` | `/api/v1/sessions/{id}` | Retrieve complete session state and audit ledger | Public |
| `POST` | `/api/v1/sessions/{id}/approve` | Submit human approval with SHA-256 fingerprint | Public |
| `POST` | `/api/v1/sessions/{id}/reject` | Submit human rejection with reason | Public |
| `POST` | `/api/v1/sessions/{id}/execute` | Dispatch approved tasks for execution | Public |

### Example: Initializing a Session

```bash
curl -X POST "https://tasteops-backend.onrender.com/api/v1/sessions" \
  -H "Content-Type: application/json" \
  -d '{
    "venue_name": "The Velvet Needle",
    "venue_type": "vinyl_listening_bar",
    "location": {
      "city": "Tokyo",
      "neighborhood": "Shimokitazawa",
      "coordinates": {"latitude": 35.6618, "longitude": 139.6677}
    },
    "vibe_keywords": ["jazz", "mid-century", "japanese_whisky", "analog"],
    "target_demographic": "Creatives aged 25-42 seeking analog warmth and rare vinyl"
  }'
```

---

## 16. Tech Stack

| Layer | Technology | Rationale |
| :--- | :--- | :--- |
| **Language** | Python 3.12+ | Native async support, typing features, robust ecosystem |
| **Package Manager** | [Astral uv](https://github.com/astral-sh/uv) | 10–100x faster dependency resolution, deterministic `uv.lock` |
| **Web Framework** | [FastAPI](https://fastapi.tiangolo.com/) | High performance, automatic OpenAPI documentation, Pydantic v2 integration |
| **ASGI Server** | [Uvicorn](https://www.uvicorn.org/) | Standard lightning-fast ASGI server |
| **Validation & Settings** | [Pydantic v2](https://docs.pydantic.dev/) | Strict data contracts, schema generation, secret masking |
| **Agent Protocol** | [FastMCP](https://github.com/jlowin/fastmcp) | Standardized Model Context Protocol for typed tool calling |
| **HTTP Client** | [HTTPX](https://www.python-httpx.org/) | Modern async HTTP client with connection pooling and timeouts |
| **Mocking & Testing** | [pytest](https://pytest.org/) & [respx](https://lundberg.github.io/respx/) | 192 tests with strict mock isolation and live Qloo support |
| **Code Quality** | [Ruff](https://astral.sh/ruff) & [Mypy](https://mypy-lang.org/) | Sub-second linting, formatting, and strict static type checking |
| **Containerization** | Docker (Multi-stage) | Lean production container running as non-root `appuser` |
| **Cloud Hosting** | Render Web Service | Declarative Blueprint deployment via `render.yaml` |

---

## 17. Local Setup

### Prerequisites

- [uv](https://github.com/astral-sh/uv) (recommended) or Python 3.12+
- A valid **Qloo Hackathon API Key**

### 1. Clone & Install

```bash
# Clone the repository
git clone https://github.com/maitray-agrawal/TasteOps.git
cd TasteOps

# Install dependencies using uv
uv sync --frozen
```

### 2. Configure Environment

```bash
# Create local environment configuration
cp .env.example .env

# Edit .env and supply your QLOO_API_KEY
```

### 3. Start Development Server

```bash
uv run uvicorn tasteops.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Run MCP Server (Optional)

```bash
uv run tasteops-mcp
```

---

## 18. Environment Variables

| Variable | Type | Default | Required | Description |
| :--- | :--- | :--- | :---: | :--- |
| `QLOO_API_KEY` | `SecretStr` | — | **Yes** | Qloo Hackathon API Key (masked in representations). |
| `QLOO_BASE_URL` | `str` | `https://hackathon.api.qloo.com` | No | Qloo Hackathon API endpoint. |
| `QLOO_TIMEOUT_SECONDS` | `float` | `15.0` | No | HTTP timeout in seconds (range: 1.0–120.0). |
| `QLOO_MAX_RETRIES` | `int` | `3` | No | Retries for transient 429/5xx errors. |
| `QLOO_RETRY_BACKOFF_FACTOR`| `float` | `0.5` | No | Exponential backoff factor. |
| `QLOO_CACHE_ENABLED` | `bool` | `true` | No | Enables in-memory async TTL caching. |
| `QLOO_CACHE_TTL_SECONDS` | `int` | `3600` | No | Cache TTL in seconds (1 hour). |
| `ENVIRONMENT` | `str` | `development` | No | Deployment mode (`development`, `production`). |
| `HOST` | `str` | `0.0.0.0` | No | Host interface for server binding. |
| `PORT` | `int` | `8000` | No | Port for server binding (supplied by Render). |
| `CORS_ORIGINS` | `str` | `http://localhost:3000,...` | No | Comma-delimited list of allowed browser origins. |
| `TASTEOPS_STORAGE_DIR` | `str` | `storage/workflows` | No | Directory path for session snapshots and audit logs. |
| `LOG_LEVEL` | `str` | `INFO` | No | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |

---

## 19. Docker Deployment

TasteOps features a hardened multi-stage Docker build running under a dedicated non-root user (`appuser`, UID 1000).

### Build Container

```bash
docker build -t tasteops-backend .
```

### Run Container

```bash
docker run -d --name tasteops \
  -p 8000:8000 \
  -e ENVIRONMENT=production \
  -e QLOO_API_KEY="your_qloo_hackathon_api_key_here" \
  -e PORT=8000 \
  tasteops-backend
```

### Healthcheck Verification

```bash
# Liveness probe
curl -f http://localhost:8000/health

# Readiness probe
curl -f http://localhost:8000/ready
```

---

## 20. Render Production Deployment

TasteOps is pre-configured for one-click **Render Web Service** deployment using the included [render.yaml](render.yaml) Blueprint:

1. Connect this repository to your **Render Dashboard**.
2. Create a **New Blueprint Instance**.
3. Render automatically provisions the service via `Dockerfile`.
4. Supply your secret `QLOO_API_KEY` under the service environment variables.
5. Render uses `/health` as the automated zero-downtime healthcheck path.

---

## 21. Testing & Quality Verification

TasteOps maintains strict CI quality gates with **192 passing tests**:

```bash
# 1. Lint checking (Ruff)
uv run ruff check src tests

# 2. Format checking (Ruff format)
uv run ruff format --check src tests

# 3. Static type analysis (Mypy)
uv run mypy src

# 4. Full test suite (pytest)
uv run pytest -q
```

**Quality Summary:**
- **Linting:** 0 warnings, 0 errors.
- **Formatting:** 58 files checked, 100% compliant.
- **Type Safety:** 38 source files checked, 0 type errors.
- **Test Coverage:** 192 tests passed in ~26 seconds.

---

## 22. Security & Isolation

- **Secret Protection:** API keys are never stored in plain text or logged. Handled strictly via Pydantic `SecretStr`.
- **Non-Root Execution:** The production container runs strictly under non-privileged `appuser`.
- **CORS Protection:** Configurable origin whitelisting with automatic credential stripping when wildcards are detected.
- **Cryptographic Gate:** Plans cannot be modified or swapped post-generation without invalidating the SHA-256 fingerprint.
- **Sub-5ms Liveness Probe:** The `/health` endpoint isolates monitoring from external dependencies, eliminating DDoS amplification via health checks.

---

## 23. Hackathon Context

TasteOps was engineered for the **Qloo Hackathon** to demonstrate how **Taste AI™** can power autonomous, culturally coherent physical space activations.

### Key Hackathon Innovations
- **Cross-Domain Synthesis:** Unifies 6 separate cultural domains into a single quantitative affinity matrix.
- **Grounding Against Hallucination:** Eliminates generative AI drift by anchoring recommendations in verified Qloo knowledge graph entities.
- **Production-Grade Engineering:** Built with strict type safety, deterministic state machine architecture, 192 unit/integration tests, and automated multi-stage containerization.

---

## 24. Roadmap

- [x] **Phase 1: Core Engine & Architecture**
  - [x] Isolated Qloo HTTP client with caching & retries.
  - [x] 13-state deterministic workflow machine.
  - [x] 4 specialized domain agents with 10 FastMCP tools.
  - [x] Cryptographic human approval gate with SHA-256 fingerprinting.
  - [x] Production Docker container & Render Blueprint.
  - [x] 192 automated unit and integration tests.
- [ ] **Phase 2: Frontend Client Integration** *(Branch `feature/member-3-tasks` in progress)*
  - [ ] Interactive venue brief builder UI.
  - [ ] Real-time 6-domain cultural matrix visualization.
  - [ ] Human approval dashboard with one-click signing.
- [ ] **Phase 3: Physical Operations & IoT**
  - [ ] Automated Spotify / Sonos playlist synchronization.
  - [ ] Smart lighting & DMX controller presets.
  - [ ] Digital display menu & visual art triggers.

---

## 25. Contributors

- **Maitray Agrawal** — Core Backend Architecture, Qloo Integration, DevOps & Release Engineering ([maitrayagrawal1705@gmail.com](mailto:maitrayagrawal1705@gmail.com))
- **TasteOps Team** — Domain Agent Design & Frontend Client Integration

---

## 26. License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
