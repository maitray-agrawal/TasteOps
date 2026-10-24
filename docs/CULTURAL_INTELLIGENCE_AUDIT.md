# TasteOps Cultural Intelligence — Anti-Hallucination Audit Report

**Audit Date:** October 25, 2026
**Scope:** Cultural Intelligence Layer Anti-Hallucination & Provenance Verification
**Audited Components:** `QlooClient`, `EntityResolver`, `TagResolver`, `InsightsService`, `CulturalMatrixService`, `GovernanceAgent`
**Regression Test Suite:** `tests/unit/test_cultural_intelligence_audit.py`

---

## 1. Executive Summary

This audit evaluates the TasteOps Cultural Intelligence layer specifically against the risks of hallucinated entity identifiers, fabricated affinity metrics, invented brand/artist names, and ungrounded recommendation evidence.

TasteOps enforces a strict zero-hallucination policy:
1. **Zero Invented Qloo IDs:** No agent, resolver, or service ever invents, synthesizes, or predicts a Qloo entity or tag identifier. Every ID must originate from a verified Qloo API response.
2. **Zero Invented Affinity Scores:** Numerical affinity scores, confidence rankings, and resonance metrics originate directly from Qloo Insights telemetry. No synthetic scores are generated when results are empty.
3. **Zero Invented Entity Names:** Candidates retain exact names and metadata returned by Qloo. No composite, hybrid, or generic placeholder names are ever synthesized.
4. **Zero Recommendation Without Provider Evidence:** Recommendations cannot be emitted or approved for physical space execution without complete, traceable Qloo provenance (`source_query`, `source_signal`, `explainability`).

---

## 2. Failure Mode Audit & Verification

### 2.1. Unknown Entity
- **Scenario:** Natural language query does not correspond to any known cultural entity in Qloo (e.g. `"ZzzNonExistentAnchor9999XYZ"`).
- **Behavior:**
  - `QlooClient.search()` returns `[]`.
  - `EntityResolver.resolve()` detects 0 candidate matches.
  - Returns `EntityResolutionResult` with:
    - `is_resolved = False`
    - `resolved_entity_id = None`
    - `entity = None`
    - `confidence = 0.0`
    - `evidence.match_method = "unresolved_no_results"`
    - `alternatives = []`
- **Guarantee:** Never fabricates a placeholder entity ID or guesses an entity name.
- **Regression Test:** `test_unknown_entity_returns_unresolved_zero_invented_id` (PASSED).

### 2.2. Ambiguous Entity
- **Scenario:** A search query matches multiple valid candidates with similar names (e.g. `"Chelsea"` matching `"Chelsea Market"`, `"Chelsea Hotel"`, and `"Chelsea Piers"`).
- **Behavior:**
  - `EntityResolver` scores all candidates using deterministic string heuristics (exact, token set, token subset, prefix, fuzzy similarity).
  - Selects the single highest-scoring candidate as the primary match if it satisfies `min_confidence`.
  - Preserves all other candidates in `alternatives: list[EntityCandidate]`, retaining each candidate's exact Qloo ID, entity name, type, and individual confidence score.
- **Guarantee:** Never creates a synthetic hybrid entity (e.g. `"Chelsea Generic"`) or merges candidate IDs.
- **Regression Test:** `test_ambiguous_entity_preserves_candidates_no_invented_composite` (PASSED).

### 2.3. Unknown Tag
- **Scenario:** A user brief provides an unsupported aesthetic motif, subcultural term, or vibe not present in the Qloo taxonomy (e.g. `"hyperpop-polka-fusion-vibes-999"`).
- **Behavior:**
  - `QlooClient.get_tags()` returns `[]`.
  - `TagResolver.resolve()` rejects the term.
  - Returns `TagResolutionResult` with:
    - `is_resolved = False`
    - `resolved_tag_id = None`
    - `tag_name = None`
    - `confidence = 0.0`
    - `evidence.match_method = "rejected_unknown_tag"`
- **Guarantee:** Unknown tags are strictly omitted from downstream cultural twin signals; no synthetic taxonomy IDs are created.
- **Regression Test:** `test_unknown_tag_returns_unresolved_zero_invented_id` (PASSED).

### 2.4. Low-Confidence Entity
- **Scenario:** A provider search returns candidates, but none satisfy the configured confidence threshold (`min_confidence = 0.50`), such as searching `"Blue Bottle"` and receiving `"Xylophone Specialty Store"`.
- **Behavior:**
  - `EntityResolver` calculates similarity (`score < 0.50`).
  - Flags the match as below threshold.
  - Logs a warning: `Top candidate '...' was below min_confidence 0.50. Rejected.`
  - Returns:
    - `is_resolved = False`
    - `resolved_entity_id = None`
    - `entity = None`
    - `confidence = score` (< 0.50)
    - `evidence.match_method = "rejected_below_confidence"`
- **Guarantee:** Weak matches are never forced into acceptance or promoted to verified anchors.
- **Regression Test:** `test_low_confidence_entity_strictly_rejected` (PASSED).

