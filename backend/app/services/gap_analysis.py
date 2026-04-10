"""수요(채용) vs 관심(트렌드) 점수화 및 격차 유형 분류."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import DemandSupplySummary, ExtractedSkill, Job, TrendKeyword

GAP_LABELS_KO = {
    "oversaturated": "과포화 가능성 높음",
    "opportunity": "기회 영역",
    "stable_hot": "안정적 인기 분야",
    "low_priority": "비추천 영역",
}


def compute_demand_by_keyword(db: Session, category: str) -> dict[str, float]:
    rows = (
        db.query(ExtractedSkill.normalized_skill)
        .join(Job, Job.id == ExtractedSkill.job_id)
        .filter(Job.category == category)
        .all()
    )
    counts: dict[str, int] = defaultdict(int)
    for (ns,) in rows:
        counts[ns] += 1
    if not counts:
        return {}
    mx = max(counts.values())
    return {k: (v / mx) * 100 for k, v in counts.items()}


def compute_interest_by_keyword(
    db: Session, category: str, days: int = 90
) -> dict[str, float]:
    since = date.today() - timedelta(days=days)
    rows = (
        db.query(TrendKeyword.keyword, TrendKeyword.interest_score)
        .filter(TrendKeyword.category == category, TrendKeyword.date >= since)
        .all()
    )
    acc: dict[str, list[float]] = defaultdict(list)
    for kw, score in rows:
        acc[kw].append(score)
    return {k: sum(v) / len(v) for k, v in acc.items()}


def classify_gap(demand: float, interest: float) -> str:
    """임계값 기반 4분면 분류."""
    hd, hi = demand >= 55, interest >= 55
    if hi and not hd:
        return "oversaturated"
    if hd and not hi:
        return "opportunity"
    if hd and hi:
        return "stable_hot"
    return "low_priority"


def refresh_demand_supply_summary(db: Session, category: str) -> None:
    demand = compute_demand_by_keyword(db, category)
    interest = compute_interest_by_keyword(db, category)
    all_kw = set(demand) | set(interest)
    for kw in all_kw:
        d = demand.get(kw, 0.0)
        i = interest.get(kw, 0.0)
        g = classify_gap(d, i)
        row = (
            db.query(DemandSupplySummary)
            .filter(
                DemandSupplySummary.keyword == kw,
                DemandSupplySummary.category == category,
            )
            .first()
        )
        if row:
            row.demand_score = d
            row.interest_score = i
            row.gap_type = g
            row.analyzed_at = datetime.utcnow()
        else:
            db.add(
                DemandSupplySummary(
                    keyword=kw,
                    category=category,
                    demand_score=d,
                    interest_score=i,
                    gap_type=g,
                    analyzed_at=datetime.utcnow(),
                )
            )
    db.commit()
