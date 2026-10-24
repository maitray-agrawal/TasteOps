# TasteOps Backend API Contract & Frontend Handoff Specification

**Version:** `0.1.0`  
**Target:** Render Web Service (Backend) → Vercel / Next.js (Frontend)  
**Author:** Senior Backend, DevOps & Reliability Engineering  
**Consumer:** Member 3 (Frontend Engineering)

---

## 1. Overview & Connection Architecture

The TasteOps backend is a standalone, deterministic Cultural Intelligence Operating System for physical spaces. It wraps the Qloo Hackathon API with multi-category affinity intelligence, deterministic state transitions, anti-hallucination guarantees, and human-in-the-loop governance.

```text
┌────────────────────────────────────────────────────────┐
│                   Frontend (Member 3)                  │
│               Vercel / React / Next.js                 │
└───────────────────────────┬────────────────────────────┘
                            │ HTTPS + JSON (CORS)
                            v
┌────────────────────────────────────────────────────────┐
│                 TasteOps FastAPI Backend               │
│                  Render Web Service                    │
│    GET /health           │  POST /api/v1/sessions/...  │
└───────────┬───────────────┴───────────────┬────────────┘
            │                               │
            v                               v
┌───────────────────────┐       ┌────────────────────────┐
│  FileStateStore (Disk)│       │  Qloo Cultural API     │
│   /app/storage/...    │       │  hackathon.api.qloo.com│
└───────────────────────┘       └────────────────────────┘
```

### Base URLs

- **Local Development:** `http://localhost:8000`
- **Render Production:** `https://tasteops-backend.onrender.com` (or your configured Render URL)

### CORS Requirements

The backend is configured with FastAPI's `CORSMiddleware` reading `CORS_ORIGINS`:

- **Development Defaults:** `http://localhost:3000`, `http://localhost:5173`, `http://127.0.0.1:3000`, `http://127.0.0.1:5173`
- **Production Setting:** Comma-separated list containing your deployed frontend origin (e.g. `https://tasteops.vercel.app`).
- **Credentials:** Supported (`allow_credentials=True`) when explicit origins are provided.
- **Allowed Methods:** `GET, POST, OPTIONS`
- **Allowed Headers:** `*` (including `Content-Type`, `X-Request-ID`)

---

## 2. Global Request & Response Formats

### Request Correlation (`X-Request-ID`)

Every incoming request may include an optional `X-Request-ID` header. If omitted, the server generates a unique UUID `req_<hex>`. All responses include this header:

```http
X-Request-ID: req_a1b2c3d4e5f6
```

### Standard Error Response Schema

All error responses return structured JSON with uniform fields:

```json
{
  "error": "http_404",
  "message": "Workflow session 'sess_999' not found in active cache or state store.",
  "request_id": "req_a1b2c3d4e5f6"
}
```

| HTTP Status | Error Code | Description |
|---|---|---|
| `400 Bad Request` | `http_400` | Illegal state transition or invalid operation (e.g. executing an unapproved plan). |
| `404 Not Found` | `http_404` | Session ID does not exist in memory or disk. |
| `422 Unprocessable Content` | `validation_error` | Request body failed Pydantic schema validation. |
| `503 Service Unavailable` | `not_ready` | Backend starting up or downstream Qloo credentials missing. |
| `500 Internal Error` | `internal_server_error` | Server-side exception (traceback is logged server-side, never leaked to client). |

---

## 3. System & Health Endpoints

### `GET /health`

Lightweight liveness probe designed for Render health checks and uptime monitoring.

- **Upstream Calls:** None (guaranteed 0 Qloo calls, no database query)
- **Target Latency:** `< 5ms`
- **Status Codes:** `200 OK`

#### Response (`200 OK`)

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

---

### `GET /ready`

Readiness probe verifying that backend dependencies (storage writability and `QLOO_API_KEY`) are available.

- **Status Codes:** `200 OK` (ready), `503 Service Unavailable` (not ready)

#### Response (`200 OK`)

