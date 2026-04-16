"""GEO CLI Backend — FastAPI Application."""
from __future__ import annotations

import mimetypes
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from backend.database.engine import init_db
from backend.database.engine import SessionLocal
from backend.database.models import PipelineStageModel
from backend.routers import briefs, interview, pipeline, prompts, settings


# Windows can resolve JavaScript as text/plain in some environments, which
# prevents browsers from executing Vite's module bundle.
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".mjs")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        stale_running = db.query(PipelineStageModel).filter_by(status="running").all()
        for stage in stale_running:
            stage.status = "error"
            stage.error_message = "서버 재시작으로 실행이 중단되었습니다. 다시 실행해 주세요."
        db.commit()
    finally:
        db.close()
    yield


app = FastAPI(
    title="GEO CLI API",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — allow React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers (including WebSocket endpoints)
app.include_router(interview.router, prefix="/api/interview", tags=["interview"])
app.include_router(pipeline.router, prefix="/api/pipeline", tags=["pipeline"])
app.include_router(briefs.router, prefix="/api/briefs", tags=["briefs"])
app.include_router(prompts.router, prefix="/api/prompts", tags=["prompts"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])

# Serve React SPA in production (only mount static files for non-API, non-WS paths)
_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _frontend_dist.exists() and not os.getenv("GEO_DEV_MODE"):
    _no_cache_headers = {"Cache-Control": "no-store, max-age=0"}

    def _safe_file_response(file_path: Path, base_dir: Path) -> FileResponse | Response:
        resolved_file = file_path.resolve()
        resolved_base = base_dir.resolve()
        if not resolved_file.is_relative_to(resolved_base):
            return Response(status_code=403)
        if not resolved_file.exists() or not resolved_file.is_file():
            return Response(status_code=404)

        media_type = mimetypes.guess_type(str(resolved_file))[0]
        return FileResponse(
            resolved_file,
            media_type=media_type,
            headers=_no_cache_headers,
        )

    # Serve static assets explicitly so browsers do not reuse stale MIME metadata.
    _assets_dir = _frontend_dist / "assets"
    if _assets_dir.exists():
        @app.get("/assets/{asset_path:path}", include_in_schema=False)
        async def serve_asset(asset_path: str):
            return _safe_file_response(_assets_dir / asset_path, _assets_dir)

    # Catch-all for SPA routing — only for non-API HTTP requests
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Don't intercept API or WebSocket paths
        if full_path.startswith("api/") or full_path.startswith("ws/"):
            return Response(status_code=404)
        # Try to serve the exact file first (favicon.svg, etc.)
        file_path = _frontend_dist / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return _safe_file_response(file_path, _frontend_dist)
        # Otherwise serve index.html for SPA routing
        return FileResponse(
            _frontend_dist / "index.html",
            media_type="text/html",
            headers=_no_cache_headers,
        )
