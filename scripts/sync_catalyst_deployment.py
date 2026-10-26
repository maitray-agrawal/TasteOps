"""TasteOps Catalyst Deployment Preparation and Synchronization Tool.

Synchronizes canonical static frontend assets from `src/tasteops/api/static` to
`deploy/catalyst/client`, transforms root-relative `/static/` references to resolve
cleanly under Catalyst Web Client Hosting (`/app/`), validates asset resolution,
and provides CLI configuration for the remote AppSail API URL.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path


def get_paths() -> tuple[Path, Path, Path]:
    repo_root = Path(__file__).resolve().parent.parent
    src_static = repo_root / "src" / "tasteops" / "api" / "static"
    deploy_dir = repo_root / "deploy" / "catalyst"
    client_dir = deploy_dir / "client"
    return repo_root, src_static, client_dir


def transform_index_html(index_file: Path, api_url: str | None = None) -> None:
    """Transforms index.html for Catalyst Web Client Hosting under /app/."""
    content = index_file.read_text(encoding="utf-8")

    # 1. Transform /static/ asset references to relative paths
    content = content.replace('href="/static/css/index.css"', 'href="css/index.css"')
    content = content.replace('src="/static/config.js"', 'src="config.js"')
    content = content.replace('src="/static/js/app.js"', 'src="js/app.js"')

    # 2. Inject <base href="/app/"> inside <head> if not already present
    if '<base href="/app/">' not in content:
        # Place base tag right after meta charset
        content = re.sub(
            r'(<meta charset="UTF-8"\s*\/?>)',
            r'\1\n  <base href="/app/">',
            content,
            count=1,
        )

    # 3. Inject catalyst-api-base-url meta tag if api_url is provided
    if api_url:
        clean_url = api_url.rstrip("/")
        meta_tag = f'  <meta name="catalyst-api-base-url" content="{clean_url}" />'
        if 'name="catalyst-api-base-url"' in content:
            content = re.sub(
                r'<meta name="catalyst-api-base-url"[^>]*\/?>',
                meta_tag.strip(),
                content,
            )
        else:
            content = content.replace(
                "</head>",
                f"{meta_tag}\n</head>",
            )

    index_file.write_text(content, encoding="utf-8")


def transform_client_scripts(client_dir: Path) -> None:
    """Transforms /static/ asset paths in copied JavaScript files."""
    for js_file in client_dir.glob("**/*.js"):
        content = js_file.read_text(encoding="utf-8")
        modified = False

        if "/static/images/" in content:
            content = content.replace('"/static/images/', '"images/')
            content = content.replace("'/static/images/", "'images/")
            modified = True

        if modified:
            js_file.write_text(content, encoding="utf-8")


def sync_client_assets(
    src_static: Path, client_dir: Path, api_url: str | None = None
) -> None:
    """Copies canonical static files to deploy/catalyst/client and adapts for Catalyst."""
    if not src_static.exists():
        raise FileNotFoundError(f"Source static directory not found: {src_static}")

    client_dir.mkdir(parents=True, exist_ok=True)

    # Copy all files and directories from canonical src_static to client_dir
    for item in src_static.iterdir():
        dest = client_dir / item.name
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    # Transform index.html for Catalyst /app/ hosting
    index_file = client_dir / "index.html"
    transform_index_html(index_file, api_url)

    # Transform script image references
    transform_client_scripts(client_dir)

    # Ensure client-package.json conforms to official Catalyst basic client schema
    client_pkg_file = client_dir / "client-package.json"
    client_pkg = {
        "name": "tasteops-client",
        "version": "0.1.0",
        "homepage": "index.html",
    }
    client_pkg_file.write_text(
        json.dumps(client_pkg, indent=2) + "\n", encoding="utf-8"
    )

    # If an AppSail API URL was supplied, configure it in deploy/catalyst/client/config.js
    if api_url:
        config_file = client_dir / "config.js"
        clean_url = api_url.rstrip("/")
        content = config_file.read_text(encoding="utf-8")
        updated = re.sub(
            r"const defaultRemote = ['\"][^'\"]*['\"];",
            f"const defaultRemote = '{clean_url}';",
            content,
        )
        config_file.write_text(updated, encoding="utf-8")
        print(f"[Catalyst Sync] Injected AppSail API URL: {clean_url}")


def ensure_catalyst_configs(deploy_dir: Path) -> None:
    """Ensures catalyst.json exists in deploy/catalyst/ and removes obsolete app-config.json."""
    deploy_dir.mkdir(parents=True, exist_ok=True)

    catalyst_json_file = deploy_dir / "catalyst.json"
    catalyst_config = {"client": {"source": "client"}}
    catalyst_json_file.write_text(
        json.dumps(catalyst_config, indent=2) + "\n", encoding="utf-8"
    )

    obsolete_app_config = deploy_dir / "app-config.json"
    if obsolete_app_config.exists():
        obsolete_app_config.unlink()
        print(
            "[Catalyst Sync] Removed obsolete app-config.json (AppSail custom OCI is configured via Catalyst Console)"
        )


def validate_catalyst_client(client_dir: Path) -> None:
    """Validates that deploy/catalyst/client contains no unresolved /static/ paths and all assets exist."""
    errors: list[str] = []

    # Check index.html exists
    index_html = client_dir / "index.html"
    if not index_html.exists():
        errors.append(f"Missing index.html at {index_html}")
    else:
        content = index_html.read_text(encoding="utf-8")
        if '<base href="/app/">' not in content:
            errors.append('index.html missing <base href="/app/">')
        if "/static/" in content:
            errors.append("index.html contains unresolved /static/ path references")

    # Check required bundle files exist
    required_files = [
        client_dir / "config.js",
        client_dir / "css" / "index.css",
        client_dir / "js" / "app.js",
        client_dir / "js" / "router.js",
        client_dir / "js" / "apiClient.js",
        client_dir / "images" / "splash_arch.jpg",
        client_dir / "images" / "hero_interior.jpg",
        client_dir / "client-package.json",
    ]
    for req in required_files:
        if not req.exists():
            errors.append(f"Missing required client asset: {req}")

    # Check for any remaining /static/ references across all .html and .js files
    for path in client_dir.glob("**/*"):
        if path.is_file() and path.suffix in (".html", ".js"):
            # Exclude comments in apiClient.js if any, but ensure active code doesn't use /static/
            text = path.read_text(encoding="utf-8")
            for line_no, line in enumerate(text.splitlines(), start=1):
                if (
                    "/static/" in line
                    and not line.strip().startswith("//")
                    and not line.strip().startswith("*")
                ):
                    # Check if it's the explanatory string in apiClient error message
                    if "in /static/config.js before" in line:
                        continue
                    errors.append(
                        f"Unresolved /static/ reference in {path.name}:{line_no}: {line.strip()}"
                    )

    if errors:
        msg = "[Catalyst Validation Failed]:\n" + "\n".join(
            f"  - {err}" for err in errors
        )
        raise RuntimeError(msg)

    print("[Catalyst Validation Passed] All asset paths resolve correctly under /app/.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare, sync, and validate Catalyst deployment layout."
    )
    parser.add_argument(
        "--api-url",
        help="AppSail backend URL (e.g. https://tasteops-appsail-xxxx.catalystserverless.com)",
        default=None,
    )
    args = parser.parse_args()

    repo_root, src_static, client_dir = get_paths()
    deploy_dir = repo_root / "deploy" / "catalyst"

    print(f"[Catalyst Sync] Synchronizing from {src_static} -> {client_dir}...")
    sync_client_assets(src_static, client_dir, args.api_url)
    ensure_catalyst_configs(deploy_dir)
    validate_catalyst_client(client_dir)
    print(
        f"[Catalyst Sync] Synchronization complete. Deploy package ready at {deploy_dir}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
