# TasteOps — Cultural Intelligence Infrastructure

> Cultural Intelligence Operating System for Physical Spaces.

This package provides the core Cultural Intelligence infrastructure for **TasteOps**, integrating with Qloo's Taste AI™ APIs behind a secure service abstraction layer and exposing a Model Context Protocol (MCP) server for agent orchestration.

---

## 🏛️ Architecture Overview

```
TasteOps/
├── src/tasteops/
│   ├── config.py             # QlooSettings (SecretStr masking, configurable base URL)
│   ├── exceptions.py         # Normalized Qloo error hierarchy
│   ├── client.py             # QlooClient (async HTTP, retries, 401/403 exclusion)
│   ├── models/
│   │   ├── entity.py         # QlooEntity
│   │   ├── tag.py            # QlooTag
│   │   ├── insight.py        # QlooInsight
│   │   ├── error.py          # QlooError
│   │   ├── params.py         # SearchParams, TagParams, InsightParams
│   │   ├── resolution.py     # EntityResolutionResult, TagResolutionResult, ResolutionEvidence
│   │   └── cultural_matrix.py# CulturalTwin, CulturalMatrix, CulturalRecommendation
│   ├── services/
│   │   ├── entity_resolver.py# Resolves natural language cultural anchors
│   │   ├── tag_resolver.py   # Resolves aesthetic and vibe taxonomy tags
│   │   ├── insights_service.py # Capability-aware Qloo insights queries
│   │   └── cultural_matrix_service.py # Holistic CulturalMatrix with fallback retries
│   └── mcp/
│       ├── server.py         # MCPServer exposing high-level tools
│       └── schemas.py        # Strict MCP tool schemas
└── tests/
    ├── conftest.py
    └── unit/
        ├── test_qloo_client.py
        ├── test_resolvers.py
        ├── test_cultural_matrix_service.py
        └── test_mcp_server.py
```

---

## 🔒 Security & Developer Hygiene

1. **No Raw HTTP Exposure**: The application never invokes raw HTTP or requests directly against Qloo. All interactions pass through typed service interfaces.
2. **Key Masking**: `QLOO_API_KEY` is loaded as a `SecretStr`. It is masked in string representations (`***REDACTED***`) and stripped from all request logging.
3. **Zero Hallucination / No Fabrication**: If Qloo returns 0 results or candidates are below confidence thresholds, results return `None` or `[]`. The system never invents entity or tag IDs.
4. **Git Hygiene**: `.env` and Qloo response datasets are strictly ignored via `.gitignore`.

---

## 🛠️ MCP Tools

The Model Context Protocol server exposes high-level cultural intelligence tools to AI agents:

| Tool | Purpose | Input Sample |
| :--- | :--- | :--- |
| `health_check` | Diagnostics & base URL verification | `{}` |
| `resolve_entity` | Maps natural language cultural anchors to verified Qloo entities | `{"query": "A24", "expected_type": "brand"}` |
| `resolve_tag` | Maps aesthetic vibes to verified taxonomy tags | `{"query": "Japanese minimalism", "expected_category": "style"}` |
| `get_cultural_profile` | Cross-domain profile for a single anchor | `{"entity_name": "Blue Bottle Coffee", "take": 5}` |
| `get_related_artists` | High-affinity music recommendations | `{"anchor_entities": ["ent_1"], "take": 10}` |
| `get_related_books` | High-affinity literature and design books | `{"anchor_entities": ["ent_1"], "take": 10}` |
| `get_related_brands` | High-affinity lifestyle & design brands | `{"anchor_entities": ["ent_1"], "take": 10}` |
| `get_related_places` | High-affinity venues with spatial radius | `{"anchor_entities": ["ent_1"], "latitude": 40.74, "longitude": -73.98, "radius_meters": 3000}` |
| `get_related_movies` | High-affinity films & cinema references | `{"anchor_entities": ["ent_1"], "take": 10}` |
| `get_cultural_matrix` | Holistic multidimensional space matrix | `{"cultural_twin": {...}, "take_per_category": 10}` |

### Running the MCP Server
```bash
uv run tasteops-mcp
```

---

## 🧪 Running Tests

The test suite covers:
- HTTP 200, 401, 403, 404, 429, 500, and timeouts
- Non-retry guarantee for authentication failures
- Entity and tag resolution with candidate ranking and provenance
- Capability enforcement (spatial vs non-spatial entities)
- Concurrent execution and single-retry deterministic fallback
- Every single MCP tool

```bash
uv run pytest -v
```
