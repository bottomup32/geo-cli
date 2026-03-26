"""
GEO CLI — 통합 서버 (FastAPI + Streamlit)
FastAPI가 /api/* 요청 처리, 나머지는 Streamlit으로 리버스 프록시.
Render 배포 시 이 파일이 메인 엔트리포인트.
"""
from __future__ import annotations

import subprocess
import sys
import time
import os

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import Response
from contextlib import asynccontextmanager

from api_server import app as api_app

STREAMLIT_PORT = 8501
SERVER_PORT = int(os.getenv("PORT", "10000"))

_streamlit_proc = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 시작 시 Streamlit 서브프로세스 실행."""
    global _streamlit_proc
    _streamlit_proc = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", "app.py",
            f"--server.port={STREAMLIT_PORT}",
            "--server.address=127.0.0.1",
            "--server.headless=true",
            "--browser.gatherUsageStats=false",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Streamlit 준비 대기
    for _ in range(30):
        try:
            async with httpx.AsyncClient() as c:
                r = await c.get(f"http://127.0.0.1:{STREAMLIT_PORT}/_stcore/health")
                if r.status_code == 200:
                    break
        except Exception:
            pass
        time.sleep(1)
    yield
    if _streamlit_proc:
        _streamlit_proc.terminate()


# ── 메인 앱 ────────────────────────────────────────────────────
main_app = FastAPI(lifespan=lifespan)

# api_server.py의 라우트는 이미 /api/* 프리픽스를 포함하므로 루트에 마운트
for route in api_app.routes:
    main_app.routes.insert(0, route)


# ── Streamlit 리버스 프록시 ────────────────────────────────────
@main_app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def proxy_to_streamlit(request: Request, path: str = ""):
    """Streamlit으로 모든 비-API 요청 프록시."""
    url = f"http://127.0.0.1:{STREAMLIT_PORT}/{path}"
    headers = dict(request.headers)
    headers.pop("host", None)

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                params=dict(request.query_params),
                content=await request.body(),
            )
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=dict(resp.headers),
            )
        except httpx.ConnectError:
            return Response(
                content=b"Streamlit is starting up...",
                status_code=503,
            )


if __name__ == "__main__":
    uvicorn.run(
        "server:main_app",
        host="0.0.0.0",
        port=SERVER_PORT,
        log_level="info",
    )
