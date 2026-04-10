"""수집 파이프라인 공통: 로그·메타데이터는 `ScraperRunLog`에 기록."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import Job, ScraperRunLog
from app.services.posting_metadata import empty_job_metadata


@dataclass
class ScraperContext:
    source: str
    db: Session
    meta: dict[str, Any] = field(default_factory=dict)


def log_run_start(db: Session, source: str, meta: dict | None = None) -> ScraperRunLog:
    row = ScraperRunLog(
        source=source,
        run_started_at=datetime.utcnow(),
        status="running",
        jobs_fetched=0,
        jobs_new=0,
        meta=meta or {},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def log_run_finish(
    log: ScraperRunLog,
    db: Session,
    *,
    status: str,
    jobs_fetched: int = 0,
    jobs_new: int = 0,
    error_message: str | None = None,
):
    log.run_finished_at = datetime.utcnow()
    log.status = status
    log.jobs_fetched = jobs_fetched
    log.jobs_new = jobs_new
    log.error_message = error_message
    db.commit()


def persist_jobs(db: Session, source: str, items: list[dict]) -> tuple[list[int], int]:
    """items: title, company, category, job_metadata, external_id?, search_keyword?, location?, posted_at?, source_url?

    description 은 저장하지 않음(빈 문자열). 원본 본문은 메타데이터 추출 후 폐기.

    Returns: (new_job_ids, skipped_duplicates)
    """
    new_ids: list[int] = []
    skipped = 0
    for it in items:
        ext = it.get("external_id")
        if ext:
            exists = (
                db.query(Job.id)
                .filter(Job.source == source, Job.external_id == ext)
                .first()
            )
            if exists:
                skipped += 1
                continue
        su = it.get("source_url")
        meta = it.get("job_metadata")
        if not isinstance(meta, dict):
            meta = empty_job_metadata(it.get("company"))
        row = Job(
            source=source,
            external_id=ext,
            search_keyword=it.get("search_keyword"),
            title=it["title"][:500],
            company=(it.get("company") or "")[:250],
            category=it["category"],
            description="",
            job_metadata=meta,
            location=it.get("location"),
            posted_at=it.get("posted_at"),
            collected_at=datetime.utcnow(),
            source_url=(su[:1000] if isinstance(su, str) and su.strip() else None),
        )
        db.add(row)
        db.flush()
        new_ids.append(row.id)
    db.commit()
    return new_ids, skipped


def run_demo_stub(ctx: ScraperContext) -> int:
    """데모: 실제 HTTP 없이 로그만 남기는 스텁."""
    log = log_run_start(ctx.db, ctx.source, meta=ctx.meta)
    log_run_finish(log, ctx.db, status="skipped", jobs_fetched=0, jobs_new=0)
    return 0
