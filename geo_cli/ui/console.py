"""
Rich 기반 터미널 UI 렌더링 헬퍼
모든 rich import는 이 모듈에서만 사용한다.
"""
from __future__ import annotations

import io
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme
from rich import box

# ---------------------------------------------------------------------------
# Global console instance
# ---------------------------------------------------------------------------

_theme = Theme({
    "geo.brand": "bold cyan",
    "geo.label": "bold white",
    "geo.value": "white",
    "geo.hint": "dim white",
    "geo.success": "bold green",
    "geo.error": "bold red",
    "geo.warn": "bold yellow",
    "geo.input": "bold cyan",
})


def _build_console() -> Console:
    """Streamlit 환경에서는 devnull로, CLI에서는 UTF-8 안전 출력."""
    import os

    # Streamlit 환경 감지: streamlit 모듈이 로드되어 있고 TTY가 아닌 경우
    # io.StringIO를 사용해 OS 파일 핸들 없이 출력을 버린다 (닫힘 오류 방지)
    if "streamlit" in sys.modules and not getattr(sys.stdout, "isatty", lambda: False)():
        return Console(theme=_theme, file=io.StringIO(), highlight=False)

    # CLI 환경: Windows cp949 등 비-UTF-8 터미널 안전 처리
    try:
        encoding = getattr(sys.stdout, "encoding", None) or "ascii"
        if encoding.lower().replace("-", "") not in ("utf8", "utf16", "utf32"):
            if hasattr(sys.stdout, "buffer"):
                safe = io.TextIOWrapper(
                    sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
                )
                return Console(theme=_theme, file=safe, highlight=False)
    except Exception:
        pass
    return Console(theme=_theme)


console = _build_console()


# ---------------------------------------------------------------------------
# Panels
# ---------------------------------------------------------------------------

def render_welcome_panel() -> None:
    content = Text.assemble(
        ("GEO CLI", "geo.brand"),
        " — ",
        ("Generative Engine Optimization\n", "bold white"),
        "\n",
        ("AI 시대의 SEO 분석 도구\n", "white"),
        ("브랜드·제품·서비스가 ChatGPT, Google AI 에서 어떻게 묘사되는지\n", "geo.hint"),
        ("정량적으로 분석하고 최적화 전략을 수립합니다.\n", "geo.hint"),
        "\n",
        ("시작하려면 Enter 를 누르세요. 종료: Ctrl+C", "geo.hint"),
    )
    console.print(Panel(content, title="[geo.brand]TecAce GEO CLI[/]", border_style="cyan", padding=(1, 2)))


def render_success_panel(file_path: str) -> None:
    content = Text.assemble(
        ("✓  분석 브리프가 저장되었습니다.\n\n", "geo.success"),
        ("파일: ", "geo.label"),
        (file_path, "geo.value"),
        "\n\n",
        ("다음 단계: Query Agent 가 50~100개 쿼리를 생성합니다.", "geo.hint"),
    )
    console.print(Panel(content, title="[geo.success]저장 완료[/]", border_style="green", padding=(1, 2)))


def render_error_panel(message: str, detail: str = "") -> None:
    content = Text.assemble(
        ("✗  ", "geo.error"),
        (message + "\n", "bold white"),
    )
    if detail:
        content.append(f"\n{detail}", style="geo.hint")
    console.print(Panel(content, title="[geo.error]오류[/]", border_style="red", padding=(1, 2)))


def render_interrupt_panel(draft_path: str) -> None:
    content = Text.assemble(
        ("인터뷰가 중단되었습니다.\n\n", "geo.warn"),
        ("임시 저장: ", "geo.label"),
        (draft_path, "geo.value"),
        "\n\n",
        ("다음에 같은 파일을 불러와 이어서 진행할 수 있습니다.", "geo.hint"),
    )
    console.print(Panel(content, title="[geo.warn]중단됨[/]", border_style="yellow", padding=(1, 2)))


# ---------------------------------------------------------------------------
# Confirmation table
# ---------------------------------------------------------------------------

