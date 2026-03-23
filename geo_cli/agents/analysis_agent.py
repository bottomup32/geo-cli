"""Analysis Agent — GEO 정량 지표 계산"""
from __future__ import annotations

import csv
import json
import math
import os
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path

import anthropic

from geo_cli.orchestrator.schema import AnalysisBrief
from geo_cli.agents.query_agent import GeoQuery, QueryResult, load_queries
from geo_cli.agents.testing_agent import RawResponse, TestingResult, load_testing_result
from geo_cli.ui.console import console, print_separator, print_status, render_error_panel

_BATCH_SIZE = 20  # Claude에 한 번에 보낼 응답 수


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class QueryAnalysis:
    # ── 식별자
    query_id: str
    query_text: str
    answer_text: str = ""           # AI 플랫폼 원문 응답
    # ── 분류
    category: str = ""              # brand_focus: "target" | "competitor" | "general"
    tags: str = ""                  # 언어 + 쿼리유형 (예: "ko, informational")
    query_type: str = ""            # "informational" | "exploratory" | "comparative"
    # ── 페르소나
    persona_id: str = ""
    persona_name: str = ""          # 페르소나 이름 (해석 후)
    # ── 브랜드 언급
    target_brand: str = ""          # 분석 대상 브랜드명
    brand_mentioned: bool = False
    mention_rank: int = 0           # 0 = 미언급, 1 = 첫 번째, 2 = 두 번째...
    total_brand_mentions: int = 0   # 타겟 + 경쟁사 합산 언급 수
    # ── 감성
    sentiment: str = "not_mentioned"   # "positive" | "negative" | "neutral" | "not_mentioned"
    sentiment_score: float = 0.0       # -1.0 (부정) ~ 1.0 (긍정), 0.0 = 미언급/중립
    # ── 기타
    competitors_mentioned: list[str] = field(default_factory=list)
    key_quote: str = ""
    response_urls: list[str] = field(default_factory=list)


@dataclass
class PersonaMetrics:
    persona_id: str
    persona_name: str
    total_queries: int = 0
    mentioned_count: int = 0
    visibility: float = 0.0
    avg_rank: float = 0.0
    sentiment_positive: int = 0
    sentiment_negative: int = 0
    sentiment_neutral: int = 0


@dataclass
class CompetitorMetric:
    name: str
    mention_count: int = 0
    sov: float = 0.0           # share of voice (전체 브랜드 언급 중 비중)


@dataclass
class UrlMetric:
    url: str
    domain: str
    count: int = 1


@dataclass
class GeoMetrics:
    total_queries: int = 0
    mentioned_count: int = 0
    visibility: float = 0.0           # 언급률 (0.0~1.0)
    avg_rank: float = 0.0             # 언급된 쿼리들의 평균 순위
    rank_1_count: int = 0             # 1순위 언급 횟수
    sov: float = 0.0                  # share of voice
    sentiment_positive: int = 0
    sentiment_negative: int = 0
    sentiment_neutral: int = 0
    competitor_metrics: list[CompetitorMetric] = field(default_factory=list)
    persona_metrics: list[PersonaMetrics] = field(default_factory=list)
    top_urls: list[UrlMetric] = field(default_factory=list)


@dataclass
class AnalysisResult:
    brief_id: str
    subject_name: str
    platform: str
    query_analyses: list[QueryAnalysis] = field(default_factory=list)
    metrics: GeoMetrics = field(default_factory=GeoMetrics)

    def to_dict(self) -> dict:
        return {
            "brief_id": self.brief_id,
            "subject_name": self.subject_name,
            "platform": self.platform,
            "query_analyses": [asdict(q) for q in self.query_analyses],
            "metrics": asdict(self.metrics),
        }


# ---------------------------------------------------------------------------
# Claude 분석 프롬프트
# ---------------------------------------------------------------------------

