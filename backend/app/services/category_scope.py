"""직군 슬러그(기본·사용자 정의)에 따른 공고 범위 — 정확 category 일치 후 유사 키워드 확장."""

from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import ConsultantCustomCategory, Job


def _meta_keyword_bundle(db: Session, slug: str) -> list[str]:
    row = db.query(ConsultantCustomCategory).filter(ConsultantCustomCategory.slug == slug).first()
    if not row:
        return []
    meta = row.meta if isinstance(row.meta, dict) else {}
    primary = [str(x).strip() for x in (meta.get("primary_keywords") or []) if str(x).strip()]
    similar = [str(x).strip() for x in (meta.get("similar_keywords") or []) if str(x).strip()]
    label = (row.label_ko or "").strip()
    out: list[str] = []
    for x in [label, *primary, *similar]:
        if len(x) >= 2 and x not in out:
            out.append(x)
    return out[:22]


def job_ids_for_category(db: Session, category: str | None, limit: int = 500) -> list[int] | None:
    """None 이면 직군 필터 없음(전체). 빈 리스트면 매칭 공고 없음."""
    if not category or str(category).strip().lower() in ("", "all"):
        return None
    cat = str(category).strip()
    rows = (
        db.query(Job.id).filter(Job.category == cat).order_by(Job.id.desc()).limit(limit).all()
    )
    ids = [r[0] for r in rows]
    if ids:
        return ids
    kws = _meta_keyword_bundle(db, cat)
    if not kws:
        return []
    conds = [Job.category == cat]
    for kw in kws:
        conds.append(Job.title.contains(kw))
        conds.append(Job.search_keyword == kw)
    rows2 = (
        db.query(Job.id)
        .filter(or_(*conds))
        .order_by(Job.id.desc())
        .limit(limit)
        .all()
    )
    return [r[0] for r in rows2]


def allowed_analysis_category_slugs(db: Session) -> set[str]:
    from app.seed import CATEGORY_LABEL

    s = set(CATEGORY_LABEL.keys())
    s.update(r.slug for r in db.query(ConsultantCustomCategory.slug).all())
    return s


def collect_category_slugs(db: Session) -> set[str]:
    """수집 API에 허용되는 직군 슬러그(기본·등록·DB에 공고가 있는 임의 슬러그)."""
    s = allowed_analysis_category_slugs(db)
    for (c,) in db.query(Job.category).distinct():
        if c:
            s.add(c)
    return s


def merge_collect_keywords(db: Session, category: str, keywords: list[str]) -> list[str]:
    """등록 직군의 primary·similar 키워드를 수집 검색어 앞에 합칩니다."""
    row = (
        db.query(ConsultantCustomCategory)
        .filter(ConsultantCustomCategory.slug == category)
        .first()
    )
    extra: list[str] = []
    if row and isinstance(row.meta, dict):
        meta = row.meta
        extra.extend(str(x).strip() for x in (meta.get("primary_keywords") or []) if str(x).strip())
        extra.extend(str(x).strip() for x in (meta.get("similar_keywords") or []) if str(x).strip())
        lab = (row.label_ko or "").strip()
        if lab:
            extra.insert(0, lab)
    seen: set[str] = set()
    out: list[str] = []
    for k in extra + [x.strip() for x in keywords if x and x.strip()]:
        kl = k.lower()
        if kl in seen:
            continue
        seen.add(kl)
        out.append(k)
    return out[:24]
