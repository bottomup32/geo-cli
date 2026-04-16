"""Interview API router — WebSocket for streaming, REST for state management."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.database.engine import SessionLocal
from backend.database.models import BriefModel, PipelineStageModel
from backend.schemas.api_models import InterviewApproveRequest, InterviewStateResponse
from backend.services.interview_service import interview_service

router = APIRouter()


@router.websocket("/ws/{session_id}")
async def interview_websocket(ws: WebSocket, session_id: str):
    await ws.accept()
    session = interview_service.get_or_create(session_id)

    # Send existing messages on connect
    if session.messages:
        await ws.send_json({
            "type": "history",
            "messages": session.messages,
            "interview_done": session.interview_done,
            "brief_dict": session.brief_dict,
        })

    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") == "message":
                async for event in session_service_stream(session, data["content"]):
                    await ws.send_json(event)
    except WebSocketDisconnect:
        pass


async def session_service_stream(session, user_text: str):
    async for event in interview_service.send_message_streaming(session, user_text):
        yield event


@router.get("/state/{session_id}", response_model=InterviewStateResponse)
def get_interview_state(session_id: str):
    session = interview_service.get_session(session_id)
    if not session:
        return InterviewStateResponse(messages=[], interview_done=False)
    return InterviewStateResponse(
        messages=session.messages,
        interview_done=session.interview_done,
        brief_dict=session.brief_dict,
    )


@router.post("/approve")
def approve_brief(req: InterviewApproveRequest):
    from geo_cli.orchestrator.schema import AnalysisBrief, _generate_brief_id
    from geo_cli.utils.file_io import save_brief

    brief_dict = req.brief_dict
    brief_dict.setdefault("query_settings", {})["target_count"] = req.query_count

    brief = AnalysisBrief.from_dict(brief_dict)
    if not brief.brief_id:
        brief.brief_id = _generate_brief_id()
    brief.created_at = datetime.now(timezone.utc).isoformat()
    brief.status = "approved"

    # Save to file
    save_brief(brief)

    # Save to DB
    db = SessionLocal()
    try:
        db.merge(BriefModel(
            id=brief.brief_id,
            title=brief.title or brief.subject.name,
            status="approved",
            created_at=brief.created_at,
            subject_name=brief.subject.name,
            subject_type=brief.subject.type,
            subject_industry=brief.subject.industry or "",
            subject_market=brief.subject.primary_market or "",
            brief_json=brief.to_json(),
        ))
        # Init pipeline stages
        for stage in ["brief", "query", "testing", "analysis", "report"]:
            status = "complete" if stage == "brief" else "pending"
            db.merge(PipelineStageModel(
                brief_id=brief.brief_id, stage=stage, status=status,
            ))
        db.commit()
    finally:
        db.close()

    return {
        "status": "ok",
        "brief_id": brief.brief_id,
        "brief_dict": brief.to_dict(),
    }


@router.post("/restart/{session_id}")
def restart_interview(session_id: str):
    interview_service.delete_session(session_id)
    return {"status": "ok"}
