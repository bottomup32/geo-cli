"""GEO CLI Backend — FastAPI Application."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from backend.database.engine import init_db
from backend.routers import briefs, interview, pipeline, prompts, settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
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
    # Mount static assets (js, css, images) under /assets
    _assets_dir = _frontend_dist / "assets"
    if _assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")

    # Catch-all for SPA routing — only for non-API HTTP requests
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Don't intercept API or WebSocket paths
        if full_path.startswith("api/") or full_path.startswith("ws/"):
            return Response(status_code=404)
        # Try to serve the exact file first (favicon.svg, etc.)
        file_path = _frontend_dist / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        # Otherwise serve index.html for SPA routing
        return FileResponse(_frontend_dist / "index.html")
