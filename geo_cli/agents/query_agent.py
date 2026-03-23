"""Query Agent — 타겟 고객 관점의 자연어 쿼리 생성"""
from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal

import anthropic

from geo_cli.orchestrator.schema import AnalysisBrief
from geo_cli.ui.console import (
    console,
    print_separator,
    print_status,
    prompt_user,
)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class GeoQuery:
    id: str
    text: str
    language: str
    type: str   # information_search | comparison | recommendations | use_cases | trends | performance | pricing
    persona_id: str
    brand_focus: str = "target"   # "target" | "competitor" | "general"
    category: str = ""            # 제품/도메인 카테고리 (예: "스마트폰", "노트북")


@dataclass
class QueryResult:
    brief_id: str
    queries: list[GeoQuery] = field(default_factory=list)
    total: int = 0

    def to_dict(self) -> dict:
        return {
            "brief_id": self.brief_id,
            "total": self.total,
            "queries": [asdict(q) for q in self.queries],
        }


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are a marketing and GEO (Generative Engine Optimization) research expert tasked with creating questionnaires to evaluate GEO performance.

Your questions must be carefully structured so that they do NOT explicitly mention any brand or product names, but are instead naturally likely to produce answers that mention a specific brand or product when completed by a knowledgeable respondent or LLM. Your goal is to construct questions that elicit brand or product mentions even though the questions themselves remain fully brand-neutral.

## Output Format
Return ONLY a valid JSON array. No prose, no markdown fences, just the raw JSON array.

Each query object must have exactly these fields:
- "id": sequential ID like "q_001", "q_002", etc.
- "text": the actual question (brand-neutral, natural, conversational phrasing)
- "language": language code ("ko", "en", etc.)
- "type": one of — "information_search" | "comparison" | "recommendations" | "use_cases" | "trends" | "performance" | "pricing"
- "category": the product/domain this question targets (e.g., "스마트폰", "노트북", "이어폰")
- "persona_id": the persona ID this query represents (use the IDs provided)
- "brand_focus": "target" | "competitor" | "general"

## Core Design Rules
1. NEVER include the target brand, competitor names, or specific product names in the question text.
2. EVERY question must be designed so that a natural answer will almost certainly mention a specific brand or product.
3. Sound natural — like a real person asking an AI assistant or search engine.
4. Distribute questions evenly across all 7 question types: information_search, comparison, recommendations, use_cases, trends, performance, pricing.
5. Distribute questions evenly across all provided personas.
6. Distribute questions across specified languages according to ratios.
7. Assign a category to each question (product/domain grouping).
8. Align questions with the full purchase journey: awareness → consideration → decision.

## Validation (check every question)
✅ No brand or competitor names in the question text
✅ Neutral phrasing — but answer will naturally reference a brand/product
✅ Fluent and native in the specified language
✅ Labeled with both type and category
✅ Supports GEO goals: visibility, ranking order, sentiment, competitor benchmarking
"""


def _build_prompt(brief: AnalysisBrief) -> str:
    qs = brief.query_settings

    target_company = brief.subject.name
    products_str = ", ".join(qs.products) if qs.products else target_company
    keywords_str = ", ".join(qs.keywords) if qs.keywords else "(키워드 미지정)"
    competitors_str = (
        ", ".join(c.name for c in brief.competitors)
        if brief.competitors else "없음"
    )
    region = brief.subject.primary_market or "글로벌"
    languages = qs.query_languages
    target_count = qs.target_count
    direction = brief.additional_context or ""

    personas_desc = "\n".join(
        f'  - id="{p.id}", name="{p.name}", description="{p.description}"'
        for p in brief.personas
    ) or '  - id="persona_1", name="일반 사용자", description=""'

    lang_note = ""
    if len(languages) > 1:
        per_lang = target_count // len(languages)
        lang_note = f" (~{per_lang}개씩 각 언어별 배분)"

    return f"""## GEO 쿼리 생성 요청

다음 변수를 기반으로 정확히 {target_count}개의 GEO 평가 질문을 생성하세요.

### 변수
- **Target Company (분석 대상 회사):** {target_company}
- **Products (분석 대상 제품):** {products_str}
- **Keywords (포함할 키워드):** {keywords_str}
- **Competitors (경쟁사):** {competitors_str}
- **Region (지역):** {region}
- **Language (언어):** {', '.join(languages)}{lang_note}
- **Total Questions (총 질문 수):** {target_count}
- **Analysis Purpose:** {brief.analysis_purpose.type}

### Target Personas (질문을 이 페르소나 관점에서 설계)
{personas_desc}

