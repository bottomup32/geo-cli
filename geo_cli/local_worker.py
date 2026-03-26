"""
GEO CLI — 로컬 Worker (폴링 데몬)
클라우드 API를 주기적으로 폴링하여 대기 중인 작업을 감지하고,
Testing Agent(Playwright)를 실행한 뒤 결과를 클라우드에 업로드한다.
클라우드에서 분석/보고서가 완료되면 로컬에 영구 저장한다.

실행:
    python -m geo_cli.local_worker --server https://geo-cli.onrender.com
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


# ── 설정 ──────────────────────────────────────────────────────
DEFAULT_SERVER = "https://geo-cli.onrender.com"
POLL_INTERVAL = 30  # 초
DATA_DIR = Path(os.getenv("GEO_DATA_DIR", str(Path(__file__).parent.parent / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _headers(api_key: str) -> dict:
    """API 인증 헤더."""
    h: dict[str, str] = {}
    if api_key:
        h["X-API-Key"] = api_key
    return h


def _log(msg: str, level: str = "INFO") -> None:
    """간단한 콘솔 로거."""
    icons = {"INFO": "ℹ", "OK": "✅", "WARN": "⚠", "ERR": "❌", "STEP": "▶"}
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {icons.get(level, '·')} {msg}")


# ── API 호출 ──────────────────────────────────────────────────
def poll_once(server: str, api_key: str) -> list[dict]:
    """대기 중인 작업 목록 조회."""
    import httpx
    try:
        r = httpx.get(f"{server}/api/pending-jobs", headers=_headers(api_key), timeout=15)
        r.raise_for_status()
        return r.json().get("pending", [])
    except Exception as e:
        _log(f"폴링 실패: {e}", "WARN")
        return []


def download_job(server: str, api_key: str, bid: str) -> dict | None:
    """brief + queries 다운로드."""
    import httpx
    try:
        r = httpx.get(f"{server}/api/download/{bid}", headers=_headers(api_key), timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        _log(f"다운로드 실패 ({bid}): {e}", "ERR")
        return None


def upload_results(server: str, api_key: str, bid: str, result: dict) -> bool:
    """테스트 결과를 클라우드에 업로드."""
    import httpx
    try:
        r = httpx.post(f"{server}/api/upload-results/{bid}", json=result, headers=_headers(api_key), timeout=60)
        r.raise_for_status()
        _log(f"결과 업로드 완료 ({bid})", "OK")
        return True
    except Exception as e:
        _log(f"업로드 실패 ({bid}): {e}", "ERR")
        return False


def trigger_analysis(server: str, api_key: str, bid: str) -> bool:
    """클라우드에서 분석 + 보고서 생성 트리거."""
    import httpx
    try:
        _log("클라우드에서 분석 + 보고서 생성 중... (최대 5분 소요)", "STEP")
        r = httpx.post(f"{server}/api/trigger-analysis/{bid}", headers=_headers(api_key), timeout=300)
        r.raise_for_status()
        data = r.json()
        _log(f"분석 완료: {data.get('analysis')} | 보고서: {data.get('report')}", "OK")
        return True
    except Exception as e:
        _log(f"분석 트리거 실패 ({bid}): {e}", "WARN")
        return False


def download_results(server: str, api_key: str, bid: str) -> bool:
    """클라우드에서 분석/보고서 결과를 다운로드하여 로컬에 영구 저장."""
    import httpx
    try:
        r = httpx.get(f"{server}/api/download-results/{bid}", headers=_headers(api_key), timeout=30)
        r.raise_for_status()
        data = r.json()

        saved = []
        if "analysis" in data:
            p = DATA_DIR / f"analysis_{bid}.json"
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data["analysis"], f, ensure_ascii=False, indent=2)
            saved.append(p.name)

        if "analysis_csv" in data:
            p = DATA_DIR / f"analysis_{bid}.csv"
            with open(p, "w", encoding="utf-8-sig") as f:
                f.write(data["analysis_csv"])
            saved.append(p.name)

        if "report" in data:
            p = DATA_DIR / f"report_{bid}.md"
            with open(p, "w", encoding="utf-8") as f:
                f.write(data["report"])
            saved.append(p.name)

        _log(f"로컬 저장 완료: {', '.join(saved)}", "OK")
        return True
    except Exception as e:
        _log(f"결과 다운로드 실패 ({bid}): {e}", "WARN")
        return False


# ── 로컬 데이터 저장 ──────────────────────────────────────────
def save_downloaded(data: dict, bid: str) -> None:
    """다운로드된 brief + queries를 로컬에 저장."""
    if "brief" in data:
        p = DATA_DIR / f"brief_{bid}.json"
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data["brief"], f, ensure_ascii=False, indent=2)
        _log(f"Brief 저장: {p.name}")

    if "queries" in data:
        p = DATA_DIR / f"queries_{bid}.json"
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data["queries"], f, ensure_ascii=False, indent=2)
        _log(f"Queries 저장: {p.name}")


# ── Testing Agent 실행 ────────────────────────────────────────
def run_testing(bid: str) -> dict | None:
    """Testing Agent 실행 후 결과 dict 반환."""
    from geo_cli.orchestrator.schema import AnalysisBrief
    from geo_cli.utils.file_io import load_brief
    from geo_cli.agents.query_agent import load_queries
    from geo_cli.agents.testing_agent import TestingAgent

    try:
        brief = load_brief(bid)
    except FileNotFoundError:
        brief = AnalysisBrief.new()
        brief.brief_id = bid
        brief.title = "Worker 자동 실행"

    query_result = load_queries(bid)
    _log(f"Testing Agent 시작 — {query_result.total}개 쿼리", "STEP")

    agent = TestingAgent()
    result = agent.run(brief, query_result)
    return result.to_dict()


# ── 작업 처리 ─────────────────────────────────────────────────
def process_job(server: str, api_key: str, job: dict) -> None:
    """단일 작업: 다운로드 → 테스트 → 업로드 → 분석 → 결과 저장."""
    bid = job["brief_id"]
    title = job.get("title", bid)
    _log(f"작업 시작: {title} ({bid})", "STEP")

    # 1. 쿼리 + 브리프 다운로드 → 로컬 저장
    data = download_job(server, api_key, bid)
    if not data:
        return
    save_downloaded(data, bid)

    # 2. Testing Agent (Playwright) — 로컬에서만 실행
    try:
        result = run_testing(bid)
    except Exception as e:
        _log(f"Testing Agent 실패: {e}", "ERR")
        return
    if not result:
        return

    # 3. 결과 업로드 → 클라우드
    upload_results(server, api_key, bid, result)

    # 4. 분석 + 보고서 생성 트리거 → 클라우드에서 실행
    if trigger_analysis(server, api_key, bid):
        # 5. 완료된 분석/보고서 다운로드 → 로컬 영구 저장
        download_results(server, api_key, bid)

    _log(f"작업 완료: {title} ({bid})", "OK")
    _log(f"로컬 저장 위치: {DATA_DIR}", "INFO")


# ── 메인 루프 ─────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="GEO CLI Local Worker")
    parser.add_argument("--server", default=DEFAULT_SERVER, help="Cloud server URL")
    parser.add_argument("--api-key", default="", help="Worker API Key")
    parser.add_argument("--interval", type=int, default=POLL_INTERVAL, help="Polling interval (sec)")
    parser.add_argument("--once", action="store_true", help="Poll once and exit")
    args = parser.parse_args()

    api_key = args.api_key or os.getenv("GEO_WORKER_API_KEY", "")
    server = args.server.rstrip("/")

    print("=" * 50)
    print("  🎯 GEO CLI Local Worker")
    print(f"  Server : {server}")
    print(f"  Data   : {DATA_DIR}")
    print(f"  Poll   : {args.interval}s")
    print(f"  API Key: {'설정됨' if api_key else '미설정 (인증 없음)'}")
    print("=" * 50)

    if args.once:
        _log("단일 폴링 모드...")
        jobs = poll_once(server, api_key)
        if jobs:
            _log(f"{len(jobs)}개 대기 작업 발견")
            for job in jobs:
                process_job(server, api_key, job)
        else:
            _log("대기 중인 작업 없음")
        return

    _log("폴링 데몬 시작 (Ctrl+C로 종료)...")
    try:
        while True:
            jobs = poll_once(server, api_key)
            if jobs:
                _log(f"{len(jobs)}개 대기 작업 발견!")
                for job in jobs:
                    process_job(server, api_key, job)
            else:
                _log("대기 중인 작업 없음")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        _log("Worker 종료", "OK")


if __name__ == "__main__":
    main()
