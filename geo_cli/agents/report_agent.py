"""Report Agent — Claude 기반 GEO 컨설팅 보고서 생성"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import anthropic

from geo_cli.orchestrator.schema import AnalysisBrief
from geo_cli.agents.analysis_agent import AnalysisResult, GeoMetrics, load_analysis
from geo_cli.ui.console import console, print_separator, print_status, render_error_panel


# ---------------------------------------------------------------------------
# 보고서 시스템 프롬프트
# ---------------------------------------------------------------------------

_REPORT_SYSTEM = """You are a senior GEO (Generative Engine Optimization) strategy consultant at TecAce Software, delivering analysis reports to C-level executives and marketing leaders.

GEO is SEO for the AI age — optimizing how AI platforms (ChatGPT, Google AI Mode, Perplexity, etc.) describe, recommend, and rank brands. Your reports directly inform marketing budgets, content strategy, and competitive positioning.

## Report Quality Standards
- **Strategic, not descriptive.** Every data point must be followed by "so what?" — the business implication.
- **Specific, not generic.** Name the competitors, cite the key quotes verbatim, reference actual URLs. Never say "improve your content" without specifying which content and how.
- **Data-driven.** Lead with the number, then interpret it. Use tables for comparisons.
- **Actionable.** Every recommendation must include: what to do, why it matters, and expected impact.
- **Write entirely in the language specified** (default: Korean). Professional tone matching the audience level.

## Report Structure (follow exactly, all sections required)

# GEO 분석 보고서: {brand_name}

> 분석 플랫폼: {platform} | 분석 쿼리: {total_queries}개 | 생성일: {date}

## 1. Executive Summary
3-5 bullet points. Lead with the single most important finding. Include the #1 recommended action with expected impact. This section alone should give a busy executive everything they need.

## 2. AI 가시성 분석 (Visibility & Ranking)
- Interpret Visibility rate in competitive context (is 60% good or bad for this industry?)
- Share of Voice comparison table: brand vs. each competitor (with mention counts and SoV%)
- Mention Rank distribution: how often is the brand mentioned first vs. later?
- Interpret what "Rank 1" rate means for conversion intent

## 3. 감성 분석 (Sentiment Analysis)
- Sentiment distribution breakdown (positive/neutral/negative counts and %)
- Average sentiment score interpretation
- Quote the top 3 most positive and top 3 most negative key_quotes verbatim
- Identify recurring themes in negative sentiment — what specific criticisms does AI repeat?
- Compare sentiment against competitors if data is available

## 4. 카테고리별 성과 분석 (Category Performance)
- Which product categories have the highest/lowest brand visibility?
- Which query types (information_search, comparison, recommendations, use_cases, trends, performance, pricing) yield the best/worst results?
- Identify "blind spots": categories where the brand should appear but doesn't

## 5. 경쟁사 비교 (Competitive Landscape)
- Who dominates AI recommendations overall?
- Per-competitor breakdown: mention count, SoV, typical positioning
- Where does the brand consistently lose to each competitor? What narrative does AI construct?
- Identify competitors' strengths that AI latches onto

## 6. 페르소나별 인사이트 (Persona Insights)
- Which persona has the highest/lowest brand awareness through AI?
- Persona × Sentiment matrix: who sees the brand positively vs. negatively?
- Business implication: which customer segment needs the most attention?

## 7. 참조 소스 분석 (Source & Citation Analysis)
- Top 10 most-cited URLs/domains in AI responses
- Which of these cite the brand favorably vs. unfavorably?
- Gaps: which authoritative sources does AI NOT cite for this brand?
- What does the citation pattern reveal about the brand's digital authority?

## 8. GEO 전략 제안 (Strategic Recommendations)
Prioritized into 3 tiers with specific actions:

### P1 — 즉시 실행 (30일 이내, 높은 임팩트)
- 2-3 specific, high-impact actions addressing the biggest gaps found in the analysis

### P2 — 중기 전략 (30-90일, 체계적 개선)
- Content strategy: specific topics, formats, and publication venues
- Website optimization: specific pages/sections to update or create
- PR/media strategy: specific angles for press releases and citation-worthy content

### P3 — 장기 투자 (90일+, 지속적 개선)
- Technical SEO: schema markup, structured data, knowledge graph optimization
- Partnership/citation building: specific targets for backlinks and mentions
- Monitoring cadence: recommended re-analysis schedule

## 9. 다음 단계 (Immediate Next Steps)
5 specific action items for the next 2 weeks, with owners/responsibilities where applicable.

## 부록: 핵심 데이터 테이블
- Include a summary table of all key metrics
- Competitor comparison matrix

