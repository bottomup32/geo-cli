"""Pipeline execution service — runs agents in background threads."""
from __future__ import annotations

import json
import threading
import traceback
from datetime import datetime, timezone

from backend.config import ANTHROPIC_API_KEY, DATA_DIR, GEO_MODEL
from backend.database.engine import SessionLocal
from backend.database.models import (
    AnalysisModel,
    BriefModel,
    MetricsModel,
    PipelineStageModel,
    QueryModel,
    RawResponseModel,
)
from geo_cli.utils.stream_log import geo_log


class PipelineService:
    """Manages pipeline stage execution in background threads."""

    def __init__(self):
        self._running: dict[str, str] = {}  # brief_id -> stage
        self._results: dict[str, dict] = {}  # brief_id -> {stage: result}

    def is_running(self, brief_id: str) -> bool:
        return brief_id in self._running

    def current_stage(self, brief_id: str) -> str | None:
        return self._running.get(brief_id)

    def get_result(self, brief_id: str, stage: str):
        return self._results.get(brief_id, {}).get(stage)

    def run_stage(self, brief_id: str, stage: str, brief_dict: dict, **kwargs) -> dict:
        """Start a pipeline stage in a background thread. Returns immediately."""
        if self.is_running(brief_id):
            return {"error": f"이미 실행 중: {self._running[brief_id]}"}

        self._running[brief_id] = stage
        geo_log.clear()

        thread = threading.Thread(
            target=self._execute_stage,
            args=(brief_id, stage, brief_dict),
            kwargs=kwargs,
            daemon=True,
        )
        thread.start()
        return {"status": "started", "stage": stage}

    def _execute_stage(self, brief_id: str, stage: str, brief_dict: dict, **kwargs):
        """Execute a single pipeline stage (runs in thread)."""
        db = SessionLocal()
        now = datetime.now(timezone.utc).isoformat()

        try:
            # Mark stage as running
            self._upsert_stage(db, brief_id, stage, "running", started_at=now)

            from geo_cli.orchestrator.schema import AnalysisBrief
            brief = AnalysisBrief.from_dict(brief_dict)
            result = None

            if stage == "query":
                from geo_cli.agents.query_agent import QueryAgent
                agent = QueryAgent(api_key=ANTHROPIC_API_KEY, model=GEO_MODEL)
                result = agent.run(brief, interactive=False)
                self._save_queries_to_db(db, brief_id, result)

            elif stage == "testing":
                from geo_cli.agents.testing_agent import TestingAgent
                query_result = kwargs.get("query_result")
                if not query_result:
                    from geo_cli.agents.query_agent import load_queries
                    query_result = load_queries(brief_id)
                agent = TestingAgent()
                result = agent.run(brief, query_result)
                self._save_responses_to_db(db, brief_id, result)

            elif stage == "analysis":
                from geo_cli.agents.analysis_agent import AnalysisAgent
                testing_result = kwargs.get("testing_result")
                query_result = kwargs.get("query_result")
                if not testing_result:
                    from geo_cli.agents.testing_agent import load_testing_result
                    testing_result = load_testing_result(brief_id)
                if not query_result:
                    from geo_cli.agents.query_agent import load_queries
                    query_result = load_queries(brief_id)
                agent = AnalysisAgent(api_key=ANTHROPIC_API_KEY, model=GEO_MODEL)
                result = agent.run(brief, testing_result, query_result)
                self._save_analysis_to_db(db, brief_id, result)

            elif stage == "report":
                from geo_cli.agents.report_agent import ReportAgent
                analysis_result = kwargs.get("analysis_result")
                if not analysis_result:
                    from geo_cli.agents.analysis_agent import load_analysis
                    analysis_result = load_analysis(brief_id)
                agent = ReportAgent(api_key=ANTHROPIC_API_KEY, model=GEO_MODEL)
                result = agent.run(brief, analysis_result)

            # Store result
            self._results.setdefault(brief_id, {})[stage] = result
            completed_at = datetime.now(timezone.utc).isoformat()
            self._upsert_stage(db, brief_id, stage, "complete", completed_at=completed_at)

        except Exception as e:
            geo_log.error(f"[{stage}] 오류: {e}")
            geo_log.error(traceback.format_exc())
            self._upsert_stage(db, brief_id, stage, "error", error_message=str(e))
            self._results.setdefault(brief_id, {})[stage] = {"error": str(e)}
        finally:
            self._running.pop(brief_id, None)
            db.close()

    def _upsert_stage(self, db, brief_id, stage, status, **kwargs):
        existing = db.query(PipelineStageModel).filter_by(
            brief_id=brief_id, stage=stage
        ).first()
        if existing:
            existing.status = status
            for k, v in kwargs.items():
                if v is not None:
                    setattr(existing, k, v)
        else:
            db.add(PipelineStageModel(brief_id=brief_id, stage=stage, status=status, **kwargs))
        db.commit()

    def _save_queries_to_db(self, db, brief_id, query_result):
        db.query(QueryModel).filter_by(brief_id=brief_id).delete()
        for q in query_result.queries:
            db.add(QueryModel(
                brief_id=brief_id, query_id=q.id, text=q.text,
                language=q.language, type=q.type, persona_id=q.persona_id,
                brand_focus=q.brand_focus, category=q.category,
            ))
        db.commit()

    def _save_responses_to_db(self, db, brief_id, testing_result):
        db.query(RawResponseModel).filter_by(brief_id=brief_id).delete()
        for r in testing_result.responses:
            db.add(RawResponseModel(
                brief_id=brief_id, query_id=r.query_id, query_text=r.query_text,
                platform=r.platform, response_text=r.response_text,
                response_urls=json.dumps(r.response_urls, ensure_ascii=False),
                status=r.status, error_message=r.error_message, timestamp=r.timestamp,
            ))
        db.commit()

    def _save_analysis_to_db(self, db, brief_id, analysis_result):
        db.query(AnalysisModel).filter_by(brief_id=brief_id).delete()
        for a in analysis_result.query_analyses:
            db.add(AnalysisModel(
                brief_id=brief_id, query_id=a.query_id,
                brand_mentioned=a.brand_mentioned, mention_rank=a.mention_rank,
                sentiment=a.sentiment, sentiment_score=a.sentiment_score,
                competitors_mentioned=json.dumps(a.competitors_mentioned, ensure_ascii=False),
                key_quote=a.key_quote,
                response_urls=json.dumps(a.response_urls, ensure_ascii=False),
            ))
        # Save metrics
        m = analysis_result.metrics
        db.query(MetricsModel).filter_by(brief_id=brief_id).delete()
        db.add(MetricsModel(
            brief_id=brief_id, visibility=m.visibility, avg_rank=m.avg_rank,
            rank_1_count=m.rank_1_count, sov=m.sov,
            sentiment_positive=m.sentiment_positive,
            sentiment_negative=m.sentiment_negative,
            sentiment_neutral=m.sentiment_neutral,
            competitor_metrics=json.dumps([c.__dict__ for c in m.competitor_metrics], ensure_ascii=False),
            persona_metrics=json.dumps([p.__dict__ for p in m.persona_metrics], ensure_ascii=False),
            top_urls=json.dumps([u.__dict__ for u in m.top_urls] if m.top_urls else [], ensure_ascii=False),
            computed_at=datetime.now(timezone.utc).isoformat(),
        ))
        db.commit()


# Global singleton
pipeline_service = PipelineService()