```json
{
  "status": "ready",
  "version": "0.1.0",
  "qloo_configured": true,
  "storage_ready": true,
  "details": "All backend services and storage operational."
}
```

#### Response (`503 Service Unavailable`)

```json
{
  "status": "not_ready",
  "version": "0.1.0",
  "qloo_configured": false,
  "storage_ready": true,
  "details": "Backend is starting up or missing credentials (e.g. QLOO_API_KEY)."
}
```

---

### `GET /api/v1/config`

Returns safe public configuration. **Guaranteed never to expose secret keys.**

#### Response (`200 OK`)

```json
{
  "environment": "production",
  "qloo_base_url": "https://hackathon.api.qloo.com",
  "version": "0.1.0",
  "mcp_tools_available": 10
}
```

---

## 4. Cultural Workflow & Session Endpoints

The complete physical space activation lifecycle progresses through deterministic states:

```text
CREATED ──► INTENT_PARSED ──► CULTURAL_TWIN_CREATED ──► QLOO_RESOLVED ──►
CULTURAL_MATRIX_READY ──► AGENTS_RUNNING ──► PLAN_GENERATED ──►
VALIDATED ──► AWAITING_APPROVAL ──► APPROVED ──► EXECUTING ──► COMPLETED
                                      │
                                      └──► (Reject) ──► FAILED
```

---

### `POST /api/v1/sessions`

Initializes a new physical space cultural activation workflow session.

- **Method:** `POST`
- **Status Code:** `201 Created`

#### Request Body (`application/json`)

