"""
GEO CLI 메인 진입점

실행:
    python -m geo_cli
    또는 설치 후: geo
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# .env 파일 로드 (프로젝트 루트 기준)
load_dotenv(Path(__file__).parent.parent / ".env")


def main() -> None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        from geo_cli.ui.console import render_error_panel
        render_error_panel(
            "ANTHROPIC_API_KEY가 설정되지 않았습니다.",
            ".env 파일에 ANTHROPIC_API_KEY=your_key_here 를 추가하세요.",
        )
        sys.exit(1)

    model = os.getenv("GEO_MODEL", "claude-sonnet-4-6")

    from geo_cli.orchestrator.agent import OrchestratorAgent
    from geo_cli.agents import query_agent, testing_agent, analysis_agent, report_agent

    # 1. Orchestrator — 인터뷰 실행 & 브리프 생성
    orchestrator = OrchestratorAgent(api_key=api_key, model=model)
    brief = orchestrator.run()

    # 2. Query Agent — 쿼리 생성
    query_result = query_agent.run(brief)

    # 3. AI Testing Agent — AI 플랫폼 질의
    testing_result = testing_agent.run(brief, query_result)

    # 4. Analysis Agent — 정량 분석
    analysis_result = analysis_agent.run(brief, testing_result, query_result)

    # 5. Report Agent — 보고서 생성
    report_agent.run(brief, analysis_result)


if __name__ == "__main__":
    main()
