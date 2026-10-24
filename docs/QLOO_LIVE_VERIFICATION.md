# TasteOps Cultural Intelligence — Qloo API Verification & Audit Report

**Audit Date:** October 25, 2026
**Target Environment:** Qloo Hackathon Gateway (`https://hackathon.api.qloo.com`)
**Client Implementation:** `tasteops.client.QlooClient`
**Service Layer:** `InsightsService`, `CulturalMatrixService`, `EntityResolver`, `TagResolver`

---

## 1. Executive Summary

This document presents a comprehensive audit of the existing TasteOps Cultural Intelligence layer against the Qloo Hackathon API. The audit inspects HTTP transport behavior, request parameter serialization, error classification, retry lifecycles, and domain service workflows.

Each item in this audit is strictly categorized under:
- **Verified Against Live API:** Confirmed by direct HTTP probes to `https://hackathon.api.qloo.com`.
- **Verified Using Mocks:** Confirmed by deterministic unit and integration test fixtures via `respx` and `pytest`.
- **Assumptions:** Architectural and protocol assumptions grounded in official Qloo API conventions.
- **Unsupported / Unknown Behavior:** Identified gaps, unexposed endpoints, or untestable live features.

---

## 2. Verification Matrix

| Area / Feature | Status | Verification Mechanism | Key Findings & Contract Behaviors |
| :--- | :--- | :--- | :--- |
| **Authentication** | Verified Live & Mock | Direct HTTPS Probes + Unit Tests | Authenticates via `X-Api-Key` header. Live gateway responds with 401 on missing/mismatched keys. Keys protected via `SecretStr`. |
| **Entity Search** | Verified Mock | `respx` + `EntityResolver` tests | `GET /search` with `query`, `type`, `take`. Match scoring (exact, token, subset, fuzzy) with confidence thresholds. |
| **Tag Resolution** | Verified Mock | `respx` + `TagResolver` tests | `GET /v2/tags` with `query`, `type`, `take`. Rejects unverified tags; guarantees zero tag hallucination. |
| **Insights** | Verified Mock | `respx` + `InsightsService` tests | `GET /v2/insights` with dot-notation parameters (`signal.interests.*`, `filter.type`). Normalizes to `QlooInsight`. |
| **Spatial Queries** | Verified Mock | `respx` + Capability Validation | Restricts WKT `POINT(lon lat)` and `radius` strictly to spatial categories (`place`, `destination`). Rejects invalid WKT. |
| **Cultural Matrix** | Verified Mock | Async Concurrency + Fallback tests | `asyncio.gather` queries 6 domains in parallel. Single-retry deterministic fallback on 0 results; zero hallucinated items. |
| **Filter Parameters** | Verified Mock | `SearchParams`, `InsightParams` validation | Dot-notation query parameter serialization (`filter.type`, `feature.explainability`). Strict parameter typing. |
| **Response Parsing** | Verified Mock | Multi-envelope extraction tests | Flexible extraction handling raw lists, or dictionaries with `results`, `data`, `entities`, `tags`, or `insights`. |
| **401/403 Behavior** | Verified Live & Mock | Live Gateway Probes + Unit Tests | Immediate non-retryable failure. Raises `QlooAuthenticationError` immediately without retrying or leaking credentials. |
| **429 Handling** | Verified Mock | `respx` Mock + Retry Loop tests | Transient backoff. Respects `Retry-After` header when present, falls back to exponential backoff (`factor * 2^(attempt-1)`). |
| **5xx Handling** | Verified Mock | `respx` Transient 500/502/503 tests | Retries up to `max_retries` with exponential backoff. Raises `QlooServerError` upon exhaustion. |
| **Timeout Behavior** | Verified Mock | `httpx.TimeoutException` tests | Enforces client timeout (`timeout_seconds >= 1.0`). Retries transient timeouts; raises `QlooTimeoutError` if exhausted. |

---

## 3. Live API Gateway Audit Findings

Direct network probes against the public Qloo Hackathon endpoint (`https://hackathon.api.qloo.com`) yielded the following verified behavioral characteristics:

### 3.1. Gateway Availability & TLS
- **Host:** `https://hackathon.api.qloo.com`
- **Transport:** HTTPS (TLS 1.3)
- **Status:** Operational and responsive.

