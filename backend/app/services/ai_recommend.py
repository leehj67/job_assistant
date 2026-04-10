"""추천 문장 생성: OpenAI 선택, 없으면 규칙 기반 한국어 문장."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import DemandSupplySummary, Recommendation, TargetType
from app.services.gap_analysis import GAP_LABELS_KO
from app.services.llm_client import chat_completion


def _rule_based_academy(category: str, db: Session) -> list[tuple[str, str]]:
    rows = (
        db.query(DemandSupplySummary)
        .filter(DemandSupplySummary.category == category)
        .order_by(DemandSupplySummary.demand_score.desc())
        .limit(5)
        .all()
    )
    top_skills = [r.keyword for r in rows[:3]]
    opp = (
        db.query(DemandSupplySummary)
        .filter(
            DemandSupplySummary.category == category,
            DemandSupplySummary.gap_type == "opportunity",
        )
        .order_by(DemandSupplySummary.demand_score.desc())
        .limit(3)
        .all()
    )
    over = (
        db.query(DemandSupplySummary)
        .filter(
            DemandSupplySummary.category == category,
            DemandSupplySummary.gap_type == "oversaturated",
        )
        .limit(3)
        .all()
    )

    lines: list[tuple[str, str]] = []
    if top_skills:
        lines.append(
            (
                "핵심 역량 요구",
                f"최근 채용 공고 기준으로 {', '.join(top_skills)} 역량의 요구 빈도가 높습니다.",
            )
        )
    if over:
        kws = ", ".join(o.keyword for o in over)
        lines.append(
            (
                "관심 대비 수요 해석",
                f"{kws} 키워드는 관심도 대비 실질 채용 수요가 상대적으로 낮을 수 있어, 단독 입문 강의보다 실무 프로젝트와 결합하는 편이 적절합니다.",
            )
        )
    if opp:
        kws = ", ".join(o.keyword for o in opp)
        lines.append(
            (
                "신규 강의 기회",
                f"수요는 높은 반면 검색 관심도가 낮은 영역({kws})이 있어, 교육기관 관점에서 차별화된 강의 개설 여지가 있습니다.",
            )
        )
    return lines


def _rule_based_jobseeker(category: str, db: Session) -> list[tuple[str, str]]:
    stable = (
        db.query(DemandSupplySummary)
        .filter(
            DemandSupplySummary.category == category,
            DemandSupplySummary.gap_type == "stable_hot",
        )
        .limit(4)
        .all()
    )
    over = (
        db.query(DemandSupplySummary)
        .filter(
            DemandSupplySummary.category == category,
            DemandSupplySummary.gap_type == "oversaturated",
        )
        .limit(3)
        .all()
    )
    opp = (
        db.query(DemandSupplySummary)
        .filter(
            DemandSupplySummary.category == category,
            DemandSupplySummary.gap_type == "opportunity",
        )
        .limit(3)
        .all()
    )
    lines: list[tuple[str, str]] = []
    lines.append(
        (
            "시장 우선순위",
            "단순 검색 관심도가 높은 분야보다, 채용 공고에 반복 등장하는 실무형 역량을 먼저 확보하는 것이 유리합니다.",
        )
    )
    if stable:
        lines.append(
            (
                "우선 학습 스킬",
                f"{', '.join(s.keyword for s in stable)} 은(는) 수요와 관심이 함께 높아 준비 가치가 큽니다.",
            )
        )
    if over:
        lines.append(
            (
                "과포화 경고",
                f"{', '.join(o.keyword for o in over)} 은(는) 관심 대비 채용 수요가 제한적일 수 있어 진입 시 차별화 전략이 필요합니다.",
            )
        )
    if opp:
        lines.append(
            (
                "유망 방향",
                f"{', '.join(o.keyword for o in opp)} 은(는) 수요는 있는데 관심이 상대적으로 낮아, 스킬을 쌓으면 경쟁 우위를 기대할 수 있습니다.",
            )
        )
    return lines


def ensure_recommendations(db: Session, category: str, use_llm: bool = True) -> None:
    """추천 레코드 갱신 (학원/취준생 각 1세트 이상)."""
    for target in (TargetType.academy, TargetType.jobseeker):
        existing = (
            db.query(Recommendation)
            .filter(
                Recommendation.category == category,
                Recommendation.target_type == target.value,
            )
            .first()
        )
        if existing:
            continue
        _add_one_recommendation(db, category, target, use_llm=use_llm)
    db.commit()


def refresh_recommendations_for_category(db: Session, category: str, use_llm: bool = True) -> None:
    """해당 직군 추천 문장을 모두 다시 생성."""
    db.query(Recommendation).filter(Recommendation.category == category).delete()
    db.commit()
    for target in (TargetType.academy, TargetType.jobseeker):
        _add_one_recommendation(db, category, target, use_llm=use_llm)
    db.commit()


def _add_one_recommendation(
    db: Session, category: str, target: TargetType, use_llm: bool = True
) -> None:
    if target == TargetType.academy:
        pairs = _rule_based_academy(category, db)
        title = "교육기관 맞춤 인사이트"
    else:
        pairs = _rule_based_jobseeker(category, db)
        title = "취업준비생 맞춤 인사이트"

    body = "\n\n".join(f"• {p[1]}" for p in pairs) if pairs else "데이터가 부족합니다."
    if use_llm and pairs:
        ctx = "\n".join(f"- {a}: {b}" for a, b in pairs)
        llm = chat_completion(
            "당신은 한국어 HR/교육 도메인 애널리스트입니다. 불필요한 서론 없이 실무형 문장만 작성합니다.",
            f"직군 카테고리: {category}\n요약 불릿:\n{ctx}\n위를 바탕으로 3~5문장으로 자연스럽게 합쳐 설명하세요.",
        )
        if llm:
            body = llm

    db.add(
        Recommendation(
            target_type=target.value,
            category=category,
            title=title,
            content=body,
            generated_at=datetime.utcnow(),
        )
    )


def interpretation_for_gap(db: Session, category: str, keyword: str) -> str:
    row = (
        db.query(DemandSupplySummary)
        .filter(
            DemandSupplySummary.category == category,
            DemandSupplySummary.keyword == keyword,
        )
        .first()
    )
    if not row:
        return "해당 키워드 요약 데이터가 없습니다."
    label = GAP_LABELS_KO.get(row.gap_type, row.gap_type)
    if row.gap_type == "oversaturated":
        return (
            f"최근 관심도는 상대적으로 높지만 채용 공고에서의 요구 빈도는 제한적일 수 있습니다. ({label})"
        )
    if row.gap_type == "opportunity":
        return "채용 수요는 높은 반면 검색 관심도가 낮아, 교육·이직 관점에서 기회로 볼 수 있습니다."
    if row.gap_type == "stable_hot":
        return "수요와 관심이 모두 높은 안정적으로 인기 있는 영역입니다."
    return "수요와 관심이 모두 낮거나 데이터가 충분하지 않아 우선순위가 낮을 수 있습니다."
