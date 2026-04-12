"""키워드 기반 사람인·잡코리아 수집 후 스킬 추출·요약 갱신."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models import ExtractedSkill, Job
from app.services.ai_recommend import refresh_recommendations_for_category
from app.services.gap_analysis import refresh_demand_supply_summary
from app.services.posting_metadata import extract_posting_metadata, metadata_text_for_skills
from app.services.skill_normalize import extract_skills_from_text
from scrapers.base import log_run_finish, log_run_start, persist_jobs
from scrapers.detail_enrich import gather_recruit_text_for_parsing

logger = logging.getLogger(__name__)

SourceName = Literal["saramin", "jobkorea"]

ProgressEmit = Callable[[dict[str, Any]], None]
CancelCheck = Callable[[], bool]


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


def _finalize_collect(
    db: Session,
    log: Any,
    *,
    category: str,
    total_new_ids: list[int],
    total_fetched: int,
    errors: list[str],
    log_status: str,
) -> dict[str, Any]:
    """이미 DB에 반영된 공고 ID에 대해 스킬·격차·추천을 갱신하고 실행 로그를 마칩니다."""
    if total_new_ids:
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
        status=log_status,
        jobs_fetched=total_fetched,
        jobs_new=len(total_new_ids),
        error_message="\n".join(errors) if errors else None,
    )
    cancelled = log_status == "cancelled"
    return {
        "jobs_fetched": total_fetched,
        "jobs_new": len(total_new_ids),
        "job_ids": total_new_ids[:200],
        "errors": errors,
        "cancelled": cancelled,
    }


def _should_cancel(cancel_check: CancelCheck | None) -> bool:
    return bool(cancel_check and cancel_check())


def generate_collect_events(
    db: Session,
    *,
    keywords: list[str],
    category: str,
    sources: list[SourceName],
    max_pages: int = 1,
    delay_sec: float = 0.4,
    fetch_detail: bool = False,
    use_ocr: bool = True,
    cancel_check: CancelCheck | None = None,
    emit: ProgressEmit | None = None,
) -> Iterator[dict[str, Any]]:
    """
    수집 진행 이벤트를 순차적으로 보냅니다.
    마지막은 ``{"type": "done"|"cancelled", "payload": {...}}`` (payload에 cancelled bool 포함).
    """

    keywords = [k.strip() for k in keywords if k.strip()]
    if not keywords:
        err = {"type": "error", "message": "키워드가 비었습니다."}
        if emit:
            emit(err)
        yield err
        return

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
    total_batches = max(1, len(sources) * len(keywords) * max_pages)
    batches_done = 0

    start_ev = {
        "type": "start",
        "keywords": keywords,
        "category": category,
        "sources": sources,
        "max_pages": max_pages,
        "total_page_batches": total_batches,
        "fetch_detail": fetch_detail,
        "use_ocr": use_ocr,
    }
    if emit:
        emit(start_ev)
    yield start_ev

    try:
        for src in sources:
            for kw in keywords:
                for page in range(1, max_pages + 1):
                    if _should_cancel(cancel_check):
                        payload = _finalize_collect(
                            db,
                            log,
                            category=category,
                            total_new_ids=total_new_ids,
                            total_fetched=total_fetched,
                            errors=errors,
                            log_status="cancelled",
                        )
                        done = {"type": "cancelled", "payload": payload}
                        if emit:
                            emit(done)
                        yield done
                        return

                    prog = {
                        "type": "progress",
                        "phase": "fetch_list",
                        "source": src,
                        "keyword": kw,
                        "page": page,
                        "page_batches_done": batches_done,
                        "page_batches_total": total_batches,
                        "jobs_fetched_so_far": total_fetched,
                        "jobs_new_so_far": len(total_new_ids),
                    }
                    if emit:
                        emit(prog)
                    yield prog

                    try:
                        rows = _fetch_source(src, kw, page)
                    except Exception as e:
                        logger.exception("수집 실패 %s %s p%s", src, kw, page)
                        errors.append(f"{src}:{kw}:p{page}:{e!s}")
                        batches_done += 1
                        continue

                    total_fetched += len(rows)
                    items: list[dict] = []
                    for idx, r in enumerate(rows):
                        if _should_cancel(cancel_check):
                            if items:
                                new_ids, _skipped = persist_jobs(db, src, items)
                                total_new_ids.extend(new_ids)
                            payload = _finalize_collect(
                                db,
                                log,
                                category=category,
                                total_new_ids=total_new_ids,
                                total_fetched=total_fetched,
                                errors=errors,
                                log_status="cancelled",
                            )
                            done = {"type": "cancelled", "payload": payload}
                            if emit:
                                emit(done)
                            yield done
                            return

                        if fetch_detail:
                            det_ev = {
                                "type": "progress",
                                "phase": "detail_row",
                                "source": src,
                                "keyword": kw,
                                "page": page,
                                "row": idx + 1,
                                "rows_total": len(rows),
                                "page_batches_done": batches_done,
                                "page_batches_total": total_batches,
                            }
                            if emit:
                                emit(det_ev)
                            yield det_ev

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
                                errors.append(
                                    f"detail:{src}:{kw}:{detail_u[:40] if detail_u else ''}:{ex!s}"
                                )
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

                    new_ids, _skipped = persist_jobs(db, src, items)
                    total_new_ids.extend(new_ids)
                    batches_done += 1
                    logger.info(
                        "수집 페이지 완료 source=%s keyword=%s page=%s listings=%s new_this_page=%s total_new=%s",
                        src,
                        kw,
                        page,
                        len(rows),
                        len(new_ids),
                        len(total_new_ids),
                    )

                    page_done = {
                        "type": "progress",
                        "phase": "page_done",
                        "source": src,
                        "keyword": kw,
                        "page": page,
                        "listings": len(rows),
                        "new_ids_this_page": len(new_ids),
                        "page_batches_done": batches_done,
                        "page_batches_total": total_batches,
                        "jobs_fetched_so_far": total_fetched,
                        "jobs_new_so_far": len(total_new_ids),
                    }
                    if emit:
                        emit(page_done)
                    yield page_done

                    time.sleep(delay_sec)

        log_status = "success" if not errors else "partial"
        payload = _finalize_collect(
            db,
            log,
            category=category,
            total_new_ids=total_new_ids,
            total_fetched=total_fetched,
            errors=errors,
            log_status=log_status,
        )
        done = {"type": "done", "payload": payload}
        if emit:
            emit(done)
        yield done
    except Exception as e:
        logger.exception("collect 실패")
        log_run_finish(log, db, status="error", error_message=str(e))
        err = {"type": "error", "message": str(e)}
        if emit:
            emit(err)
        yield err
        return


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
    """키워드별·소스별 검색 페이지를 가져와 `jobs`에 저장 (기존 단일 응답 API용)."""
    last: dict[str, Any] | None = None
    for ev in generate_collect_events(
        db,
        keywords=keywords,
        category=category,
        sources=sources,
        max_pages=max_pages,
        delay_sec=delay_sec,
        fetch_detail=fetch_detail,
        use_ocr=use_ocr,
        cancel_check=None,
        emit=None,
    ):
        last = ev
    if not last:
        return {"error": "수집이 비어 있습니다."}
    if last.get("type") == "error":
        return {"error": last.get("message", "수집 실패")}
    if last.get("type") in ("done", "cancelled"):
        return last["payload"]  # type: ignore[return-value]
    return {"error": "수집 결과를 확인할 수 없습니다."}