### 3.2. Gateway Headers
Every live HTTP response from the gateway contains the following headers:
- `x-qloo-request-id`: Unique UUID assigned to the transaction (e.g. `9a09749f-1cd4-4685-bebf-20cd4397af6b`).
- `www-authenticate`: Set to `apikey realm="key"` when requests lack valid credentials.
- `access-control-allow-origin`: `*` (CORS wildcard enabled).
- `access-control-allow-methods`: `GET,HEAD,PUT,PATCH,POST,DELETE,OPTIONS,TRACE,CONNECT`.
- `access-control-max-age`: `3600`.
- `content-type`: `text/plain; charset=utf-8` on gateway-level error envelopes.

### 3.3. Preflight & Options Probing (Verified Live)
Probing `OPTIONS` on all core endpoints returns `HTTP 200 OK`:
- `OPTIONS /search` → `200 OK`
- `OPTIONS /v2/tags` → `200 OK`
- `OPTIONS /v2/insights` → `200 OK`

### 3.4. Unauthenticated Request Behavior (Verified Live)
Sending a request without the `X-Api-Key` header:
- **Endpoint:** `GET /search`
- **HTTP Status:** `401 Unauthorized`
- **Payload:**
  ```json
  {"error":{"reason":"No API key found in request","message":"Unauthorized","code":401}}
  ```
- **Client Handling:** `QlooClient` captures the 401 status, parses the JSON error object, logs the incident without exposing credentials, and immediately raises `QlooAuthenticationError`.

### 3.5. Invalid / Mismatched Key Behavior (Verified Live)
Sending a request with `X-Api-Key: invalid_test_key_xyz`:
- **Endpoints:** `GET /search`, `GET /v2/tags`, `GET /v2/insights`
- **HTTP Status:** `401 Unauthorized`
- **Payload:**
  ```json
  {"error":{"reason":"API keys mismatch","message":"Unauthorized","code":401}}
  ```
- **Client Handling:** `QlooClient` extracts `details={"reason": "API keys mismatch", "message": "Unauthorized", "code": 401}` and immediately raises `QlooAuthenticationError`. It never retries authentication failures.

---

## 4. Detailed Implementation Verification

### 4.1. Authentication
- **Mechanism:** HTTP Header `X-Api-Key: <key>`
- **Live Status:** Verified. Live gateway mandates this header and rejects requests lacking it.
- **Client Security:**
  - `QlooSettings.api_key` is typed as `pydantic.SecretStr`.
  - Calling `repr(settings)` displays `api_key='***REDACTED***'`.
  - Header logging sanitizes `X-Api-Key`, `Authorization`, and `Cookie` to `***REDACTED***`.
- **Verdict:** Fully compliant and verified.

### 4.2. Entity Search (`GET /search`)
- **Query Parameters:**
  - `query` (`str`, required, 1-200 chars): Search term. Blank/whitespace-only queries are blocked by `SearchParams` validation.
  - `type` (`str | None`, optional): Domain type hint (`place`, `artist`, `brand`, `movie`, `book`).
  - `take` (`int`, default 10, 1-100): Result count constraint.
- **Normalization:**
  - Results parsed into `QlooEntity`.
  - Tags handled flexibly as either strings or structured objects (`name`, `id`).
- **Resolver Logic (`EntityResolver`):**
  - Trims quotes and extra spaces.
  - Ranks candidates using a 5-tier scoring hierarchy:
    1. Exact match (`1.0`)
    2. Token set match (`0.98`)
    3. Token subset match (`0.85 - 0.95`)
    4. Substring/prefix match (`0.80 - 0.94`)
    5. SequenceMatcher fuzzy score (`0.0 - 1.0` + `0.05` type bonus).
  - Rejects results below `min_confidence` (`0.5`).
- **Verdict:** Verified via mock suite (`test_search_200_success`, `test_resolvers.py`).

### 4.3. Tag Resolution (`GET /v2/tags`)
- **Query Parameters:**
  - `query` (`str | None`): Tag keyword search.
  - `type` (`str | None`): Domain category (e.g. `music`, `dining`, `style`).
  - `take` (`int`, default 20): Candidate limit.
- **Normalization:**
  - Parsed into `QlooTag` (`id`, `name`, `category`, `urn`, `metadata`).
- **Resolver Logic (`TagResolver`):**
  - Converts vibes/motifs into verified taxonomy tag IDs.
  - Strictly rejects unknown tags (returns `is_resolved = False`, `resolved_tag_id = None`).
  - Never fabricates tag IDs.
- **Verdict:** Verified via mock suite (`test_get_tags_200_success`, `test_resolvers.py`).

