"""Briefs API router — CRUD for analysis briefs."""
from __future__ import annotations

import json
import mimetypes
import zipfile
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse

from backend.config import DATA_DIR
from backend.database.engine import SessionLocal
from backend.database.models import BriefModel, PipelineStageModel
from backend.schemas.api_models import ArtifactInfo, BriefDetail, BriefSummary

router = APIRouter()


@router.get("", response_model=list[BriefSummary])
def list_briefs():
    db = SessionLocal()
    try:
        rows = db.query(BriefModel).order_by(BriefModel.created_at.desc()).all()

        # If DB is empty, fallback to file-based listing
        if not rows:
            from geo_cli.utils.file_io import list_briefs as file_list_briefs, load_brief, pipeline_status
            brief_files = file_list_briefs()
            result = []
            for bf in brief_files:
                bid = bf.stem.replace("brief_", "")
                try:
                    brief = load_brief(bid)
                    status = pipeline_status(bid)
                    result.append(BriefSummary(
                        id=bid,
                        title=brief.title or brief.subject.name,
                        status=brief.status,
                        created_at=brief.created_at or "",
                        subject_name=brief.subject.name,
                        subject_type=brief.subject.type,
                        subject_industry=brief.subject.industry,
                        pipeline_stages={s: ("complete" if done else "pending") for s, done in status.items()},
                    ))
                except Exception:
                    continue
            return result

        result = []
        for row in rows:
            stages = db.query(PipelineStageModel).filter_by(brief_id=row.id).all()
            stage_dict = {s.stage: s.status for s in stages}
            if not stage_dict:
                from geo_cli.utils.file_io import pipeline_status
                file_status = pipeline_status(row.id)
                stage_dict = {s: ("complete" if done else "pending") for s, done in file_status.items()}
            result.append(BriefSummary(
                id=row.id,
                title=row.title,
                status=row.status,
                created_at=row.created_at,
                subject_name=row.subject_name,
                subject_type=row.subject_type,
                subject_industry=row.subject_industry,
                pipeline_stages=stage_dict,
            ))
        return result
    finally:
        db.close()


@router.get("/{brief_id}", response_model=BriefDetail)
def get_brief(brief_id: str):
    db = SessionLocal()
    try:
        row = db.query(BriefModel).filter_by(id=brief_id).first()
        if not row:
            # Fallback to file
            from geo_cli.utils.file_io import load_brief
            try:
                brief = load_brief(brief_id)
                return BriefDetail(
                    id=brief_id,
                    title=brief.title or brief.subject.name,
                    status=brief.status,
                    created_at=brief.created_at or "",
                    brief_dict=brief.to_dict(),
                )
            except Exception:
                raise HTTPException(404, f"Brief not found: {brief_id}")

        stages = db.query(PipelineStageModel).filter_by(brief_id=brief_id).all()
        return BriefDetail(
            id=row.id,
            title=row.title,
            status=row.status,
            created_at=row.created_at,
            brief_dict=json.loads(row.brief_json),
            pipeline_stages={s.stage: s.status for s in stages},
        )
    finally:
        db.close()


@router.delete("/{brief_id}")
def delete_brief(brief_id: str):
    db = SessionLocal()
    try:
        db.query(PipelineStageModel).filter_by(brief_id=brief_id).delete()
        deleted = db.query(BriefModel).filter_by(id=brief_id).delete()
        db.commit()

        # Also remove files
        for f in DATA_DIR.glob(f"*{brief_id}*"):
            f.unlink(missing_ok=True)

        if not deleted:
            raise HTTPException(404, f"Brief not found: {brief_id}")
        return {"status": "ok"}
    finally:
        db.close()


@router.get("/{brief_id}/artifacts", response_model=list[ArtifactInfo])
def list_artifacts(brief_id: str):
    from geo_cli.utils.file_io import list_artifacts as file_list_artifacts
    artifacts = file_list_artifacts(brief_id)
    return [
        ArtifactInfo(
            filename=a.path.name,
            label=a.label,
            size=a.path.stat().st_size if a.path.exists() else 0,
        )
        for a in artifacts
    ]


@router.get("/{brief_id}/artifacts.zip")
def download_artifacts_zip(brief_id: str):
    from geo_cli.utils.file_io import list_artifacts as file_list_artifacts

    artifacts = file_list_artifacts(brief_id)
    if not artifacts:
        raise HTTPException(404, "Artifacts not found")

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for artifact in artifacts:
            path = artifact.path
            if path.exists() and path.resolve().is_relative_to(DATA_DIR.resolve()):
                zf.write(path, arcname=path.name)

    buffer.seek(0)
    headers = {
        "Content-Disposition": f'attachment; filename="geo_artifacts_{brief_id}.zip"',
        "Cache-Control": "no-store, max-age=0",
    }
    return StreamingResponse(buffer, media_type="application/zip", headers=headers)


@router.get("/{brief_id}/artifacts/{filename}")
def download_artifact(
    brief_id: str,
    filename: str,
    download: bool = Query(False),
):
    filepath = DATA_DIR / filename
    if not filepath.exists():
        raise HTTPException(404, f"File not found: {filename}")
    # Security: ensure the file is in DATA_DIR
    if not filepath.resolve().is_relative_to(DATA_DIR.resolve()):
        raise HTTPException(403, "Access denied")

    media_type = mimetypes.guess_type(str(filepath))[0] or "application/octet-stream"
    headers = {"Cache-Control": "no-store, max-age=0"}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return FileResponse(filepath, media_type=media_type, filename=filename if download else None, headers=headers)
