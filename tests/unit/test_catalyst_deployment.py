"""Unit tests for Zoho Catalyst deployment packaging and asset resolution."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scripts.sync_catalyst_deployment import (
    ensure_catalyst_configs,
    get_paths,
    sync_client_assets,
    validate_catalyst_client,
)


def test_catalyst_client_synchronization_and_asset_resolution(tmp_path: Path):
    """Validates that sync_client_assets transforms /static/ paths and satisfies all Catalyst constraints."""
    _, src_static, _ = get_paths()
    test_client_dir = tmp_path / "client"
    test_deploy_dir = tmp_path / "deploy"
    app_sail_url = "https://tasteops-backend-50047164098.development.catalystappsail.in"

    sync_client_assets(src_static, test_client_dir, api_url=app_sail_url)
    ensure_catalyst_configs(test_deploy_dir)

    # 1. Validate that index.html exists and is adapted for /app/ hosting
    index_file = test_client_dir / "index.html"
    assert index_file.exists()
    content = index_file.read_text(encoding="utf-8")

    assert '<base href="/app/">' in content
    assert 'href="css/index.css"' in content
    assert 'src="config.js"' in content
    assert 'src="js/app.js"' in content
    assert "/static/" not in content
    assert f'content="{app_sail_url}"' in content

    # 2. Validate that config.js has the AppSail URL injected
    config_file = test_client_dir / "config.js"
    assert config_file.exists()
    config_content = config_file.read_text(encoding="utf-8")
    assert f"const defaultRemote = '{app_sail_url}';" in config_content

    # 3. Validate that screen scripts do not contain /static/images/
    splash_file = test_client_dir / "js" / "screens" / "splash.js"
    assert splash_file.exists()
    assert '"/static/images/' not in splash_file.read_text(encoding="utf-8")
    assert '"images/splash_arch.jpg"' in splash_file.read_text(encoding="utf-8")

    dashboard_file = test_client_dir / "js" / "screens" / "dashboard.js"
    assert dashboard_file.exists()
    assert '"/static/images/' not in dashboard_file.read_text(encoding="utf-8")
    assert '"images/hero_interior.jpg"' in dashboard_file.read_text(encoding="utf-8")

    # 4. Validate client-package.json schema (conforming to basic client, no 404: index.html)
    pkg_file = test_client_dir / "client-package.json"
    assert pkg_file.exists()
    pkg_data = json.loads(pkg_file.read_text(encoding="utf-8"))
    assert pkg_data.get("name") == "tasteops-client"
    assert pkg_data.get("homepage") == "index.html"
    assert "404" not in pkg_data

    # 5. Validate catalyst.json schema
    cat_file = test_deploy_dir / "catalyst.json"
    assert cat_file.exists()
    cat_data = json.loads(cat_file.read_text(encoding="utf-8"))
    assert cat_data.get("client", {}).get("source") == "client"

    # 6. Validate that validate_catalyst_client passes with zero errors
    validate_catalyst_client(test_client_dir)


def test_catalyst_validation_detects_unresolved_static(tmp_path: Path):
    """Validation must raise RuntimeError if an unmigrated /static/ reference is present."""
    client_dir = tmp_path / "bad_client"
    client_dir.mkdir()
    index_file = client_dir / "index.html"
    index_file.write_text(
        '<!DOCTYPE html><html><head><base href="/app/"><script src="/static/config.js"></script></head><body></body></html>',
        encoding="utf-8",
    )
    (client_dir / "config.js").write_text("", encoding="utf-8")
    (client_dir / "css").mkdir()
    (client_dir / "css" / "index.css").write_text("", encoding="utf-8")
    (client_dir / "js").mkdir()
    (client_dir / "js" / "app.js").write_text("", encoding="utf-8")
    (client_dir / "js" / "router.js").write_text("", encoding="utf-8")
    (client_dir / "js" / "apiClient.js").write_text("", encoding="utf-8")
    (client_dir / "images").mkdir()
    (client_dir / "images" / "splash_arch.jpg").write_text("", encoding="utf-8")
    (client_dir / "images" / "hero_interior.jpg").write_text("", encoding="utf-8")
    (client_dir / "client-package.json").write_text("{}", encoding="utf-8")

    with pytest.raises(
        RuntimeError, match="contains unresolved /static/ path references"
    ):
        validate_catalyst_client(client_dir)


def test_router_screens_signature_compatibility():
    """All screen modules must accept (rootElement, params, router) matching Router.resolve()."""
    _, src_static, _ = get_paths()
    screens_dir = src_static / "js" / "screens"
    assert screens_dir.exists()

    render_fn_pattern = re.compile(
        r"export\s+(?:async\s+)?function\s+(render\w+)\s*\(([^)]*)\)"
    )

    for screen_file in screens_dir.glob("*.js"):
        content = screen_file.read_text(encoding="utf-8")
        matches = render_fn_pattern.findall(content)
        assert matches, f"Screen {screen_file.name} does not export a render function"
        for fn_name, params_str in matches:
            params = [p.strip() for p in params_str.split(",") if p.strip()]
            assert len(params) == 3, (
                f"{screen_file.name}:{fn_name} must accept 3 parameters (rootElement, params, router), "
                f"found {len(params)}: ({params_str})"
            )
            assert params[0] == "rootElement"
            assert params[1] == "params"
            assert params[2] == "router"


def test_splash_screen_enter_tasteops_navigation_path():
    """splash.js Enter TasteOps button must navigate to /home using resolved router instance."""
    _, src_static, _ = get_paths()
    splash_file = src_static / "js" / "screens" / "splash.js"
    assert splash_file.exists()
    content = splash_file.read_text(encoding="utf-8")

    # Verify signature
    assert "export function renderSplash(rootElement, params, router)" in content

    # Verify router resolution fallback
    assert "actualRouter" in content
    assert "actualRouter.navigate('/home')" in content
    assert "btn-enter-tasteops" in content
