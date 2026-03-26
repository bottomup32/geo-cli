"""
GEO CLI — FastAPI REST API 서버
로컬 Worker와 Cloud 간 자동 연동을 위한 API 엔드포인트 제공.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import JSONResponse

# ── 환경 설정 ─────────────────────────────────────────────────
DATA_DIR = Path(os.getenv("GEO_DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

WORKER_API_KEY = os.getenv("GEO_WORKER_API_KEY", "")

app = FastAPI(
    title="GEO CLI API",
    version="0.1.0",
    docs_url="/api/docs",
)


# ── 인증 헬퍼 ─────────────────────────────────────────────────
def _verify_key(x_api_key: str | None) -> None:
    """API Key 검증. 키가 미설정이면 인증 생략."""
    if WORKER_API_KEY and x_api_key != WORKER_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")


# ── 헬퍼: 파이프라인 상태 ─────────────────────────────────────
def _pipeline_status(bid: str) -> dict[str, bool]:
    """각 파이프라인 단계의 완료 여부를 반환."""
    return {
        "brief": (DATA_DIR / f"brief_{bid}.json").exists(),
        "queries": (DATA_DIR / f"queries_{bid}.json").exists(),
        "testing": (DATA_DIR / f"raw_chatgpt_{bid}.json").exists(),
        "analysis": (DATA_DIR / f"analysis_{bid}.json").exists(),
        "report": (DATA_DIR / f"report_{bid}.md").exists(),
    }


# ══════════════════════════════════════════════════════════════
# 엔드포인트
# ══════════════════════════════════════════════════════════════

@app.get("/api/health")
async def health():
    """헬스 체크."""
    return {"status": "ok"}


@app.get("/api/pending-jobs")
def pending_jobs(x_api_key: str | None = Header(None)):
    """쿼리는 생성되었지만 테스트 결과가 없는 작업 목록 반환."""
    import logging
    logger = logging.getLogger("api_server")
    logger.setLevel(logging.INFO)
    
    _verify_key(x_api_key)

    try:
        jobs = []
        for qf in sorted(DATA_DIR.glob("queries_geo_*.json"), reverse=True):
            bid = qf.stem.replace("queries_", "")
            status = _pipeline_status(bid)
            if status["queries"] and not status["testing"]:
                # brief 정보 로드 (제목 등)
                title = bid
                brief_path = DATA_DIR / f"brief_{bid}.json"
                if brief_path.exists():
                    try:
                        with open(brief_path, "r", encoding="utf-8") as f:
                            bd = json.load(f)
                        title = bd.get("title") or bd.get("subject", {}).get("name", bid)
                    except Exception as parse_e:
                        logger.warning(f"Failed to parse {brief_path}: {parse_e}")
                
                jobs.append({
                    "brief_id": bid,
                    "title": title,
                    "status": status,
                })

        return {"pending": jobs, "count": len(jobs)}
    except Exception as e:
        logger.error(f"Error in pending-jobs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/download/{brief_id}")
def download_queries(brief_id: str, x_api_key: str | None = Header(None)):
    """로컬 워커가 특정 brief_id의 쿼리 파일과 brief 파일을 다운로드."""
    _verify_key(x_api_key)

    q_file = DATA_DIR / f"queries_{brief_id}.json"
    b_file = DATA_DIR / f"brief_{brief_id}.json"

    if not q_file.exists():
        raise HTTPException(status_code=404, detail=f"queries not found: {brief_id}")
    
    # brief 정보는 없을 수도 있지만 있으면 포함
    try:
        with open(q_file, "r", encoding="utf-8") as f:
            queries = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read queries: {e}")

    brief = None
    if b_file.exists():
        try:
            with open(b_file, "r", encoding="utf-8") as f:
                brief = json.load(f)
        except Exception:
            pass

    return {
        "brief_id": brief_id,
        "queries": queries,
        "brief": brief
    }


@app.post("/api/upload-results/{brief_id}")
def upload_results(brief_id: str, request: Request, x_api_key: str | None = Header(None)):
    """로컬 워커가 수행한 검색/스크래핑 결과를 업로드."""
    _verify_key(x_api_key)
    
    import asyncio
    try:
        # Use asyncio.run to sync await request.json()
        payload = asyncio.run(request.json())
        results = payload.get("results")
        if not results:
            raise HTTPException(status_code=400, detail="No results provided")

        out_file = DATA_DIR / f"test_results_{brief_id}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
            
        return {"status": "success", "message": f"Results saved for {brief_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/trigger-analysis/{brief_id}")
def trigger_analysis(brief_id: str, x_api_key: str | None = Header(None)):
    """테스트 결과 업로드 후 분석 + 보고서 생성을 트리거."""
    _verify_key(x_api_key)

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    model = os.getenv("GEO_MODEL", "claude-sonnet-4-6")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    # 필요 파일 확인
    status = _pipeline_status(brief_id)
    if not status["testing"]:
        raise HTTPException(status_code=400, detail="testing results not found")

    try:
        from geo_cli.utils.file_io import load_brief
        from geo_cli.agents.query_agent import load_queries
        from geo_cli.agents.testing_agent import load_testing_result
        from geo_cli.agents.analysis_agent import AnalysisAgent
        from geo_cli.agents.report_agent import ReportAgent

        brief = load_brief(brief_id)
        query_result = load_queries(brief_id)
        testing_result = load_testing_result(brief_id)

        # Analysis
        analysis_agent = AnalysisAgent(api_key=api_key, model=model)
        analysis_result = analysis_agent.run(brief, testing_result, query_result)

        # Report
        report_agent = ReportAgent(api_key=api_key, model=model)
        report_path = report_agent.run(brief, analysis_result)

        return {
            "status": "ok",
            "analysis": f"analysis_{brief_id}.json",
            "report": str(Path(report_path).name) if report_path else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/download-results/{brief_id}")
async def download_results(brief_id: str, x_api_key: str | None = Header(None)):
    """분석 + 보고서 결과를 다운로드 (로컬 영구 저장용)."""
    _verify_key(x_api_key)

    result: dict = {"brief_id": brief_id, "status": _pipeline_status(brief_id)}

    # Analysis JSON
    ap = DATA_DIR / f"analysis_{brief_id}.json"
    if ap.exists():
        with open(ap, "r", encoding="utf-8") as f:
            result["analysis"] = json.load(f)

    # Analysis CSV
    ac = DATA_DIR / f"analysis_{brief_id}.csv"
    if ac.exists():
        result["analysis_csv"] = ac.read_text(encoding="utf-8-sig")

    # Report Markdown
    rp = DATA_DIR / f"report_{brief_id}.md"
    if rp.exists():
        result["report"] = rp.read_text(encoding="utf-8")

    if "analysis" not in result and "report" not in result:
        raise HTTPException(status_code=404, detail="분석/보고서 결과 없음")

    return result