_ANALYSIS_SYSTEM = """You are a senior GEO (Generative Engine Optimization) analyst specializing in brand visibility measurement within AI-generated responses.

Your task: analyze each AI response and extract precise, structured metrics about how the target brand is represented.

## Output Format
Return ONLY a valid JSON array. No prose, no markdown fences, no explanation.
Each element corresponds to one input item, in the same order:

```
{
  "query_id": "...",
  "brand_mentioned": true | false,
  "mention_rank": 0,
  "sentiment": "positive" | "negative" | "neutral" | "not_mentioned",
  "sentiment_score": 0.0,
  "competitors_mentioned": ["CompA", "CompB"],
  "key_quote": "..."
}
```

## Metric Definitions

### brand_mentioned
- true: the target brand or any of its specific products appear by name in the response
- false: not mentioned at all (paraphrases, hints, or implicit references do NOT count)

### mention_rank
- 0 = not mentioned
- 1 = the FIRST brand/product name to appear in the response
- 2 = second brand mentioned, etc.
- Count every distinct brand/product/company name that appears BEFORE the target brand, regardless of whether it is a competitor.

### sentiment
Assess the AI's overall portrayal of the target brand in this specific response:
- **positive**: recommended, praised, highlighted as a top choice, described with favorable language ("best", "leading", "excellent", "innovative")
- **negative**: criticized, warned against, described unfavorably ("outdated", "overpriced", "problems", "falls behind"), or listed as inferior to competitors
- **neutral**: mentioned factually without clear positive or negative framing (pure specs, history, or feature listing without evaluation)
- **not_mentioned**: brand does not appear → must set mention_rank=0 and sentiment_score=0.0

### sentiment_score
Fine-grained floating point score reflecting HOW positive or negative:
- **0.8 ~ 1.0**: enthusiastically recommended, described as the best/first choice
- **0.4 ~ 0.7**: positively mentioned, praised but alongside alternatives
- **0.1 ~ 0.3**: mildly positive, mentioned favorably but briefly
- **0.0**: neutral (factual only) or not mentioned
- **-0.1 ~ -0.3**: mildly negative, minor criticism or caveats
- **-0.4 ~ -0.7**: clearly negative, unfavorable comparison or significant criticism
- **-0.8 ~ -1.0**: strongly negative, explicitly warned against or described as the worst option

### competitors_mentioned
- List ONLY brand/company names from the provided competitor list that appear in the response.
- Do NOT include generic terms or brands not in the competitor list.

### key_quote
- Extract the single most relevant sentence or phrase about the target brand, verbatim from the response.
- If multiple relevant passages exist, pick the one that best captures the sentiment.
- Maximum 200 characters. Empty string if brand not mentioned.
"""


def _build_batch_prompt(
    items: list[dict],
    brand_name: str,
    competitors: list[str],
) -> str:
    competitors_str = ", ".join(competitors) if competitors else "none"
    items_json = json.dumps(items, ensure_ascii=False, indent=2)
    return (
        f"Target brand: \"{brand_name}\"\n"
        f"Competitors to watch: {competitors_str}\n\n"
        f"Analyze these {len(items)} AI responses:\n{items_json}\n\n"
        "Return the JSON array."
    )


# ---------------------------------------------------------------------------
# Analysis Agent
# ---------------------------------------------------------------------------

