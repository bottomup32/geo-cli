"""
JSON 파일 저장/로드 유틸리티

모든 에이전트가 공유하는 파일 I/O 함수.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from geo_cli.orchestrator.schema import AnalysisBrief

_DEFAULT_DATA_DIR = Path(os.getenv("GEO_DATA_DIR", "./data"))


def _ensure_data_dir(data_dir: Path) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def atomic_write(path: Path, content: str) -> None:
    """Atomic write: temp 파일에 쓴 뒤 os.replace()로 교체 (crash-safe)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        os.unlink(tmp)
        raise


def save_brief(brief: AnalysisBrief, data_dir: Path | None = None) -> Path:
    """AnalysisBrief를 JSON 파일로 저장 (atomic write)."""
    target_dir = _ensure_data_dir(data_dir or _DEFAULT_DATA_DIR)
    file_path = target_dir / f"brief_{brief.brief_id}.json"

    brief.metadata.output_file = str(file_path)
    json_str = brief.to_json()
    atomic_write(file_path, json_str)
    return file_path


def load_brief(brief_id: str, data_dir: Path | None = None) -> AnalysisBrief:
    """brief_id로 저장된 JSON 파일을 불러온다."""
    target_dir = data_dir or _DEFAULT_DATA_DIR
    file_path = target_dir / f"brief_{brief_id}.json"
    if not file_path.exists():
        raise FileNotFoundError(f"Brief not found: {file_path}")
    with open(file_path, encoding="utf-8") as f:
        return AnalysisBrief.from_json(f.read())


def list_briefs(data_dir: Path | None = None) -> list[Path]:
    target_dir = data_dir or _DEFAULT_DATA_DIR
    if not target_dir.exists():
        return []
    return sorted(target_dir.glob("brief_geo_*.json"), reverse=True)


# ---------------------------------------------------------------------------
# 분석별 데이터 관리 헬퍼
# ---------------------------------------------------------------------------

def brief_display_title(brief: AnalysisBrief) -> str:
    """사람이 읽을 수 있는 분석 제목 반환. title 필드가 있으면 사용, 없으면 자동 생성."""
    if brief.title:
        return brief.title
    name = brief.subject.name or "Untitled"
    date_str = brief.created_at[:10] if brief.created_at else ""
    return f"{name} 분석 — {date_str}" if date_str else f"{name} 분석"


from dataclasses import dataclass as _dataclass


@_dataclass
class AnalysisArtifact:
    """brief_id에 속한 개별 산출물 파일."""
    label: str       # 예: "브리프 (JSON)"
    path: Path
    stage: str       # "brief" | "queries" | "testing" | "analysis" | "report"


_ARTIFACT_PATTERNS: list[tuple[str, str, str]] = [
    ("brief",    "brief_{bid}.json",                      "브리프 (JSON)"),
    ("queries",  "queries_{bid}.json",                    "쿼리 (JSON)"),
    ("queries",  "queries_{bid}.csv",                     "쿼리 (CSV)"),
    ("testing",  "raw_chatgpt_{bid}.json",                "ChatGPT 원본 (JSON)"),
    ("testing",  "raw_chatgpt_{bid}.csv",                 "ChatGPT 원본 (CSV)"),
    ("testing",  "raw_chatgpt_{bid}.partial.json",        "ChatGPT 중간저장"),
    ("analysis", "analysis_{bid}.json",                   "분석 결과 (JSON)"),
    ("analysis", "analysis_{bid}.csv",                    "분석 결과 (CSV)"),
    ("report",   "report_{bid}.md",                       "보고서 (Markdown)"),
]


def list_artifacts(brief_id: str, data_dir: Path | None = None) -> list[AnalysisArtifact]:
    """brief_id에 속한 모든 산출물 파일 목록 반환."""
    target_dir = data_dir or _DEFAULT_DATA_DIR
    artifacts = []
    for stage, pattern, label in _ARTIFACT_PATTERNS:
        filename = pattern.replace("{bid}", brief_id)
        p = target_dir / filename
        if p.exists():
            artifacts.append(AnalysisArtifact(label=label, path=p, stage=stage))
    return artifacts


_STAGE_ORDER = ["brief", "queries", "testing", "analysis", "report"]
_STAGE_KO = {
    "brief": "브리프", "queries": "쿼리",
    "testing": "테스트", "analysis": "분석", "report": "보고서",
}


def pipeline_status(brief_id: str, data_dir: Path | None = None) -> dict[str, bool]:
    """각 파이프라인 단계 완료 여부 반환 (순서 보장)."""
    target_dir = data_dir or _DEFAULT_DATA_DIR
    checks = {
        "brief":    (target_dir / f"brief_{brief_id}.json").exists(),
        "queries":  (target_dir / f"queries_{brief_id}.json").exists(),
        "testing":  (target_dir / f"raw_chatgpt_{brief_id}.json").exists(),
        "analysis": (target_dir / f"analysis_{brief_id}.json").exists(),
        "report":   (target_dir / f"report_{brief_id}.md").exists(),
    }
    return checks