### 2.5. Empty Response & Exhausted Fallback
- **Scenario:** Qloo Insights returns 0 items for an initial category query, and a subsequent broadened fallback query (e.g. expanded spatial radius or dropped tags) also returns 0 items.
- **Behavior:**
  - `CulturalMatrixService` executes the single deterministic fallback query.
  - When the fallback also returns 0 results, the service terminates without further retries.
  - Returns `[]` for that category.
  - Records telemetry in `CategoryQueryMetadata(status="fallback_empty", items_count=0, retries=1)`.
  - Records an audit entry in `CulturalMatrixEvidence` stating: `Category returned 0 results after initial attempt and broadened fallback (...). Zero items hallucinated.`
- **Guarantee:** Zero recommendations returned; zero fake affinity scores invented.
- **Regression Test:** `test_empty_response_exhausted_fallback_zero_hallucination` (PASSED).

### 2.6. Malformed Provider Response
- **Scenario:** An external API endpoint returns non-JSON text, an unrecognized envelope structure, or missing expected keys.
- **Behavior:**
  - `QlooClient._extract_result_list()` validates response envelopes (`results`, `data`, `entities`, `tags`, `insights`).
  - Unrecognized payloads raise `QlooValidationError`.
  - In `CulturalMatrixService`, the category query task safely traps the exception:
    - Sets category items to `[]`.
    - Logs the root cause error.
    - Records `CategoryQueryMetadata(status="empty" | "error", items_count=0)`.
  - In MCP tools, the error is caught and converted to a structured JSON error envelope containing `request_id` and the root cause message.
- **Guarantee:** Malformed payloads fail safely without injecting corrupted or hallucinated entries.
- **Regression Test:** `test_malformed_provider_response_handled_gracefully` (PASSED).

### 2.7. Partial Category Failure
- **Scenario:** During a multi-category CulturalMatrix generation (e.g. querying artists, books, brands, places, movies, destinations), 2 categories fail (e.g. HTTP 500 error on books, malformed response on movies), while 4 categories succeed.
- **Behavior:**
  - `CulturalMatrixService` dispatches category tasks concurrently via `asyncio.gather(*tasks, return_exceptions=True)`.
  - Exceptions in individual categories do not abort sibling category executions.
  - Sibling categories populate recommendations with full provenance (`artists`, `brands`, `places`, `destinations`).
  - Failed categories remain strictly empty lists (`books = []`, `movies = []`).
  - `query_metadata` records `"success"` for healthy categories and `"empty"` / `"error"` for failed ones.
- **Guarantee:** Fault isolation prevents partial failures from contaminating healthy domains or triggering synthetic data generation.
- **Regression Test:** `test_partial_category_failure_resilience` (PASSED).

---

## 3. Agent Pipeline Anti-Hallucination Guardrails

| Agent | Responsibility | Anti-Hallucination Mechanism |
| :--- | :--- | :--- |
| **Cultural Strategist** | Formulates `CulturalTwin` from user brief | Resolves all anchors and vibes via MCP tools. Only includes verified IDs in `resolved_entities` and `resolved_tags`. Unresolved terms are kept as raw unverified anchors and excluded from Qloo signal parameters. |
| **Experience Architect** | Curates 6 cultural experience domains | Filters exclusively from verified `CulturalMatrix` candidates. Enforces affinity threshold ($\ge 0.50$) and prunes exclusions. Never invents candidate artists, books, or brands. |
| **Partnership Agent** | Scores and selects brand partners | Operates strictly on `CulturalMatrix.brands`. Computes 6-dimensional fit score from provider affinity and venue constraints. Outreach letters are exploratory drafts; `is_existing_partner = False` is enforced. |
| **Governance Agent** | Audits plan & enforces approval gate | Executes 7-point automated audit before human review. Verifies that 100% of recommendations carry valid provider evidence. Blocks execution if any task lacks provenance or carries an unverified/synthetic ID (`validate_task_provenance`). |

---

## 4. Verification Matrix & Test Status

| Audit Case | Mechanism Tested | Failure Behavior | Test Result |
| :--- | :--- | :--- | :--- |
| **Unknown Entity** | `EntityResolver.resolve` | `is_resolved=False`, `resolved_entity_id=None`, `confidence=0.0` | **PASSED** |
| **Ambiguous Entity** | `EntityResolver.resolve` | Preserves candidates in `alternatives`, zero synthetic hybrid names | **PASSED** |
| **Unknown Tag** | `TagResolver.resolve` | `is_resolved=False`, `resolved_tag_id=None`, zero tag ID fabrication | **PASSED** |
| **Low-Confidence Entity** | `EntityResolver.resolve` | Rejects matches below `min_confidence=0.50` (`match_method="rejected_below_confidence"`) | **PASSED** |
| **Empty Response & Fallback** | `CulturalMatrixService` | Returns `[]`, records fallback exhaustion in metadata and evidence | **PASSED** |
| **Malformed Response** | `QlooClient` + `CulturalMatrixService` | Traps `QlooValidationError`, returns `[]`, records error in metadata | **PASSED** |
| **Partial Category Failure** | `CulturalMatrixService` | Healthy domains succeed, failed domains remain `[]`, zero cross-contamination | **PASSED** |
| **Provenance Integrity** | `GovernanceAgent.validate_task_provenance` | Raises `ProvenanceValidationError` on missing or unverified provider IDs | **PASSED** |

All 8 audit scenarios are covered by automated regression tests in [`tests/unit/test_cultural_intelligence_audit.py`](file:///D:/TasteOps/tests/unit/test_cultural_intelligence_audit.py).
