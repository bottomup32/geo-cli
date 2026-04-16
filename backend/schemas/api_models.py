"""Pydantic models for API request/response."""
from __future__ import annotations

from pydantic import BaseModel


# ── Interview ─────────────────────────────────────────────────────────────────

class InterviewMessage(BaseModel):
    content: str


class InterviewApproveRequest(BaseModel):
    brief_dict: dict
    query_count: int = 75


class InterviewStateResponse(BaseModel):
    messages: list[dict]
    interview_done: bool
    brief_dict: dict | None = None


# ── Pipeline ──────────────────────────────────────────────────────────────────

class PipelineRunRequest(BaseModel):
    pass


class PipelineStageStatus(BaseModel):
    stage: str
    status: str
    started_at: str | None = None
    completed_at: str | None = None
    error_message: str = ""


class PipelineStatusResponse(BaseModel):
    brief_id: str
    stages: list[PipelineStageStatus]


# ── Briefs ────────────────────────────────────────────────────────────────────

class BriefSummary(BaseModel):
    id: str
    title: str
    status: str
    created_at: str
    subject_name: str
    subject_type: str
    subject_industry: str | None = None
    pipeline_stages: dict[str, str] = {}


class BriefDetail(BaseModel):
    id: str
    title: str
    status: str
    created_at: str
    brief_dict: dict
    pipeline_stages: dict[str, str] = {}


class ArtifactInfo(BaseModel):
    filename: str
    label: str
    size: int


# ── Prompts ───────────────────────────────────────────────────────────────────

class PromptContent(BaseModel):
    name: str
    content: str
    char_count: int


class PromptUpdateRequest(BaseModel):
    content: str


# ── Settings ──────────────────────────────────────────────────────────────────

class SettingsResponse(BaseModel):
    api_key_set: bool
    api_key_preview: str
    model: str
    data_dir: str
    chatgpt_profile_dir: str
    selectors: dict[str, str] = {}


class SettingsUpdateRequest(BaseModel):
    api_key: str | None = None
    model: str | None = None
    chatgpt_profile_dir: str | None = None


class SelectorsUpdateRequest(BaseModel):
    selectors: dict[str, str]
