"""
AnalysisBrief — Orchestrator와 하위 에이전트 간의 데이터 계약
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Literal
import uuid


# ---------------------------------------------------------------------------
# Sub-structures
# ---------------------------------------------------------------------------

@dataclass
class Subject:
    name: str = ""
    type: Literal["brand", "product", "service", "topic"] = "brand"
    description: str = ""
    industry: str = ""
    primary_market: str = ""
    website: str = ""


@dataclass
class AnalysisPurpose:
    type: Literal[
        "brand_awareness", "competitive_analysis", "content_strategy", "crisis_monitoring"
    ] = "brand_awareness"
    custom_notes: str = ""


@dataclass
class Persona:
    id: str = ""
    name: str = ""
    source: Literal["user_defined", "ai_inferred"] = "user_defined"
    description: str = ""
    typical_queries: list[str] = field(default_factory=list)


@dataclass
class Competitor:
    name: str
    website: str = ""
    notes: str = ""


@dataclass
class TargetPlatform:
    id: str = ""
    name: str = ""
    url: str = ""
    enabled: bool = True
    access_method: Literal["playwright_scraping", "official_api"] = "playwright_scraping"


@dataclass
class ReportSettings:
    language: str = "ko"
    audience_level: Literal["executive", "technical", "marketing"] = "executive"


@dataclass
class QuerySettings:
    target_count: int = 75
    query_languages: list[str] = field(default_factory=lambda: ["ko", "en"])
    query_types: list[str] = field(
        default_factory=lambda: [
            "information_search", "comparison", "recommendations",
            "use_cases", "trends", "performance", "pricing",
        ]
    )
    products: list[str] = field(default_factory=list)   # 분석 대상 제품명 목록
    keywords: list[str] = field(default_factory=list)   # 쿼리에 반영할 키워드 목록


@dataclass
class BriefMetadata:
    created_by: str = "orchestrator_agent"
    model_used: str = "claude-sonnet-4-6"
    interview_turns: int = 0
    output_file: str = ""


# ---------------------------------------------------------------------------
# Root dataclass
# ---------------------------------------------------------------------------

@dataclass
class AnalysisBrief:
    schema_version: str = "1.0"
    brief_id: str = ""
    created_at: str = ""
    status: Literal["draft", "approved"] = "draft"
    title: str = ""  # 사용자 식별용 분석 제목 (예: "삼성전자 Galaxy 분석")

    subject: Subject = field(default_factory=Subject)
    analysis_purpose: AnalysisPurpose = field(default_factory=AnalysisPurpose)
    personas: list[Persona] = field(default_factory=list)
    competitors: list[Competitor] = field(default_factory=list)
    target_platforms: list[TargetPlatform] = field(default_factory=list)
    report_settings: ReportSettings = field(default_factory=ReportSettings)
    query_settings: QuerySettings = field(default_factory=QuerySettings)
    additional_context: str = ""
    metadata: BriefMetadata = field(default_factory=BriefMetadata)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def new(cls) -> "AnalysisBrief":
        brief_id = _generate_brief_id()
        return cls(
            brief_id=brief_id,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, data: dict) -> "AnalysisBrief":
        brief = cls(
            schema_version=data.get("schema_version", "1.0"),
            brief_id=data.get("brief_id", ""),
            created_at=data.get("created_at", ""),
            status=data.get("status", "draft"),
            title=data.get("title", ""),
            additional_context=data.get("additional_context", ""),
        )

        if s := data.get("subject"):
            brief.subject = Subject(**{k: v for k, v in s.items() if k in Subject.__dataclass_fields__})

        if p := data.get("analysis_purpose"):
            brief.analysis_purpose = AnalysisPurpose(**{k: v for k, v in p.items() if k in AnalysisPurpose.__dataclass_fields__})

        if personas := data.get("personas"):
            brief.personas = [
                Persona(**{k: v for k, v in p.items() if k in Persona.__dataclass_fields__})
                for p in personas
            ]

        if competitors := data.get("competitors"):
            brief.competitors = [
                Competitor(**{k: v for k, v in c.items() if k in Competitor.__dataclass_fields__})
                for c in competitors
            ]

        if platforms := data.get("target_platforms"):
            brief.target_platforms = [
                TargetPlatform(**{k: v for k, v in p.items() if k in TargetPlatform.__dataclass_fields__})
                for p in platforms
            ]

        if rs := data.get("report_settings"):
            brief.report_settings = ReportSettings(**{k: v for k, v in rs.items() if k in ReportSettings.__dataclass_fields__})

        if qs := data.get("query_settings"):
            brief.query_settings = QuerySettings(**{k: v for k, v in qs.items() if k in QuerySettings.__dataclass_fields__})

        if md := data.get("metadata"):
            brief.metadata = BriefMetadata(**{k: v for k, v in md.items() if k in BriefMetadata.__dataclass_fields__})

        return brief

    @classmethod
    def from_json(cls, json_str: str) -> "AnalysisBrief":
        return cls.from_dict(json.loads(json_str))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_brief_id() -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:5]
    return f"geo_{ts}_{suffix}"
