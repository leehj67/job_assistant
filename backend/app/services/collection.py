"""키워드 기반 사람인·잡코리아 수집 후 스킬 추출·요약 갱신."""

from __future__ import annotations

import logging
import time
from typing import Literal

from sqlalchemy.orm import Session

from app.models import ExtractedSkill, Job
from app.services.gap_analysis import refresh_demand_supply_summary
from app.services.skill_normalize import extract_skills_from_text
from app.services.ai_recommend import refresh_recommendations_for_category
from app.services.posting_metadata import extract_posting_metadata, metadata_text_for_skills
from scrapers.base import log_run_finish, log_run_start, persist_jobs
from scrapers.detail_enrich import gather_recruit_text_for_parsing

logger = logging.getLogger(__name__)

SourceName = Literal["saramin", "jobkorea"]


def _fetch_source(source: SourceName, keyword: str, page: int) -> list[dict]:
    if source == "saramin":
        from scrapers.saramin_search import fetch_listings

        return fetch_listings(keyword, page)
    if source == "jobkorea":
        from scrapers.jobkorea_search import fetch_listings

        return fetch_listings(keyword, page)
    raise ValueError(source)


def attach_skills_for_jobs(db: Session, job_ids: list[int]) -> None:
    for jid in job_ids:
        job = db.get(Job, jid)
        if not job:
            continue
        text = metadata_text_for_skills(job)
        for raw, norm, group, conf in extract_skills_from_text(text):
            db.add(
                ExtractedSkill(
                    job_id=job.id,
                    raw_skill=raw,
                    normalized_skill=norm,
                    skill_group=group,
                    confidence=conf,
                )
            )
    db.commit()


def collect_by_keywords(
    db: Session,
    *,
    keywords: list[str],
    category: str,
    sources: list[SourceName],
    max_pages: int = 1,
    delay_sec: float = 0.4,
    fetch_detail: bool = False,
    use_ocr: bool = True,
) -> dict:
    """키워드별·소스별 검색 페이지를 가져와 `jobs`에 저장."""
    keywords = [k.strip() for k in keywords if k.strip()]
    if not keywords:
        return {"error": "키워드가 비었습니다."}

    meta = {
        "keywords": keywords,
        "category": category,
        "sources": sources,
        "max_pages": max_pages,
        "fetch_detail": fetch_detail,
        "use_ocr": use_ocr,
    }
    log = log_run_start(db, "collect_keywords", meta=meta)
    total_new_ids: list[int] = []
    total_fetched = 0
    errors: list[str] = []

    try:
        for src in sources:
            for kw in keywords:
                for page in range(1, max_pages + 1):
                    try:
                        rows = _fetch_source(src, kw, page)
                    except Exception as e:
                        logger.exception("수집 실패 %s %s p%s", src, kw, page)
                        errors.append(f"{src}:{kw}:p{page}:{e!s}")
                        continue
                    total_fetched += len(rows)
                    items = []
                    for r in rows:
                        preamble = r.get("description", "")
                        detail_u = r.get("source_url")
                        blob = preamble
                        if fetch_detail and detail_u:
                            try:
                                blob = gather_recruit_text_for_parsing(
                                    detail_url=detail_u,
                                    preamble=preamble,
                                    use_ocr=use_ocr,
                                )
                            except Exception as ex:
                                logger.warning("상세 본문 수집 실패 %s: %s", detail_u, ex)
                                errors.append(f"detail:{src}:{kw}:{detail_u[:40]}:{ex!s}")
                        meta = extract_posting_metadata(
                            blob,
                            company=r.get("company"),
                            listing_location=r.get("location"),
                        )
                        items.append(
                            {
                                "title": r["title"],
                                "company": r["company"],
                                "category": category,
                                "location": r.get("location"),
                                "external_id": r.get("external_id"),
                                "search_keyword": kw,
                                "posted_at": None,
                                "source_url": r.get("source_url"),
                                "job_metadata": meta,
                            }
                        )
                        time.sleep(delay_sec * 0.5)
                    new_ids, skipped = persist_jobs(db, src, items)
                    total_new_ids.extend(new_ids)
                    time.sleep(delay_sec)

        attach_skills_for_jobs(db, total_new_ids)
        refresh_demand_supply_summary(db, category)
        try:
            refresh_recommendations_for_category(db, category, use_llm=True)
        except Exception as ex:
            logger.warning("추천 LLM 생성 실패, 규칙 기반으로 재시도: %s", ex)
            refresh_recommendations_for_category(db, category, use_llm=False)

        log_run_finish(
            log,
            db,
            status="success" if not errors else "partial",
            jobs_fetched=total_fetched,
            jobs_new=len(total_new_ids),
            error_message="\n".join(errors) if errors else None,
        )
        return {
            "jobs_fetched": total_fetched,
            "jobs_new": len(total_new_ids),
            "job_ids": total_new_ids[:200],
            "errors": errors,
        }
    except Exception as e:
        logger.exception("collect 실패")
        log_run_finish(log, db, status="error", error_message=str(e))
        raise
