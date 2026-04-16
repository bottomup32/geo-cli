"""Prompts API router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.config import PROMPTS_DIR
from backend.schemas.api_models import PromptContent, PromptUpdateRequest

router = APIRouter()

PROMPT_LABELS = {
    "orchestrator": "Orchestrator — 인터뷰 에이전트",
    "query_agent": "Query Agent — 쿼리 생성",
    "analysis": "Analysis Agent — GEO 분석",
    "report": "Report Agent — 보고서 생성",
}


def _load_default_prompts() -> dict[str, str]:
    from geo_cli.orchestrator.prompts import SYSTEM_PROMPT as orch
    from geo_cli.agents.query_agent import _SYSTEM_PROMPT as query
    from geo_cli.agents.analysis_agent import _ANALYSIS_SYSTEM as analysis
    from geo_cli.agents.report_agent import _REPORT_SYSTEM as report
    return {"orchestrator": orch, "query_agent": query, "analysis": analysis, "report": report}


def _ensure_prompt_files():
    PROMPTS_DIR.mkdir(exist_ok=True)
    if not any(PROMPTS_DIR.glob("*.txt")):
        for name, content in _load_default_prompts().items():
            (PROMPTS_DIR / f"{name}.txt").write_text(content, encoding="utf-8")


def _get_prompt(name: str) -> str:
    _ensure_prompt_files()
    path = PROMPTS_DIR / f"{name}.txt"
    return path.read_text(encoding="utf-8") if path.exists() else _load_default_prompts().get(name, "")


@router.get("")
def list_prompts():
    _ensure_prompt_files()
    return [
        {"name": name, "label": label}
        for name, label in PROMPT_LABELS.items()
    ]


@router.get("/{name}", response_model=PromptContent)
def get_prompt(name: str):
    if name not in PROMPT_LABELS:
        raise HTTPException(404, f"Unknown prompt: {name}")
    content = _get_prompt(name)
    return PromptContent(name=name, content=content, char_count=len(content))


@router.put("/{name}")
def update_prompt(name: str, req: PromptUpdateRequest):
    if name not in PROMPT_LABELS:
        raise HTTPException(404, f"Unknown prompt: {name}")
    PROMPTS_DIR.mkdir(exist_ok=True)
    (PROMPTS_DIR / f"{name}.txt").write_text(req.content, encoding="utf-8")
    return {"status": "ok", "char_count": len(req.content)}


@router.post("/{name}/reset")
def reset_prompt(name: str):
    if name not in PROMPT_LABELS:
        raise HTTPException(404, f"Unknown prompt: {name}")
    defaults = _load_default_prompts()
    content = defaults.get(name, "")
    (PROMPTS_DIR / f"{name}.txt").write_text(content, encoding="utf-8")
    return {"status": "ok", "char_count": len(content)}