class AnalysisAgent:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def run(
        self,
        brief: AnalysisBrief,
        testing_result: TestingResult | None = None,
        query_result: QueryResult | None = None,
    ) -> AnalysisResult:
        from geo_cli.utils.stream_log import geo_log
        geo_log.step("Analysis Agent 시작")

        print_separator()
        console.print("\n[bold cyan]▶ Analysis Agent[/] — GEO 지표 계산\n")

        # 데이터 로드
        if testing_result is None:
            testing_result = load_testing_result(brief.brief_id)
        if query_result is None:
            query_result = load_queries(brief.brief_id)

        # query_id → GeoQuery 매핑 (type, language, brand_focus 포함)
        query_map: dict[str, "GeoQuery"] = {q.id: q for q in query_result.queries}
        # persona_id → persona_name 매핑
        persona_name_map: dict[str, str] = {p.id: p.name for p in brief.personas}

        successful = [r for r in testing_result.responses if r.status == "success"]
        print_status(f"분석 대상: {len(successful)}개 응답 (전체 {testing_result.total}개 중 성공)")

        # 경쟁사 목록
        competitor_names = [c.name for c in brief.competitors]
        brand_name = brief.subject.name

        # Claude 배치 분석
        query_analyses = self._analyze_batched(
            successful, query_map, persona_name_map, brand_name, competitor_names
        )

        # 지표 집계
        metrics = self._aggregate(query_analyses, brief)

        result = AnalysisResult(
            brief_id=brief.brief_id,
            subject_name=brand_name,
            platform=testing_result.platform,
            query_analyses=query_analyses,
            metrics=metrics,
        )

        # 저장
        json_path, csv_path = _save_analysis(result, brief.brief_id)
        console.print(f"\n[geo.success]✓[/] 분석 완료")
        console.print(f"  [geo.hint]JSON: {json_path}[/]")
        console.print(f"  [geo.hint]CSV:  {csv_path}[/]")

        # 핵심 지표 출력
        self._print_summary(metrics, brand_name)
        print_separator()

        return result

    # ------------------------------------------------------------------
    # Claude 배치 분석
    # ------------------------------------------------------------------

    def _analyze_batched(
        self,
        responses: list[RawResponse],
        query_map: dict[str, "GeoQuery"],
        persona_name_map: dict[str, str],
        brand_name: str,
        competitor_names: list[str],
    ) -> list[QueryAnalysis]:
        all_analyses: list[QueryAnalysis] = []
        total_batches = math.ceil(len(responses) / _BATCH_SIZE)

        for batch_idx in range(total_batches):
            batch = responses[batch_idx * _BATCH_SIZE:(batch_idx + 1) * _BATCH_SIZE]
            from geo_cli.utils.stream_log import geo_log
            geo_log.info(f"배치 분석 {batch_idx + 1}/{total_batches} ({len(batch)}개 응답) → Claude API 호출 중...")
            print_status(
                f"배치 분석 중 {batch_idx + 1}/{total_batches} "
                f"({len(batch)}개 응답)..."
            )

            items = [
                {
                    "query_id": r.query_id,
                    "query": r.query_text,
                    "response": r.response_text[:3000],  # 토큰 절약
                }
                for r in batch
            ]

            prompt = _build_batch_prompt(items, brand_name, competitor_names)

            try:
                api_response = self._client.messages.create(
                    model=self._model,
                    max_tokens=4096,
                    system=_ANALYSIS_SYSTEM,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = api_response.content[0].text.strip()
                if raw.startswith("```"):
                    lines = raw.splitlines()
                    raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
                parsed = json.loads(raw)
            except (anthropic.APIError, json.JSONDecodeError) as e:
                from geo_cli.utils.stream_log import geo_log as gl
                gl.error(f"배치 {batch_idx + 1} 분석 실패: {e}")
                console.print(f"  [geo.error]배치 {batch_idx + 1} 분석 실패: {e}[/]")
                # fallback: 해당 배치는 미언급으로 처리
                parsed = [
                    {
                        "query_id": r.query_id,
                        "brand_mentioned": False,
                        "mention_rank": 0,
                        "sentiment": "not_mentioned",
                        "sentiment_score": 0.0,
                        "competitors_mentioned": [],
                        "key_quote": "",
                    }
                    for r in batch
                ]

            for r, p in zip(batch, parsed):
                gq = query_map.get(r.query_id)
                pid = gq.persona_id if gq else ""
                q_type = gq.type if gq else ""
                q_lang = gq.language if gq else ""
                brand_focus = gq.brand_focus if gq else "target"

                brand_mentioned = bool(p.get("brand_mentioned", False))
                competitors_mentioned = p.get("competitors_mentioned", [])
                # 총 언급 수: 타겟(0 or 1) + 경쟁사 언급 수
                total_mentions = (1 if brand_mentioned else 0) + len(competitors_mentioned)

                all_analyses.append(QueryAnalysis(
                    query_id=r.query_id,
                    query_text=r.query_text,
                    answer_text=r.response_text,
                    category=brand_focus,
                    tags=", ".join(filter(None, [q_lang, q_type, gq.category if gq else ""])),
                    query_type=q_type,
                    persona_id=pid,
                    persona_name=persona_name_map.get(pid, pid),
                    target_brand=brand_name,
                    brand_mentioned=brand_mentioned,
                    mention_rank=int(p.get("mention_rank", 0)),
                    total_brand_mentions=total_mentions,
                    sentiment=p.get("sentiment", "not_mentioned"),
                    sentiment_score=float(p.get("sentiment_score", 0.0)),
                    competitors_mentioned=competitors_mentioned,
                    key_quote=p.get("key_quote", ""),
                    response_urls=r.response_urls,
                ))

        return all_analyses

    # ------------------------------------------------------------------
    # 지표 집계
    # ------------------------------------------------------------------

    def _aggregate(self, analyses: list[QueryAnalysis], brief: AnalysisBrief) -> GeoMetrics:
        m = GeoMetrics()
        m.total_queries = len(analyses)
        if m.total_queries == 0:
            return m

        mentioned = [a for a in analyses if a.brand_mentioned]
        m.mentioned_count = len(mentioned)
        m.visibility = m.mentioned_count / m.total_queries

        # 평균 순위 & 1순위 횟수
        if mentioned:
            ranks = [a.mention_rank for a in mentioned if a.mention_rank > 0]
            m.avg_rank = sum(ranks) / len(ranks) if ranks else 0.0
            m.rank_1_count = sum(1 for a in mentioned if a.mention_rank == 1)

        # 감성
        m.sentiment_positive = sum(1 for a in mentioned if a.sentiment == "positive")
        m.sentiment_negative = sum(1 for a in mentioned if a.sentiment == "negative")
        m.sentiment_neutral = sum(1 for a in mentioned if a.sentiment == "neutral")

        # SoV
        competitor_counts: dict[str, int] = defaultdict(int)
        for a in analyses:
            for c in a.competitors_mentioned:
                competitor_counts[c] += 1

        total_brand_mentions = m.mentioned_count
        total_competitor_mentions = sum(competitor_counts.values())
        total_all_mentions = total_brand_mentions + total_competitor_mentions
        m.sov = total_brand_mentions / total_all_mentions if total_all_mentions > 0 else 0.0

        # 경쟁사별 지표
        for comp in brief.competitors:
            cnt = competitor_counts.get(comp.name, 0)
            sov = cnt / total_all_mentions if total_all_mentions > 0 else 0.0
            m.competitor_metrics.append(CompetitorMetric(
                name=comp.name,
                mention_count=cnt,
                sov=sov,
            ))

        # 페르소나별 지표
        by_persona: dict[str, list[QueryAnalysis]] = defaultdict(list)
        for a in analyses:
            by_persona[a.persona_id].append(a)

        for pid, pa_list in by_persona.items():
            # persona_name은 QueryAnalysis에 이미 해석되어 저장됨
            resolved_name = pa_list[0].persona_name if pa_list else pid
            pm = PersonaMetrics(
                persona_id=pid,
                persona_name=resolved_name,
                total_queries=len(pa_list),
            )
            pa_mentioned = [a for a in pa_list if a.brand_mentioned]
            pm.mentioned_count = len(pa_mentioned)
            pm.visibility = pm.mentioned_count / pm.total_queries if pm.total_queries else 0.0
            r_vals = [a.mention_rank for a in pa_mentioned if a.mention_rank > 0]
            pm.avg_rank = sum(r_vals) / len(r_vals) if r_vals else 0.0
            pm.sentiment_positive = sum(1 for a in pa_mentioned if a.sentiment == "positive")
            pm.sentiment_negative = sum(1 for a in pa_mentioned if a.sentiment == "negative")
            pm.sentiment_neutral = sum(1 for a in pa_mentioned if a.sentiment == "neutral")
            m.persona_metrics.append(pm)

        # URL 집계 (상위 20개)
        url_counts: dict[str, int] = defaultdict(int)
        for a in analyses:
            for url in a.response_urls:
                url_counts[url] += 1

        def _domain(url: str) -> str:
            try:
                from urllib.parse import urlparse
                return urlparse(url).netloc
            except Exception:
                return url

        top_urls = sorted(url_counts.items(), key=lambda x: x[1], reverse=True)[:20]
        m.top_urls = [UrlMetric(url=u, domain=_domain(u), count=c) for u, c in top_urls]

        return m

    # ------------------------------------------------------------------
    # 요약 출력
    # ------------------------------------------------------------------

    def _print_summary(self, m: GeoMetrics, brand_name: str) -> None:
        from rich.table import Table
        from rich import box as rich_box

        console.print(f"\n[bold cyan]── 핵심 GEO 지표: {brand_name}[/]\n")

        table = Table(box=rich_box.SIMPLE, show_header=False, padding=(0, 2))
        table.add_column("지표", style="geo.brand", width=20)
        table.add_column("값", style="white")

        vis_pct = f"{m.visibility * 100:.1f}%"
        sov_pct = f"{m.sov * 100:.1f}%"
        avg_rank_str = f"{m.avg_rank:.1f}" if m.avg_rank > 0 else "N/A"
        total_s = m.sentiment_positive + m.sentiment_negative + m.sentiment_neutral
        pos_pct = f"{m.sentiment_positive / total_s * 100:.0f}%" if total_s else "N/A"
        neg_pct = f"{m.sentiment_negative / total_s * 100:.0f}%" if total_s else "N/A"

        table.add_row("Visibility", f"{vis_pct}  ({m.mentioned_count}/{m.total_queries}개 쿼리)")
        table.add_row("Share of Voice", sov_pct)
        table.add_row("Avg. Mention Rank", avg_rank_str)
        table.add_row("Rank 1 (첫 언급)", f"{m.rank_1_count}회")
        table.add_row("Sentiment (+/-)", f"긍정 {pos_pct} / 부정 {neg_pct}")

        if m.competitor_metrics:
            comp_str = "  ".join(
                f"{c.name}: {c.mention_count}회" for c in m.competitor_metrics
            )
            table.add_row("경쟁사 언급", comp_str)

        console.print(table)

        # 페르소나별 visibility
        if m.persona_metrics:
            console.print("  [geo.hint]페르소나별 Visibility:[/]")
            for pm in m.persona_metrics:
                bar = "█" * int(pm.visibility * 20)
                console.print(
                    f"    [dim]{pm.persona_name[:18]:18}[/] "
                    f"[cyan]{bar:<20}[/] {pm.visibility * 100:.0f}%"
                )


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def _save_analysis(result: AnalysisResult, brief_id: str, data_dir: Path | None = None) -> tuple[Path, Path]:
    from geo_cli.utils.file_io import _ensure_data_dir, _DEFAULT_DATA_DIR, atomic_write
    target_dir = _ensure_data_dir(data_dir or _DEFAULT_DATA_DIR)

    json_path = target_dir / f"analysis_{brief_id}.json"
    atomic_write(json_path, json.dumps(result.to_dict(), ensure_ascii=False, indent=2))

    csv_path = target_dir / f"analysis_{brief_id}.csv"
    _write_csv(csv_path, result.query_analyses, result.subject_name)

    return json_path, csv_path


def load_analysis(brief_id: str, data_dir: Path | None = None) -> AnalysisResult:
    from geo_cli.utils.file_io import _DEFAULT_DATA_DIR
    target_dir = data_dir or _DEFAULT_DATA_DIR
    json_path = target_dir / f"analysis_{brief_id}.json"
    if not json_path.exists():
        raise FileNotFoundError(f"분석 결과 파일 없음: {json_path}")
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    qa_list = [
        QueryAnalysis(
            query_id=q["query_id"],
            query_text=q["query_text"],
            answer_text=q.get("answer_text", ""),
            category=q.get("category", ""),
            tags=q.get("tags", ""),
            query_type=q.get("query_type", ""),
            persona_id=q.get("persona_id", ""),
            persona_name=q.get("persona_name", ""),
            target_brand=q.get("target_brand", ""),
            brand_mentioned=q["brand_mentioned"],
            mention_rank=q["mention_rank"],
            total_brand_mentions=q.get("total_brand_mentions", 0),
            sentiment=q["sentiment"],
            sentiment_score=q.get("sentiment_score", 0.0),
            competitors_mentioned=q.get("competitors_mentioned", []),
            key_quote=q.get("key_quote", ""),
            response_urls=q.get("response_urls", []),
        )
        for q in data["query_analyses"]
    ]

    md = data["metrics"]
    metrics = GeoMetrics(
        total_queries=md["total_queries"],
        mentioned_count=md["mentioned_count"],
        visibility=md["visibility"],
        avg_rank=md["avg_rank"],
        rank_1_count=md["rank_1_count"],
        sov=md["sov"],
        sentiment_positive=md["sentiment_positive"],
        sentiment_negative=md["sentiment_negative"],
        sentiment_neutral=md["sentiment_neutral"],
        competitor_metrics=[
            CompetitorMetric(**c) for c in md.get("competitor_metrics", [])
        ],
        persona_metrics=[
            PersonaMetrics(**p) for p in md.get("persona_metrics", [])
        ],
        top_urls=[
            UrlMetric(**u) for u in md.get("top_urls", [])
        ],
    )

    return AnalysisResult(
        brief_id=data["brief_id"],
        subject_name=data["subject_name"],
        platform=data["platform"],
        query_analyses=qa_list,
        metrics=metrics,
    )


_CSV_FIELDS = [
    "Query ID",
    "Query Text",
    "Answer Text",
    "Cate",
    "Tags",
    "Persona",
    "Target Brand",
    "Target Brand Mentions (Count)",
    "Brand Mentions (Position)",
    "Total Mentions (All Brands)",
    "Sentiment (Category)",
    "Sentiment (Score)",
    "Competitor (Brand)",
    "Reference",
    "Type",
    "Key Quote",
    "Persona ID",
]


def _write_csv(path: Path, analyses: list[QueryAnalysis], brand_name: str) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for a in analyses:
            writer.writerow({
                "Query ID": a.query_id,
                "Query Text": a.query_text,
                "Answer Text": a.answer_text,
                "Cate": a.category,
                "Tags": a.tags,
                "Persona": a.persona_name,
                "Target Brand": a.target_brand,
                "Target Brand Mentions (Count)": 1 if a.brand_mentioned else 0,
                "Brand Mentions (Position)": a.mention_rank,
                "Total Mentions (All Brands)": a.total_brand_mentions,
                "Sentiment (Category)": a.sentiment,
                "Sentiment (Score)": a.sentiment_score,
                "Competitor (Brand)": "; ".join(a.competitors_mentioned),
                "Reference": "; ".join(a.response_urls),
                "Type": a.query_type,
                "Key Quote": a.key_quote,
                "Persona ID": a.persona_id,
            })


# ---------------------------------------------------------------------------
# Module-level entry point
# ---------------------------------------------------------------------------

def run(brief: AnalysisBrief, testing_result: TestingResult | None = None, query_result: QueryResult | None = None) -> AnalysisResult:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    model = os.getenv("GEO_MODEL", "claude-sonnet-4-6")
    agent = AnalysisAgent(api_key=api_key, model=model)
    return agent.run(brief, testing_result, query_result)