---
Write the complete report. Be thorough, specific, and strategic. Do not truncate or summarize sections.
"""


def _build_report_prompt(brief: AnalysisBrief, result: AnalysisResult) -> str:
    from collections import defaultdict

    m = result.metrics
    lang = brief.report_settings.language
    audience = brief.report_settings.audience_level
    qs = brief.query_settings

    # ── 핵심 지표 요약
    total_s = m.sentiment_positive + m.sentiment_negative + m.sentiment_neutral
    avg_score = 0.0
    if result.query_analyses:
        mentioned = [a for a in result.query_analyses if a.brand_mentioned]
        if mentioned:
            avg_score = sum(a.sentiment_score for a in mentioned) / len(mentioned)

    metrics_summary = {
        "brand": result.subject_name,
        "platform": result.platform,
        "total_queries": m.total_queries,
        "visibility": f"{m.visibility * 100:.1f}%",
        "share_of_voice": f"{m.sov * 100:.1f}%",
        "avg_mention_rank": round(m.avg_rank, 2),
        "rank_1_count": m.rank_1_count,
        "rank_1_rate": f"{m.rank_1_count / m.mentioned_count * 100:.1f}%" if m.mentioned_count else "N/A",
        "sentiment": {
            "positive": m.sentiment_positive,
            "negative": m.sentiment_negative,
            "neutral": m.sentiment_neutral,
            "avg_score": round(avg_score, 2),
        },
        "competitors": [
            {"name": c.name, "mention_count": c.mention_count, "sov": f"{c.sov * 100:.1f}%"}
            for c in m.competitor_metrics
        ],
        "persona_breakdown": [
            {
                "persona": p.persona_name,
                "total_queries": p.total_queries,
                "visibility": f"{p.visibility * 100:.1f}%",
                "avg_rank": round(p.avg_rank, 2),
                "sentiment_positive": p.sentiment_positive,
                "sentiment_negative": p.sentiment_negative,
                "sentiment_neutral": p.sentiment_neutral,
            }
            for p in m.persona_metrics
        ],
        "top_urls": [
            {"url": u.url, "domain": u.domain, "cited_count": u.count}
            for u in m.top_urls[:10]
        ],
    }

    # ── 카테고리별 성과 (신규)
    by_category: dict[str, dict] = defaultdict(lambda: {"total": 0, "mentioned": 0, "positive": 0, "negative": 0})
    by_type: dict[str, dict] = defaultdict(lambda: {"total": 0, "mentioned": 0, "positive": 0, "negative": 0})

    for a in result.query_analyses:
        cat = a.category or "기타"
        by_category[cat]["total"] += 1
        if a.brand_mentioned:
            by_category[cat]["mentioned"] += 1
        if a.sentiment == "positive":
            by_category[cat]["positive"] += 1
        elif a.sentiment == "negative":
            by_category[cat]["negative"] += 1

        qtype = a.query_type or "기타"
        by_type[qtype]["total"] += 1
        if a.brand_mentioned:
            by_type[qtype]["mentioned"] += 1
        if a.sentiment == "positive":
            by_type[qtype]["positive"] += 1
        elif a.sentiment == "negative":
            by_type[qtype]["negative"] += 1

    category_performance = {
        cat: {
            "total": d["total"],
            "visibility": f"{d['mentioned'] / d['total'] * 100:.1f}%" if d["total"] else "0%",
            "positive": d["positive"],
            "negative": d["negative"],
        }
        for cat, d in sorted(by_category.items(), key=lambda x: x[1]["mentioned"], reverse=True)
    }

    query_type_performance = {
        qtype: {
            "total": d["total"],
            "visibility": f"{d['mentioned'] / d['total'] * 100:.1f}%" if d["total"] else "0%",
            "positive": d["positive"],
            "negative": d["negative"],
        }
        for qtype, d in sorted(by_type.items(), key=lambda x: x[1]["mentioned"], reverse=True)
    }

    # ── 대표 인용구 (긍정/부정 각 최대 5개, sentiment_score로 정렬)
    sorted_by_score = sorted(
        [a for a in result.query_analyses if a.key_quote],
        key=lambda a: a.sentiment_score,
        reverse=True,
    )
    positive_quotes = [
        {"query": a.query_text, "quote": a.key_quote, "score": a.sentiment_score, "category": a.category}
        for a in sorted_by_score if a.sentiment_score > 0
    ][:5]
    negative_quotes = [
        {"query": a.query_text, "quote": a.key_quote, "score": a.sentiment_score, "category": a.category}
        for a in reversed(sorted_by_score) if a.sentiment_score < 0
    ][:5]

    # ── 제품/키워드 정보
    products_str = ", ".join(qs.products) if qs.products else brief.subject.name
    keywords_str = ", ".join(qs.keywords) if qs.keywords else "N/A"

    return f"""Write a GEO consulting report in **{lang}** (language code) for a **{audience}** audience.

## Input Data

