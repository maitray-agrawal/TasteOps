"""TasteOps AI Operations Workspace Frontend Route Tests.

Verifies:
- All 8 canonical workspace screens serve the single-page application shell:
  1. /dashboard
  2. /spaces/new
  3. /spaces/[spaceId]
  4. /sessions/[sessionId]
  5. /sessions/[sessionId]/blueprint
  6. /sessions/[sessionId]/approval
  7. /sessions/[sessionId]/execution
  8. /sessions/[sessionId]/ledger
- Static CSS and JavaScript asset resolution (/static/css/index.css, /static/js/apiClient.js, etc.)
- Security verification: Provider secrets (QLOO_API_KEY, GROQ_API_KEY, GEMINI_API_KEY, DATABASE_URL)
  are NEVER embedded or exposed in frontend static assets or HTML shells.
"""

from __future__ import annotations

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from tasteops.api.app import create_app
from tasteops.api.settings import APISettings


@pytest.fixture
def client():
    settings = APISettings(environment="testing", api_debug=True)
    app = create_app(settings=settings)
    with TestClient(app) as tc:
        yield tc


# =============================================================================
# 1. Workspace Screen Route Tests
# =============================================================================
@pytest.mark.parametrize(
    "route_path",
    [
        "/",
        "/dashboard",
        "/spaces/new",
        "/spaces/space_demo_123",
        "/sessions/sess_demo_123",
        "/sessions/sess_demo_123/blueprint",
        "/sessions/sess_demo_123/approval",
        "/sessions/sess_demo_123/execution",
        "/sessions/sess_demo_123/ledger",
    ],
)
def test_all_canonical_screens_served_by_fastapi(client, route_path):
    """Verifies all 8 required workspace screen routes return HTTP 200 and the HTML SPA shell."""
    resp = client.get(route_path)
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "<title>TasteOps — AI Operations Workspace</title>" in resp.text
    assert 'id="app-nav"' in resp.text
    assert 'id="app-main"' in resp.text
    assert 'src="/static/js/app.js"' in resp.text


# =============================================================================
# 2. Static Asset Resolution Tests
# =============================================================================
@pytest.mark.parametrize(
    "asset_path,content_type_substr",
    [
        ("/static/css/index.css", "text/css"),
        ("/static/js/app.js", "javascript"),
        ("/static/js/apiClient.js", "javascript"),
        ("/static/js/router.js", "javascript"),
        ("/static/js/components/nav.js", "javascript"),
        ("/static/js/components/ui.js", "javascript"),
        ("/static/js/screens/dashboard.js", "javascript"),
        ("/static/js/screens/spaceNew.js", "javascript"),
        ("/static/js/screens/spaceDetail.js", "javascript"),
        ("/static/js/screens/sessionDetail.js", "javascript"),
        ("/static/js/screens/sessionBlueprint.js", "javascript"),
        ("/static/js/screens/sessionApproval.js", "javascript"),
        ("/static/js/screens/sessionExecution.js", "javascript"),
        ("/static/js/screens/sessionLedger.js", "javascript"),
    ],
)
def test_static_assets_served_correctly(client, asset_path, content_type_substr):
    """Verifies all CSS stylesheets and ES module scripts resolve with valid mime types."""
    resp = client.get(asset_path)
    assert resp.status_code == 200
    assert content_type_substr in resp.headers["content-type"]
    assert len(resp.text) > 50


# =============================================================================
# 3. Security Verification: No Secrets Exposed to Browser
# =============================================================================
def test_no_provider_secrets_exposed_in_frontend():
    """Verifies that provider API keys and database URLs are never written into static frontend assets."""
    static_root = Path(__file__).resolve().parent.parent.parent / "src" / "tasteops" / "api" / "static"
    assert static_root.exists()

    forbidden_patterns = [
        "QLOO_API_KEY",
        "GROQ_API_KEY",
        "GEMINI_API_KEY",
        "DATABASE_URL",
        "sk-ant",
        "ghp_",
    ]

    for file_path in static_root.rglob("*"):
        if file_path.is_file():
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            for pattern in forbidden_patterns:
                assert pattern not in text, f"Found sensitive secret pattern '{pattern}' in {file_path}"