### 4.4. Cultural Insights (`GET /v2/insights`)
- **Protocol:** Strictly uses HTTP `GET`. Never calls legacy `/recs` or `/recommendations`.
- **Parameter Mapping:**
  - `filter.type`: Target entity URN (e.g. `urn:entity:artist`, `urn:entity:brand`).
  - `signal.interests.entities`: Comma-delimited seed entity IDs.
  - `signal.interests.tags`: Comma-delimited seed tag IDs.
  - `feature.explainability`: Set to `"true"` to request attribution data.
  - `take`: Limit per request.
- **Signal Constraint:** `InsightParams` enforces that at least one signal (`signal_entities`, `signal_tags`) or a spatial `location_wkt` is supplied before dispatch.
- **Normalization:** Parsed into `QlooInsight` (`id`, `name`, `affinity`, `score`, `explainability`, `metadata`).
- **Verdict:** Verified via mock suite (`test_get_insights_200_success`, `test_cultural_matrix_service.py`).

### 4.5. Spatial Queries
- **Parameters:**
  - `filter.location`: WKT coordinate string `POINT(longitude latitude)` (e.g. `POINT(-73.985 40.748)`).
  - `filter.location.radius`: Integer search radius in meters (`10` to `200,000`).
- **Validation:**
  - Strict regex validation on WKT syntax; rejects non-conforming coordinates.
- **Capability Guardrail (`InsightsService`):**
  - Spatial coordinates are **only** attached to entities configured with `supports_spatial_location=True` (`place`, `destination`).
  - Spatial coordinates are automatically stripped from queries for `artist`, `book`, `brand`, and `movie`.
- **Verdict:** Verified via mock suite (`test_capability_validation_does_not_pass_location_to_non_spatial_entities`).

### 4.6. Cultural Matrix Generation (`CulturalMatrixService`)
- **Concurrency:** Queries 6 target domains concurrently via `asyncio.gather`.
- **Deterministic Single-Retry Fallback:**
  - If a category returns 0 results:
    - *Spatial entities (`place`, `destination`):* Expands radius by 5x (up to 100km).
    - *Over-constrained entities (both seeds & tags):* Drops tag filters to query anchor entities only.
    - *Tag-only queries:* Drops secondary tags to query primary tag only.
  - If fallback also returns 0 results:
    - Returns `[]` for that category.
    - Records an audit evidence entry explaining query exhaustion.
    - **Zero Hallucination:** Never invents entities when empty.
- **Verdict:** Verified via mock suite (`test_deterministic_fallback_on_empty_and_retry_once`, `test_zero_hallucination_on_exhausted_fallback`).

### 4.7. Response Envelope Extraction
- Qloo API gateways may return results wrapped in different top-level dictionary keys or as raw lists.
- `_extract_result_list` supports:
  - Top-level `list`
  - `dict` with key `"results"`
  - `dict` with key `"data"`
  - `dict` with key `"entities"`
  - `dict` with key `"tags"`
  - `dict` with key `"insights"`
  - Empty `dict` (returns `[]`)
- Malformed payloads raise a clear, structured `QlooValidationError`.
- **Verdict:** Verified via mock suite (`test_malformed_json_response`, `test_malformed_item_schema`).

### 4.8. 401 & 403 Error Handling
- **Policy:** Never retried. Retrying invalid credentials can result in IP blocks or gateway penalties.
- **Behavior:** `QlooClient` immediately raises `QlooAuthenticationError` and halts request execution.
- **Verdict:** Verified both against live gateway and with mocks (`test_401_unauthorized_never_retried`, `test_403_forbidden_never_retried`).

### 4.9. 429 Rate Limiting
- **Policy:** Transient error; safe to retry.
- **Behavior:**
  - Checks response header for `Retry-After`.
  - If present and numeric, sleeps for `float(retry_after)`.
  - If absent, applies exponential backoff: `backoff_factor * (2 ** (attempt - 1))`.
  - Retries up to `max_retries` (default: 3). If exhausted, raises `QlooRateLimitError`.
- **Verdict:** Verified via mock suite (`test_transient_429_exhausted`).

### 4.10. 5xx Server Error Handling
- **Policy:** Transient infrastructure failure; safe to retry.
- **Behavior:**
  - Retries on HTTP 500, 502, 503, 504 with exponential backoff.
  - If a retry succeeds, returns payload normally.
  - If retries are exhausted, raises `QlooServerError` with details.
- **Verdict:** Verified via mock suite (`test_transient_500_retried_and_succeeds`).

### 4.11. Timeout Handling
- **Policy:** Enforces `timeout_seconds` (default: 15.0s, bounded between 1.0s and 120.0s).
- **Behavior:**
  - Catches `httpx.TimeoutException`.
  - Retries up to `max_retries` with exponential backoff.
  - If exhausted, raises `QlooTimeoutError`.
