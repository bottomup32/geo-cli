"""Migrate existing JSON/CSV file data into SQLite database."""
from __future__ import annotations

import json

from backend.database.engine import SessionLocal
from backend.database.models import BriefModel, PipelineStageModel


def migrate_existing_data():
    """Scan data/ for existing briefs and import into DB."""
    from geo_cli.utils.file_io import list_briefs, load_brief, pipeline_status

    db = SessionLocal()
    try:
        brief_files = list_briefs()
        migrated = 0

        for bf in brief_files:
            bid = bf.stem.replace("brief_", "")
            if db.query(BriefModel).filter_by(id=bid).first():
                continue  # already migrated

            try:
                brief = load_brief(bid)
            except Exception:
                continue

            db.add(BriefModel(
                id=brief.brief_id,
                title=brief.title or brief.subject.name,
                status=brief.status or "approved",
                created_at=brief.created_at or "",
                subject_name=brief.subject.name,
                subject_type=brief.subject.type,
                subject_industry=brief.subject.industry or "",
                subject_market=brief.subject.primary_market or "",
                brief_json=brief.to_json(),
            ))

            # Pipeline stages from file existence
            status = pipeline_status(bid)
            for stage, done in status.items():
                db.add(PipelineStageModel(
                    brief_id=brief.brief_id,
                    stage=stage,
                    status="complete" if done else "pending",
                ))

            migrated += 1

        db.commit()
        print(f"Migrated {migrated} briefs to database.")
    finally:
        db.close()


if __name__ == "__main__":
    from backend.database.engine import init_db
    init_db()
    migrate_existing_data()
