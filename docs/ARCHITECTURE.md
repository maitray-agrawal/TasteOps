# TasteOps System Architecture

> **Cultural Intelligence Operating System for Physical Spaces**

TasteOps transforms raw physical space briefs and demographics into culturally resonant, multi-sensory physical venue activations. It bridges Qloo's Taste AI™ intelligence with deterministic multi-agent orchestration, strict human-in-the-loop governance, and a production-grade FastAPI HTTP service.

---

## 1. System Topology

```text
┌────────────────────────────────────────────────────────┐
│                   Frontend (Member 3)                  │
│                 Vercel / React / Next.js               │
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
                            │ Signed REST API
                            ▼
┌────────────────────────────────────────────────────────┐
│            Qloo Hackathon Cultural API™                │
│             https://hackathon.api.qloo.com             │
└────────────────────────────────────────────────────────┘
```

---

## 2. Core Architectural Pillars

### I. Strict Upstream Client Isolation
Raw HTTP calls (`httpx`) exist exclusively inside [`src/tasteops/client.py`](file:///d:/TasteOps/src/tasteops/client.py). No service, agent, or workflow engine component ever directly queries external APIs.

### II. Zero-Hallucination & Anti-Fabrication Guarantee
- Anchor entity resolution and tag resolution enforce minimum confidence thresholds (default: 0.50).
- Sub-threshold queries return empty lists or `None`. The system never fabricates entity IDs or synthetic tags.
- Fallback matrix queries strictly downsample recommendation sizes rather than hallucinating affinities.

### III. Deterministic 13-State Machine
The workflow follows a strict state transition graph:
```text
CREATED ──► INTENT_PARSED ──► CULTURAL_TWIN_CREATED ──► QLOO_RESOLVED ──►
CULTURAL_MATRIX_READY ──► AGENTS_RUNNING ──► PLAN_GENERATED ──►
VALIDATED ──► AWAITING_APPROVAL ──► APPROVED ──► EXECUTING ──► COMPLETED
                                      │
                                      └──► (Reject) ──► FAILED
```
- Direct execution without passing through `AWAITING_APPROVAL` and `APPROVED` is rejected at the domain boundary with `InvalidStateTransitionError`.
- Human approval cryptographically binds the SHA-256 hash of the activation plan to ensure integrity.
- Execution tasks enforce stable idempotency keys to prevent duplicate external actions.

### IV. Production-Grade Serving & Observability
- **FastAPI HTTP Service:** Exposes session lifecycle, liveness probes (`/health`), and readiness probes (`/ready`).
- **Request Tracing:** Every request receives an `X-Request-ID` correlation identifier returned in headers.
- **Auditing:** Every state change emits an immutable [`AuditEvent`](file:///d:/TasteOps/src/tasteops/workflows/persistence.py#L27) persisted to disk.
- **Docker Container:** Runs non-root (`appuser`), multi-stage build via Astral `uv`, dynamic `$PORT` expansion.
