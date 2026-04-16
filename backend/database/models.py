"""SQLAlchemy ORM models for GEO CLI."""
from __future__ import annotations

from sqlalchemy import Boolean, Column, Float, Integer, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class BriefModel(Base):
    __tablename__ = "briefs"

    id = Column(Text, primary_key=True)
    title = Column(Text, nullable=False, default="")
    status = Column(Text, nullable=False, default="draft")
    created_at = Column(Text, nullable=False)
    subject_name = Column(Text, nullable=False, default="")
    subject_type = Column(Text, default="brand")
    subject_industry = Column(Text, default="")
    subject_market = Column(Text, default="")
    brief_json = Column(Text, nullable=False)


class PersonaModel(Base):
    __tablename__ = "personas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    brief_id = Column(Text, nullable=False, index=True)
    persona_id = Column(Text)
    name = Column(Text)
    source = Column(Text, default="user_defined")
    description = Column(Text, default="")


class CompetitorModel(Base):
    __tablename__ = "competitors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    brief_id = Column(Text, nullable=False, index=True)
    name = Column(Text)
    website = Column(Text, default="")
    notes = Column(Text, default="")


class QueryModel(Base):
    __tablename__ = "queries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    brief_id = Column(Text, nullable=False, index=True)
    query_id = Column(Text)
    text = Column(Text)
    language = Column(Text)
    type = Column(Text)
    persona_id = Column(Text, default="")
    brand_focus = Column(Text, default="target")
    category = Column(Text, default="")


class RawResponseModel(Base):
    __tablename__ = "raw_responses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    brief_id = Column(Text, nullable=False, index=True)
    query_id = Column(Text)
    query_text = Column(Text)
    platform = Column(Text, default="chatgpt")
    response_text = Column(Text)
    response_urls = Column(Text, default="[]")
    status = Column(Text, default="success")
    error_message = Column(Text, default="")
    timestamp = Column(Text, default="")


class AnalysisModel(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    brief_id = Column(Text, nullable=False, index=True)
    query_id = Column(Text)
    brand_mentioned = Column(Boolean, default=False)
    mention_rank = Column(Integer, default=0)
    sentiment = Column(Text, default="not_mentioned")
    sentiment_score = Column(Float, default=0.0)
    competitors_mentioned = Column(Text, default="[]")
    key_quote = Column(Text, default="")
    response_urls = Column(Text, default="[]")


class MetricsModel(Base):
    __tablename__ = "metrics"

    brief_id = Column(Text, primary_key=True)
    visibility = Column(Float, default=0.0)
    avg_rank = Column(Float, default=0.0)
    rank_1_count = Column(Integer, default=0)
    sov = Column(Float, default=0.0)
    sentiment_positive = Column(Integer, default=0)
    sentiment_negative = Column(Integer, default=0)
    sentiment_neutral = Column(Integer, default=0)
    competitor_metrics = Column(Text, default="[]")
    persona_metrics = Column(Text, default="[]")
    top_urls = Column(Text, default="[]")
    computed_at = Column(Text)


class PipelineStageModel(Base):
    __tablename__ = "pipeline_stages"

    brief_id = Column(Text, primary_key=True)
    stage = Column(Text, primary_key=True)
    status = Column(Text, nullable=False, default="pending")
    started_at = Column(Text)
    completed_at = Column(Text)
    error_message = Column(Text, default="")


class SettingModel(Base):
    __tablename__ = "settings"

    key = Column(Text, primary_key=True)
    value = Column(Text, nullable=False)
