"""TasteOps Frontend UI Routes.

Serves the AI Operations Workspace SPA shell for all 8 canonical frontend screens.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request, Response
from fastapi.responses import FileResponse, HTMLResponse

ui_router = APIRouter(tags=["UI"], include_in_schema=False)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
INDEX_HTML = STATIC_DIR / "index.html"


@ui_router.get("/", response_class=FileResponse, response_model=None)
@ui_router.get("/dashboard", response_class=FileResponse, response_model=None)
@ui_router.get("/spaces/new", response_class=FileResponse, response_model=None)
@ui_router.get("/spaces/{space_id}", response_class=FileResponse, response_model=None)
@ui_router.get("/sessions/{session_id}", response_class=FileResponse, response_model=None)
@ui_router.get("/sessions/{session_id}/blueprint", response_class=FileResponse, response_model=None)
@ui_router.get("/sessions/{session_id}/activity", response_class=FileResponse, response_model=None)
@ui_router.get("/sessions/{session_id}/approval", response_class=FileResponse, response_model=None)
@ui_router.get("/sessions/{session_id}/execution", response_class=FileResponse, response_model=None)
@ui_router.get("/sessions/{session_id}/ledger", response_class=FileResponse, response_model=None)
async def serve_ui_screens(request: Request) -> Response:
    """Serves the single-page application shell for all workspace routes."""
    if INDEX_HTML.exists():
        return FileResponse(INDEX_HTML, media_type="text/html")
    return HTMLResponse("<h1>TasteOps UI not found</h1>", status_code=404)
