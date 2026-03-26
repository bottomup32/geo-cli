"""
GEO CLI - 웹 연동 로컬 평가 전용 실행기
웹 앱 (Render) 에서 생성된 queries_{id}.json 파일을 받아서
스크래핑 평가, 분석, 보고서 생성 파이프라인만 로컬에서 수행합니다.
"""
from __future__ import annotations

import argparse
import os
import sys
import json
import shutil
from pathlib import Path

from dotenv import load_dotenv

# .env 파일 로드
load_dotenv(Path(__file__).parent.parent / ".env")

def main() -> None:
    parser = argparse.ArgumentParser(description="Run GEO CLI testing locally with a downloaded queries JSON file")
    parser.add_argument("queries_file", type=str, help="Path to the downloaded queries_geo_xxx.json file")
    
    args = parser.parse_args()
    queries_path = Path(args.queries_file).resolve()
    
    if not queries_path.exists():
        from geo_cli.ui.console import render_error_panel
        render_error_panel("파일을 찾을 수 없습니다", f"{queries_path} 경로에 파일이 존재하지 않습니다.")
        sys.exit(1)
        
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        from geo_cli.ui.console import render_error_panel
        render_error_panel(
            "ANTHROPIC_API_KEY가 설정되지 않았습니다.",
            ".env 파일에 ANTHROPIC_API_KEY=your_key_here 를 추가하세요.",
        )
        sys.exit(1)

    with open(queries_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    brief_id = data.get("brief_id")
    if not brief_id:
        from geo_cli.ui.console import render_error_panel
        render_error_panel("형식 오류", "올바른 queries JSON 파일이 아닙니다. (brief_id 누락)")
        sys.exit(1)
        
    from geo_cli.orchestrator.schema import AnalysisBrief
    from geo_cli.utils.file_io import load_brief, save_brief, _DEFAULT_DATA_DIR
    
    # 1. 파일 복사: 실행한 파일이 `data/` 내부가 아니라면 `data/` 로 복사합니다.
    target_queries = _DEFAULT_DATA_DIR / queries_path.name
    if queries_path != target_queries:
        _DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(queries_path, target_queries)
        from geo_cli.ui.console import console
        console.print(f"[geo.hint] 쿼리 파일을 {target_queries.name} 로 복사했습니다.[/]")

    # 2. Brief 로드/생성: 웹앱에서 전체 Brief 파일이 없을 경우 더미 객체 사용
    try:
        brief = load_brief(brief_id)
    except FileNotFoundError:
        from geo_cli.ui.console import console
        console.print(f"[geo.hint] 로컬에 brief 데이터가 없어 웹 생성용 브리프를 임시로 사용합니다.[/]")
        brief = AnalysisBrief.new()
        brief.brief_id = brief_id
        brief.title = "웹에서 다운로드된 쿼리 평가"
        save_brief(brief)
        
    from geo_cli.agents import query_agent, testing_agent, analysis_agent, report_agent
    
    # 다운받은 JSON으로부터 QueryResult 객체 변환
    query_result = query_agent.load_queries(brief_id)
    
    # 3. AI Testing Agent — ChatGPT 스크래핑
    testing_result = testing_agent.run(brief, query_result)

    # 4. Analysis Agent — 지표 분석
    analysis_result = analysis_agent.run(brief, testing_result, query_result)

    # 5. Report Agent — 최종 마크다운 보고서
    report_agent.run(brief, analysis_result)

if __name__ == "__main__":
    main()