def render_confirmation_table(brief_dict: dict) -> None:
    table = Table(
        title="[geo.label]분석 브리프 확인[/]",
        box=box.ROUNDED,
        border_style="cyan",
        show_lines=True,
        padding=(0, 1),
    )
    table.add_column("항목", style="geo.label", width=22, no_wrap=True)
    table.add_column("내용", style="geo.value")

    # Subject
    s = brief_dict.get("subject", {})
    table.add_row("[geo.brand]분석 대상[/]", f"{s.get('name', '')} ({s.get('type', '')})")
    if s.get("description"):
        table.add_row("  설명", s["description"])
    if s.get("industry"):
        table.add_row("  산업", s["industry"])
    if s.get("primary_market"):
        table.add_row("  주요 시장", s["primary_market"])
    if s.get("website"):
        table.add_row("  웹사이트", s["website"])

    # Purpose
    p = brief_dict.get("analysis_purpose", {})
    purpose_labels = {
        "brand_awareness": "브랜드 인지도 분석",
        "competitive_analysis": "경쟁사 비교 분석",
        "content_strategy": "콘텐츠 전략 수립",
        "crisis_monitoring": "위기 모니터링",
    }
    table.add_row(
        "[geo.brand]분석 목적[/]",
        purpose_labels.get(p.get("type", ""), p.get("type", "")),
    )
    if p.get("custom_notes"):
        table.add_row("  세부 사항", p["custom_notes"])

    # Personas
    personas = brief_dict.get("personas", [])
    if personas:
        table.add_row("[geo.brand]타겟 페르소나[/]", f"{len(personas)}개")
        for i, persona in enumerate(personas, 1):
            src = "사용자 정의" if persona.get("source") == "user_defined" else "AI 유추"
            table.add_row(f"  {i}. {persona.get('name', '')}", f"[geo.hint][{src}][/] {persona.get('description', '')}")

    # Competitors
    competitors = brief_dict.get("competitors", [])
    if competitors:
        names = ", ".join(c.get("name", "") for c in competitors)
        table.add_row("[geo.brand]경쟁사[/]", names)

    # Platforms
    platforms = brief_dict.get("target_platforms", [])
    enabled = [p for p in platforms if p.get("enabled")]
    if enabled:
        platform_names = ", ".join(p.get("name", "") for p in enabled)
        table.add_row("[geo.brand]분석 AI 플랫폼[/]", platform_names)

    # Report settings
    rs = brief_dict.get("report_settings", {})
    lang_map = {"ko": "한국어", "en": "영어", "ja": "일본어", "zh": "중국어"}
    audience_map = {"executive": "경영진", "technical": "기술팀", "marketing": "마케팅"}
    table.add_row(
        "[geo.brand]보고서 설정[/]",
        f"언어: {lang_map.get(rs.get('language', 'ko'), rs.get('language', 'ko'))}"
        f" | 독자: {audience_map.get(rs.get('audience_level', 'executive'), rs.get('audience_level', ''))}",
    )

    # Query settings
    qs = brief_dict.get("query_settings", {})
    table.add_row(
        "[geo.brand]쿼리 설정[/]",
        f"목표 수량: {qs.get('target_count', 75)}개"
        f" | 언어: {', '.join(qs.get('query_languages', []))}",
    )
    if qs.get("products"):
        table.add_row("  분석 제품", ", ".join(qs["products"]))
    if qs.get("keywords"):
        table.add_row("  키워드", ", ".join(qs["keywords"]))

    # Additional context
    if ctx := brief_dict.get("additional_context", ""):
        table.add_row("[geo.brand]추가 컨텍스트[/]", ctx)

    console.print(table)


# ---------------------------------------------------------------------------
# Input prompt
# ---------------------------------------------------------------------------

def prompt_user(prompt_text: str = "") -> str:
    console.print(f"\n[geo.input]You ›[/] ", end="")
    return input()


def print_agent_label() -> None:
    console.print("\n[geo.brand]GEO ›[/] ", end="")


def print_separator() -> None:
    console.rule(style="dim cyan")


def print_status(message: str) -> None:
    console.print(f"[geo.hint]  {message}[/]")