```json
{
  "raw_intent": "Design an analog listening bar in Shibuya for specialty coffee enthusiasts and indie vinyl collectors.",
  "space_id": "venue_shibuya_001",
  "hints": {
    "business_type": "Listening Bar & Cafe",
    "neighborhood": "Shibuya, Tokyo",
    "raw_anchor_entities": ["Blue Bottle Coffee", "Tower Records"],
    "raw_tags": ["Japanese Minimalism", "Vinyl Culture", "Analog Audio"],
    "location": {
      "latitude": 35.6580,
      "longitude": 139.7016,
      "radius_meters": 3000
    }
  }
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `raw_intent` | `string` | **Yes** | Natural language brief or demographic vision (min 3 chars). |
| `space_id` | `string` | No | Identifier for physical venue. |
| `hints` | `object` | No | Pre-parsed anchors, tags, or geographic coordinates. |

#### Response (`201 Created`)

```json
{
  "session_id": "sess_8f2b1a3e-4d5c",
  "space_id": "venue_shibuya_001",
  "user_input": "Design an analog listening bar in Shibuya...",
  "current_state": "CREATED",
  "parsed_intent": {},
  "cultural_twin": null,
  "cultural_matrix": null,
  "plan": null,
  "execution_plan": null,
  "approval": null,
  "audit_events": [
    {
      "event_id": "evt_abc123",
      "session_id": "sess_8f2b1a3e-4d5c",
      "from_state": "CREATED",
      "to_state": "CREATED",
      "timestamp": "2026-10-25T03:30:00Z",
      "reason": "Session initialized"
    }
  ]
}
```

---

### `GET /api/v1/sessions/{session_id}`

Retrieves the current full typed context snapshot of a session.

- **Method:** `GET`
- **Status Codes:** `200 OK`, `404 Not Found`

#### Response (`200 OK`)

Returns the complete `WorkflowContext` object.

---

### `POST /api/v1/sessions/{session_id}/pipeline`

Drives the workflow engine through all Cultural Intelligence retrieval and domain agents until the **Human Approval Gate** (`AWAITING_APPROVAL`) is reached.

- **Method:** `POST`
- **Status Codes:** `200 OK`, `404 Not Found`

#### Request Body (`application/json`)

```json
{
  "take_per_category": 10,
  "hints": null
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `take_per_category` | `integer` | `10` | Number of Qloo recommendations to query per domain (1-50). |
| `hints` | `object` | `null` | Optional hints refinement. |

#### Response (`200 OK`)

When the pipeline reaches the Human Approval Gate:

```json
{
  "session_id": "sess_8f2b1a3e-4d5c",
  "current_state": "AWAITING_APPROVAL",
  "cultural_twin": {
    "twin_id": "twin_shibuya",
    "anchor_entities": [
      {
        "entity_id": "ent_blue_bottle_123",
        "name": "Blue Bottle Coffee",
        "category": "place"
      }
    ],
    "tags": [
      {
        "tag_id": "tag_jp_minimalism",
        "name": "Japanese Minimalism"
      }
    ]
  },
  "cultural_matrix": {
    "artists": [
      {
        "entity_id": "ent_radiohead",
        "name": "Radiohead",
        "category": "artist",
        "affinity": 0.94,
        "score": 94.0,
        "explainability": "High cross-domain co-affinity with minimalist coffee culture."
      }
    ],
    "brands": [
      {
        "entity_id": "ent_muji",
        "name": "Muji",
        "category": "brand",
        "affinity": 0.91,
        "score": 91.0
      }
    ],
    "places": [],
    "books": [],
    "movies": [],
    "total_recommendations": 18
  },
  "plan": {
    "plan_id": "plan_99e8d7",
    "title": "Shibuya Analog Listening Lounge Activation",
    "summary": "Multi-sensory acoustic lounge blending specialty pour-overs with rare vinyl curations.",
    "cultural_strategy": {
      "core_narrative": "A contemplative retreat bridging Japanese analog craftsmanship and minimalist lifestyle.",
      "affinity_anchors": ["Radiohead", "Blue Bottle Coffee"]
    },
    "experience_design": {
      "soundscape": "Acoustic analog vinyl rotation, low-gain tube amplifiers.",
      "lighting": "Warm 2200K diffused amber accents.",
      "spatial_flow": "Central acoustic listening bar with intimate listening booths."
    },
    "brand_partnerships": [
      {
        "partner_name": "Audio-Technica",
        "rationale": "High-fidelity analog hardware synergy."
      }
    ],
    "plan_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  },
  "validation_result": {
    "passed": true,
    "confidence_score": 0.93,
    "rules_evaluated": 12,
    "violations": []
  }
}
```

---

### `POST /api/v1/sessions/{session_id}/approve`

Authorizes the generated cultural activation plan. Binds a cryptographic SHA-256 hash of the plan to the approval record to prevent tampering.

- **Method:** `POST`
- **Status Codes:** `200 OK`, `400 Bad Request` (if session is not in `AWAITING_APPROVAL`), `404 Not Found`

#### Request Body (`application/json`)

```json
{
  "approver": "curator_elena"
}
```

#### Response (`200 OK`)

```json
{
  "session_id": "sess_8f2b1a3e-4d5c",
  "current_state": "APPROVED",
  "approval": {
    "record_id": "appr_7c8d9e",
    "approver": "curator_elena",
    "timestamp": "2026-10-25T03:35:10Z",
    "plan_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "status": "APPROVED"
  }
}
```

---

### `POST /api/v1/sessions/{session_id}/reject`

Rejects the generated activation plan. Transitions workflow to `FAILED` and invalidates any pending approvals.

- **Method:** `POST`
- **Status Codes:** `200 OK`, `400 Bad Request`, `404 Not Found`

#### Request Body (`application/json`)

```json
{
  "reason": "Soundscape volume recommendations incompatible with municipal noise ordinances."
}
```

#### Response (`200 OK`)

```json
{
  "session_id": "sess_8f2b1a3e-4d5c",
  "current_state": "FAILED",
  "error_message": "CURATOR_REJECTION: Soundscape volume recommendations incompatible with municipal noise ordinances."
}
```

---

### `POST /api/v1/sessions/{session_id}/execute`

Dispatches verified execution tasks for an approved plan. Protected by deterministic idempotency keys and cryptographic provenance verification.

- **Method:** `POST`
- **Status Codes:** `200 OK`, `400 Bad Request` (if session is not `APPROVED`), `404 Not Found`
- **Request Body:** `{}` (empty JSON object)

#### Response (`200 OK`)

```json
{
  "session_id": "sess_8f2b1a3e-4d5c",
  "current_state": "COMPLETED",
  "execution_plan": {
    "execution_id": "exec_5a6b7c",
    "status": "SUCCESS",
    "tasks": [
      {
        "task_id": "task_soundscape_01",
        "idempotency_key": "idemp_sound_a8b9",
        "action": "CONFIG_AUDIO_PRESET",
        "status": "DISPATCHED",
        "provenance": {
          "source_agent": "ExperienceArchitect",
          "qloo_entity_id": "ent_radiohead"
        }
      },
      {
        "task_id": "task_lighting_02",
        "idempotency_key": "idemp_light_c1d2",
        "action": "SET_LIGHTING_SCENE",
        "status": "DISPATCHED"
      }
    ]
  }
}
```

---

### `GET /api/v1/sessions/{session_id}/audit`

Retrieves the immutable audit log recording every state transition, timestamp, reason, and error.

- **Method:** `GET`
- **Status Codes:** `200 OK`, `404 Not Found`

#### Response (`200 OK`)

```json
[
  {
    "event_id": "evt_001",
    "session_id": "sess_8f2b1a3e-4d5c",
    "from_state": "CREATED",
    "to_state": "INTENT_PARSED",
    "timestamp": "2026-10-25T03:30:05Z",
    "reason": "Intent parsed successfully",
    "metadata": {}
  },
  {
    "event_id": "evt_002",
    "session_id": "sess_8f2b1a3e-4d5c",
    "from_state": "INTENT_PARSED",
    "to_state": "CULTURAL_TWIN_CREATED",
    "timestamp": "2026-10-25T03:30:08Z",
    "reason": "Cultural twin constructed with 2 anchors",
    "metadata": {}
  },
  {
    "event_id": "evt_007",
    "session_id": "sess_8f2b1a3e-4d5c",
    "from_state": "VALIDATED",
    "to_state": "AWAITING_APPROVAL",
    "timestamp": "2026-10-25T03:30:15Z",
    "reason": "Plan passed governance validation (confidence 0.93)"
  },
  {
    "event_id": "evt_008",
    "session_id": "sess_8f2b1a3e-4d5c",
    "from_state": "AWAITING_APPROVAL",
    "to_state": "APPROVED",
    "timestamp": "2026-10-25T03:32:00Z",
    "reason": "Approved by human curator curator_elena"
  },
  {
    "event_id": "evt_009",
    "session_id": "sess_8f2b1a3e-4d5c",
    "from_state": "APPROVED",
    "to_state": "COMPLETED",
    "timestamp": "2026-10-25T03:32:04Z",
    "reason": "All 2 execution tasks dispatched successfully"
  }
]
```

---

## 5. Typical Frontend Integration Flow

```typescript
// 1. Check Backend Liveness
const health = await fetch("https://tasteops-backend.onrender.com/health");
if (!health.ok) throw new Error("Backend offline");

// 2. Initialize Session
const sessionRes = await fetch("https://tasteops-backend.onrender.com/api/v1/sessions", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    raw_intent: userInputBrief,
    space_id: selectedVenueId,
  }),
});
const session = await sessionRes.json();
const sessionId = session.session_id;

// 3. Trigger Pipeline (renders loading spinner / progress steps)
const pipelineRes = await fetch(`https://tasteops-backend.onrender.com/api/v1/sessions/${sessionId}/pipeline`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ take_per_category: 10 }),
});
const awaitedSession = await pipelineRes.json();

// 4. Render Activation Plan & Approval Modal
displayPlan(awaitedSession.plan);
displayMatrix(awaitedSession.cultural_matrix);

// 5. On Curator "Approve" Click:
const approveRes = await fetch(`https://tasteops-backend.onrender.com/api/v1/sessions/${sessionId}/approve`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ approver: currentUserName }),
});

// 6. On "Execute Plan" Click:
const execRes = await fetch(`https://tasteops-backend.onrender.com/api/v1/sessions/${sessionId}/execute`, {
  method: "POST",
});
const completedSession = await execRes.json();
displaySuccess(completedSession.execution_plan);
```