### 질문 유형 배분 (7가지를 균등하게)
- information_search: 제품 정보, 기능, 평판 검색
- comparison: 경쟁 제품과의 비교
- recommendations: 상황별 추천 요청
- use_cases: 특정 사용 시나리오에 최적 제품
- trends: 최신 트렌드, 신기술 관련
- performance: 성능 벤치마크, 속도, 정확도
- pricing: 가격 대비 가치, 예산별 추천

{f"### Additional Direction{chr(10)}{direction}{chr(10)}" if direction else ""}
⚠️ 중요: 질문 텍스트에 "{target_company}" 또는 경쟁사 이름({competitors_str})을 절대 포함하지 마세요.
단, 질문에 대한 답변에는 자연스럽게 해당 브랜드/제품이 언급될 수 있도록 설계하세요.

Output ONLY the raw JSON array — no markdown fences, no explanation.
"""


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------

class QueryAgent:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def run(self, brief: AnalysisBrief, interactive: bool = True) -> QueryResult:
        from geo_cli.utils.stream_log import geo_log

        geo_log.step("Query Agent 시작")
        geo_log.info(f"목표 쿼리: {brief.query_settings.target_count}개 | 언어: {', '.join(brief.query_settings.query_languages)}")
        geo_log.info(f"모델: {self._model}")

        if interactive:
            print_separator()
            console.print(
                f"\n[bold cyan]▶ Query Agent[/] — "
                f"{brief.query_settings.target_count}개 쿼리 생성 중 "
                f"({', '.join(brief.query_settings.query_languages)})\n"
            )

        queries = self._generate(brief)

        result = QueryResult(
            brief_id=brief.brief_id,
            queries=queries,
            total=len(queries),
        )

        json_path, csv_path = _save_queries(result, brief.brief_id)
        geo_log.ok(f"{len(queries)}개 쿼리 저장 완료 → {json_path.name}")

        if interactive:
            console.print(f"\n[geo.success]✓[/] {len(queries)}개 쿼리 생성 완료")
            console.print(f"  [geo.hint]JSON: {json_path}[/]")
            console.print(f"  [geo.hint]CSV:  {csv_path}[/]")
            self._review(result)

        return result

    # ------------------------------------------------------------------
    # Claude API call
    # ------------------------------------------------------------------

    def _generate(self, brief: AnalysisBrief) -> list[GeoQuery]:
        from geo_cli.utils.stream_log import geo_log

        geo_log.info("Claude API 호출 중 (쿼리 생성)...")
        geo_log.info(f"프롬프트 길이: {len(_build_prompt(brief))}자 | max_tokens: 8192")

        if True:  # always show in console too
            print_status("Claude가 쿼리를 생성하고 있습니다 (30-60초 소요될 수 있습니다)...")

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=8192,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": _build_prompt(brief)}],
            )
        except anthropic.APIConnectionError as e:
            from geo_cli.utils.stream_log import geo_log as gl
            gl.error(f"API 연결 실패: {e}")
            from geo_cli.ui.console import render_error_panel
            render_error_panel("API 연결 실패", str(e))
            raise
        except anthropic.APIStatusError as e:
            from geo_cli.utils.stream_log import geo_log as gl
            gl.error(f"API 오류: {e}")
            from geo_cli.ui.console import render_error_panel
            render_error_panel("API 오류", str(e))
            raise

        geo_log.info(f"API 응답 수신 — 입력 토큰: {response.usage.input_tokens}, 출력 토큰: {response.usage.output_tokens}")

        raw = response.content[0].text.strip()

        # Strip markdown fences if Claude wraps output
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            from geo_cli.utils.stream_log import geo_log as gl
            gl.error(f"쿼리 JSON 파싱 실패: {e}")
            from geo_cli.ui.console import render_error_panel
            render_error_panel("쿼리 JSON 파싱 실패", str(e))
            raise

        return [
            GeoQuery(
                id=q.get("id", f"q_{i + 1:03d}"),
                text=q["text"],
                language=q.get("language", brief.query_settings.query_languages[0]),
                type=q.get("type", "information_search"),
                persona_id=q.get("persona_id", ""),
                brand_focus=q.get("brand_focus", "target"),
                category=q.get("category", ""),
            )
            for i, q in enumerate(data)
        ]

    # ------------------------------------------------------------------
    # Review UX
    # ------------------------------------------------------------------

    def _review(self, result: QueryResult) -> None:
        from rich.table import Table
        from rich import box as rich_box

        print_separator()
        console.print(f"\n[bold cyan]쿼리 검토[/] — 총 {result.total}개 (처음 15개 표시)\n")

        table = Table(
            box=rich_box.SIMPLE,
            show_header=True,
            header_style="geo.brand",
            padding=(0, 1),
        )
        table.add_column("ID", style="dim", width=7)
        table.add_column("언어", width=5)
        table.add_column("유형", width=18)
        table.add_column("카테고리", width=12)
        table.add_column("페르소나", width=14)
        table.add_column("쿼리")

        _type_color = {
            "information_search": "blue",
            "comparison": "yellow",
            "recommendations": "green",
            "use_cases": "cyan",
            "trends": "magenta",
            "performance": "red",
            "pricing": "bright_yellow",
        }

        for q in result.queries[:15]:
            color = _type_color.get(q.type, "white")
            table.add_row(
                q.id,
                q.language,
                f"[{color}]{q.type}[/]",
                q.category,
                q.persona_id,
                q.text,
            )

        if result.total > 15:
            table.add_row("...", "", "", "", f"[dim]+ {result.total - 15}개 더[/]")

        console.print(table)

        # Stats summary
        by_type: dict[str, int] = {}
        by_lang: dict[str, int] = {}
        for q in result.queries:
            by_type[q.type] = by_type.get(q.type, 0) + 1
            by_lang[q.language] = by_lang.get(q.language, 0) + 1

        stats = " | ".join(
            [f"{t}: {n}" for t, n in by_type.items()]
            + [f"{l}: {n}" for l, n in by_lang.items()]
        )
        console.print(f"  [geo.hint]{stats}[/]")

        console.print(
            "\n[geo.hint]명령어: [geo.input]approve[/] (승인) | "
            "[geo.input]regenerate[/] (재생성) | "
            "[geo.input]quit[/] (종료)[/]\n"
        )

        while True:
            cmd = prompt_user("명령 입력").strip().lower()
            if cmd in ("approve", "승인", "yes", "y"):
                console.print("[geo.success]✓ 쿼리 승인됨. AI 테스트 단계로 이동합니다.[/]")
                return
            elif cmd in ("regenerate", "재생성", "r"):
                console.print("[geo.hint]재생성 기능은 다음 버전에서 지원됩니다. 승인 후 계속 진행하세요.[/]")
            elif cmd in ("quit", "q", "exit", "종료"):
                import sys
                console.print("[geo.hint]종료합니다.[/]")
                sys.exit(0)
            else:
                console.print("[geo.hint]  approve / regenerate / quit 중 하나를 입력해 주세요.[/]")


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def _save_queries(result: QueryResult, brief_id: str, data_dir: Path | None = None) -> tuple[Path, Path]:
    from geo_cli.utils.file_io import _ensure_data_dir, _DEFAULT_DATA_DIR, atomic_write
    target_dir = _ensure_data_dir(data_dir or _DEFAULT_DATA_DIR)

    json_path = target_dir / f"queries_{brief_id}.json"
    atomic_write(json_path, json.dumps(result.to_dict(), ensure_ascii=False, indent=2))

    csv_path = target_dir / f"queries_{brief_id}.csv"
    _write_csv(csv_path, result.queries)

    return json_path, csv_path


def load_queries(brief_id: str, data_dir: Path | None = None) -> QueryResult:
    """brief_id로 저장된 쿼리 파일을 불러온다."""
    from geo_cli.utils.file_io import _DEFAULT_DATA_DIR
    target_dir = data_dir or _DEFAULT_DATA_DIR
    json_path = target_dir / f"queries_{brief_id}.json"
    if not json_path.exists():
        raise FileNotFoundError(f"쿼리 파일 없음: {json_path}")
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    queries = [
        GeoQuery(
            id=q["id"],
            text=q["text"],
            language=q["language"],
            type=q["type"],
            persona_id=q["persona_id"],
            brand_focus=q.get("brand_focus", "target"),
            category=q.get("category", ""),
        )
        for q in data["queries"]
    ]
    return QueryResult(brief_id=data["brief_id"], queries=queries, total=data["total"])



def _write_csv(path: Path, queries: list[GeoQuery]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["id", "text", "language", "type", "category", "persona_id", "brand_focus"],
        )
        writer.writeheader()
        writer.writerows(asdict(q) for q in queries)


# ---------------------------------------------------------------------------
# Module-level entry point (called from main.py)
# ---------------------------------------------------------------------------

def run(brief: AnalysisBrief, interactive: bool = True) -> QueryResult:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    model = os.getenv("GEO_MODEL", "claude-sonnet-4-6")
    agent = QueryAgent(api_key=api_key, model=model)
    return agent.run(brief, interactive=interactive)
