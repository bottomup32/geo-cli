"""Pipeline API router — run stages, get status, WebSocket for logs."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, UploadFile, WebSocket, WebSocketDisconnect

from backend.config import DATA_DIR
from backend.database.engine import SessionLocal
from backend.database.models import BriefModel, PipelineStageModel
from backend.schemas.api_models import PipelineStageStatus, PipelineStatusResponse
from backend.services.log_broadcaster import log_broadcaster
from backend.services.pipeline_service import pipeline_service
from geo_cli.utils.file_io import atomic_write

router = APIRouter()

VALID_STAGES = ["query", "testing", "analysis", "report"]


@router.post("/run/{brief_id}/{stage}")
def run_stage(brief_id: str, stage: str):
    if stage not in VALID_STAGES:
        raise HTTPException(400, f"Invalid stage: {stage}")

    db = SessionLocal()
    try:
        brief_row = db.query(BriefModel).filter_by(id=brief_id).first()
        if not brief_row:
            raise HTTPException(404, f"Brief not found: {brief_id}")
        brief_dict = json.loads(brief_row.brief_json)
    finally:
        db.close()

    result = pipeline_service.run_stage(brief_id, stage, brief_dict)
    if "error" in result:
        raise HTTPException(409, result["error"])

    log_broadcaster.start(brief_id)
    return result


@router.get("/status/{brief_id}", response_model=PipelineStatusResponse)
def get_pipeline_status(brief_id: str):
    db = SessionLocal()
    try:
        stages = db.query(PipelineStageModel).filter_by(brief_id=brief_id).all()
        if not stages:
            # Fallback: check file-based status
            from geo_cli.utils.file_io import pipeline_status
            file_status = pipeline_status(brief_id)
            # Normalize "queries" key to "query" for consistency
            normalized = {("query" if k == "queries" else k): v for k, v in file_status.items()}
            return PipelineStatusResponse(
                brief_id=brief_id,
                stages=[
                    PipelineStageStatus(
                        stage=s, status="complete" if done else "pending"
                    )
                    for s, done in normalized.items()
                ],
            )
        return PipelineStatusResponse(
            brief_id=brief_id,
            stages=[
                PipelineStageStatus(
                    stage=s.stage, status=s.status,
                    started_at=s.started_at, completed_at=s.completed_at,
                    error_message=s.error_message or "",
                )
                for s in stages
            ],
        )
    finally:
        db.close()


@router.get("/running/{brief_id}")
def get_running_stage(brief_id: str):
    return {
        "running": pipeline_service.is_running(brief_id),
        "stage": pipeline_service.current_stage(brief_id),
    }


@router.get("/result/{brief_id}/{stage}")
def get_stage_result(brief_id: str, stage: str):
    result = pipeline_service.get_result(brief_id, stage)
    if result is None:
        raise HTTPException(404, "Result not found")
    if hasattr(result, "to_dict"):
        return result.to_dict()
    return {"result": str(result)}


@router.post("/upload-testing/{brief_id}")
async def upload_testing_result(brief_id: str, file: UploadFile):
    from geo_cli.agents.testing_agent import RawResponse, TestingResult

    content = await file.read()
    data = json.loads(content.decode("utf-8"))

    responses = [
        RawResponse(
            query_id=r["query_id"], query_text=r["query_text"],
            platform=r.get("platform", "chatgpt"),
            response_text=r["response_text"],
            response_urls=r.get("response_urls", []),
            timestamp=r.get("timestamp", ""),
            status=r.get("status", "success"),
            error_message=r.get("error_message", ""),
        )
        for r in data.get("responses", [])
    ]
    result = TestingResult(
        brief_id=data.get("brief_id", brief_id),
        platform=data.get("platform", "chatgpt"),
        responses=responses,
        total=data.get("total", len(responses)),
        success=data.get("success", sum(1 for r in responses if r.status == "success")),
        error=data.get("error", sum(1 for r in responses if r.status == "error")),
    )

    save_path = DATA_DIR / f"raw_chatgpt_{brief_id}.json"
    atomic_write(save_path, json.dumps(result.to_dict(), ensure_ascii=False, indent=2))

    pipeline_service._results.setdefault(brief_id, {})["testing"] = result
    return {"status": "ok", "total": result.total, "success": result.success}


@router.websocket("/ws/{brief_id}")
async def pipeline_logs_websocket(ws: WebSocket, brief_id: str):
    await ws.accept()
    log_broadcaster.register(brief_id, ws)

    try:
        # Start broadcasting loop
        broadcast_task = asyncio.create_task(log_broadcaster.broadcast_loop(brief_id))

        while True:
            data = await ws.receive_json()
            # Client can request stage results
            if data.get("type") == "get_result":
                stage = data.get("stage")
                result = pipeline_service.get_result(brief_id, stage)
                if result and hasattr(result, "to_dict"):
                    await ws.send_json({"type": "stage_result", "stage": stage, "data": result.to_dict()})

            elif data.get("type") == "check_status":
                running = pipeline_service.is_running(brief_id)
                current = pipeline_service.current_stage(brief_id)
                await ws.send_json({"type": "status", "running": running, "stage": current})

    except WebSocketDisconnect:
        pass
    finally:
        log_broadcaster.unregister(brief_id, ws)
        log_broadcaster.stop(brief_id)