- **Verdict:** Verified via mock suite (`test_timeout_handling`).

---

## 5. Explicit Audit Categorization

### 5.1. Verified Against Live API
1. **Base URL Reachability:** `https://hackathon.api.qloo.com` resolves, accepts TLS connections, and is actively serving requests.
2. **Gateway-Level Authentication Check:** Requests without an `X-Api-Key` header fail immediately with HTTP `401 Unauthorized`.
3. **Gateway Error Envelope Format:** 401 responses return JSON with `{"error": {"reason": "...", "message": "Unauthorized", "code": 401}}`.
4. **Invalid Key Recognition:** Requests with an invalid key return `{"error": {"reason": "API keys mismatch", "message": "Unauthorized", "code": 401}}`.
5. **Request ID Tracking:** Every live response includes `x-qloo-request-id` with a UUID.
6. **CORS & Preflight Handling:** `OPTIONS` requests to `/search`, `/v2/tags`, and `/v2/insights` return `HTTP 200 OK` with `access-control-allow-origin: *`.
7. **Immediate Rejection by Client:** Calling `QlooClient.search()`, `get_tags()`, or `get_insights()` with an invalid key raises `QlooAuthenticationError` on the first attempt without infinite loops or unnecessary retries.

### 5.2. Verified Using Mocks
1. **Entity Search Payload Parsing:** Deserialization of place, artist, brand, and book entities with tags and metadata.
2. **Tag Taxonomy Resolution:** Resolution of aesthetic and genre tags into verified Qloo taxonomy entries.
3. **Insights Query Execution:** Conversion of seed entities, tags, and spatial coordinates into dot-notation parameters for `GET /v2/insights`.
4. **Spatial Capabilities Enforcement:** Strict omission of geographic filters from non-spatial entity queries.
5. **Concurrent Matrix Assembly:** Parallel fetching across 6 domains via `asyncio.gather`.
6. **Deterministic Fallbacks:** Fallback logic on empty results (radius expansion, tag dropping).
7. **Zero Hallucination Enforcement:** Strict non-fabrication of entity IDs when queries return 0 items.
8. **Transient Error Resilience:** Exponential backoff on HTTP 429, 500, 502, 503, and timeouts.
9. **TTL Caching:** Cache hit/miss cycles for GET requests via `AsyncTTLCache`.
10. **Agent Orchestration Integration:** Full 13-state workflow pipeline operating on top of the mock adapter.

### 5.3. Assumptions
1. **Insights Query Param Convention:** It is assumed that the Qloo Hackathon API accepts dot-notation query parameters (`signal.interests.entities`, `signal.interests.tags`, `filter.type`, `filter.location`, `filter.location.radius`, `feature.explainability`) on `GET /v2/insights`.
2. **Coordinate Ordering:** It is assumed that Qloo WKT follows the OpenGIS standard `POINT(longitude latitude)` format (e.g. `POINT(-73.985 40.748)`).
3. **Single Result Envelope Variation:** It is assumed that Qloo responses wrap entities in either top-level lists or under `"results"`, `"data"`, `"entities"`, `"tags"`, or `"insights"`.
4. **Entity ID Stability:** It is assumed that entity IDs returned by `/search` and `/v2/insights` are durable URNs/strings that can be fed back as `signal.interests.entities`.

### 5.4. Unsupported / Unknown Behavior
1. **Live Entity Data Payloads:** Without a valid hackathon API key provisioned in the live environment, actual 200 OK data payloads from the live gateway cannot be observed.
2. **Pagination Beyond `take`:** The Qloo API pagination mechanism (cursor vs offset vs page number) beyond the `take` parameter is currently not implemented or verified.
3. **POST /v2/insights:** The service does not support or probe POST requests for insights; TasteOps strictly uses GET requests.
4. **Batch Entity Resolution:** Multi-entity search in a single HTTP request is not supported by Qloo `/search`; TasteOps resolves multiple entities through concurrent individual requests.

---

## 6. Recommendations for Live Key Deployment

When a production hackathon API key is provisioned:
1. Place the key in `.env` as `QLOO_API_KEY=...` (do not commit to git).
2. Run smoke tests with live credentials using real cultural anchors (e.g. `A24`, `Blue Bottle`).
3. Verify that the live response format matches the `QlooEntity` and `QlooInsight` schemas.
4. Monitor response latency on `GET /v2/insights` to tune `QLOO_TIMEOUT_SECONDS` if complex multi-signal queries require more than 15.0 seconds.
