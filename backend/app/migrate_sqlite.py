"""SQLite 기존 DB에 컬럼 추가 (create_all만으로는 반영되지 않음)."""

import re

from sqlalchemy import inspect, text

from app.database import engine


def _backfill_jobs_metadata_legacy() -> None:
    """기존 description 원문을 파싱해 job_metadata로 옮기고 description 은 비움."""
    from app.database import SessionLocal
    from app.models import Job
    from app.services.posting_metadata import empty_job_metadata, extract_posting_metadata

    url_in_desc = re.compile(r"상세:\s*(https?://[^\s]+)")
    db = SessionLocal()
    try:
        pending = db.query(Job).filter(Job.job_metadata.is_(None)).all()
        for job in pending:
            desc = (job.description or "").strip()
            if desc:
                if not (job.source_url or "").strip():
                    m = url_in_desc.search(desc)
                    if m:
                        job.source_url = m.group(1)[:1000]
                job.job_metadata = extract_posting_metadata(
                    desc,
                    company=job.company,
                    listing_location=job.location,
                )
                job.description = ""
            else:
                job.job_metadata = empty_job_metadata(job.company)
        if pending:
            db.commit()
    finally:
        db.close()


def run_sqlite_migrations() -> None:
    if engine.dialect.name != "sqlite":
        return
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("jobs")}
    with engine.begin() as conn:
        if "external_id" not in cols:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN external_id VARCHAR(128)"))
        if "search_keyword" not in cols:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN search_keyword VARCHAR(256)"))
        if "source_url" not in cols:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN source_url VARCHAR(1024)"))
        if "job_metadata" not in cols:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN job_metadata TEXT"))
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_jobs_source_external_id "
                "ON jobs (source, external_id)"
            )
        )
    if "consultant_custom_categories" in insp.get_table_names():
        ccat = {c["name"] for c in insp.get_columns("consultant_custom_categories")}
        with engine.begin() as conn:
            if "meta" not in ccat:
                conn.execute(text("ALTER TABLE consultant_custom_categories ADD COLUMN meta TEXT"))
    _backfill_jobs_metadata_legacy()