### Analysis Brief
- Subject: {brief.subject.name} ({brief.subject.type})
- Industry: {brief.subject.industry}
- Market: {brief.subject.primary_market}
- Products analyzed: {products_str}
- Keywords: {keywords_str}
- Analysis purpose: {brief.analysis_purpose.type}
{f'- Additional context: {brief.analysis_purpose.custom_notes}' if brief.analysis_purpose.custom_notes else ''}
- Competitors: {', '.join(c.name for c in brief.competitors)}

### Quantitative Metrics
{json.dumps(metrics_summary, ensure_ascii=False, indent=2)}

### Category Performance (brand visibility by product category)
{json.dumps(category_performance, ensure_ascii=False, indent=2)}

### Query Type Performance (brand visibility by question type)
{json.dumps(query_type_performance, ensure_ascii=False, indent=2)}

### Top Positive Quotes from AI Responses (sorted by sentiment_score)
{json.dumps(positive_quotes, ensure_ascii=False, indent=2)}

### Top Negative Quotes from AI Responses (sorted by sentiment_score)
{json.dumps(negative_quotes, ensure_ascii=False, indent=2)}

Now write the complete report following the structure in your system instructions. Be thorough, data-driven, and strategic.
"""


# ---------------------------------------------------------------------------
# Report Agent
# ---------------------------------------------------------------------------

class ReportAgent:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def run(self, brief: AnalysisBrief, analysis_result: AnalysisResult | None = None) -> Path:
        print_separator()
        console.print("\n[bold cyan]▶ Report Agent[/] — 컨설팅 보고서 생성\n")

        if analysis_result is None:
            try:
                analysis_result = load_analysis(brief.brief_id)
            except FileNotFoundError:
                render_error_panel(
                    "분석 결과 파일 없음",
                    f"data/analysis_{brief.brief_id}.json 파일이 필요합니다."
                )
                raise

        print_status(
            f"보고서 언어: {brief.report_settings.language} "
            f"| 독자: {brief.report_settings.audience_level}"
        )
        print_status("Claude가 보고서를 작성 중입니다 (1-2분 소요)...")

        report_md = self._generate(brief, analysis_result)

        report_path = _save_report(report_md, brief.brief_id)

        console.print(f"\n[geo.success]✓[/] 보고서 생성 완료")
        console.print(f"  [geo.hint]파일: {report_path}[/]")

        # 보고서 앞부분 미리보기
        self._preview(report_md)
        print_separator()

        return report_path

    def _generate(self, brief: AnalysisBrief, result: AnalysisResult) -> str:
        prompt = _build_report_prompt(brief, result)
        full_text = ""

        try:
            with self._client.messages.stream(
                model=self._model,
                max_tokens=8192,
                system=_REPORT_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                console.print()
                for text in stream.text_stream:
                    print(text, end="", flush=True)
                    full_text += text
                print()  # 줄바꿈

        except anthropic.APIConnectionError as e:
            render_error_panel("API 연결 실패", str(e))
            sys.exit(1)
        except anthropic.APIStatusError as e:
            render_error_panel("API 오류", str(e))
            sys.exit(1)

        return full_text

    def _preview(self, report_md: str) -> None:
        """보고서 Executive Summary 섹션만 패널로 표시."""
        from rich.panel import Panel
        from rich.markdown import Markdown

        # Executive Summary 섹션 추출
        lines = report_md.splitlines()
        preview_lines: list[str] = []
        in_exec = False
        for line in lines:
            if "Executive Summary" in line or "executive summary" in line.lower():
                in_exec = True
            if in_exec:
                preview_lines.append(line)
                # 다음 ## 헤더가 나오면 종료
                if len(preview_lines) > 1 and line.startswith("## "):
                    preview_lines.pop()
                    break

        if preview_lines:
            preview = "\n".join(preview_lines[:20])
            console.print(
                Panel(
                    Markdown(preview),
                    title="[geo.success]Executive Summary 미리보기[/]",
                    border_style="green",
                    padding=(1, 2),
                )
            )


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def _save_report(content: str, brief_id: str, data_dir: Path | None = None) -> Path:
    from geo_cli.utils.file_io import _ensure_data_dir, _DEFAULT_DATA_DIR, atomic_write
    target_dir = _ensure_data_dir(data_dir or _DEFAULT_DATA_DIR)

    report_path = target_dir / f"report_{brief_id}.md"
    atomic_write(report_path, content)
    return report_path


# ---------------------------------------------------------------------------
# Module-level entry point
# ---------------------------------------------------------------------------

def run(brief: AnalysisBrief, analysis_result: AnalysisResult | None = None) -> Path:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    model = os.getenv("GEO_MODEL", "claude-sonnet-4-6")
    agent = ReportAgent(api_key=api_key, model=model)
    return agent.run(brief, analysis_result)
