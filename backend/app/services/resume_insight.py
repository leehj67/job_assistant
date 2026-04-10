"""이력서 기반 시장 인사이트: 적합도, 갭 영향도, 차별화 자산, 경로, 액션 플랜.

기존 gap_analysis, collect_suggestions, resume_match, posting_metadata, llm_client 를 조합."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.models import DemandSupplySummary, Job
from app.seed import CATEGORY_LABEL
from app.services.collect_suggestions import build_collect_suggestions
from app.services.gap_analysis import compute_demand_by_keyword, compute_interest_by_keyword
from app.services.llm_client import chat_completion
from app.services.posting_metadata import merged_job_metadata
from app.services.resume_match import extract_resume_skills
from app.services.resume_dashboard import estimate_career_years
from app.services.skill_normalize import _ALIASES

SECTION_WEIGHT_REQ = 1.0
SECTION_WEIGHT_PREF = 0.45
SECTION_WEIGHT_RESP = 0.7


def _combined_text(resume_text: str | None, career_summary: str | None) -> str:
    parts = [p.strip() for p in (resume_text or "", career_summary or "") if p and p.strip()]
    return "\n".join(parts)


def _mentions_skill_in_text(norm: str, text: str) -> bool:
    if not text or not norm:
        return False
    low = text.lower()
    n = norm.lower()
    if n in low:
        return True
    for alias, (mapped, _) in _ALIASES.items():
        if mapped == norm and alias in low:
            return True
    if len(n) >= 3 and re.search(r"\b" + re.escape(n) + r"\b", low):
        return True
    return False


def _metadata_section_frequencies(
    db: Session,
    category: str,
    skills: list[str],
    job_limit: int = 380,
) -> dict[str, dict[str, float]]:
    """스킬별 requirements/preferred/responsibilities 등장 문서 비율."""
    jobs = (
        db.query(Job)
        .filter(Job.category == category)
        .order_by(Job.id.desc())
        .limit(job_limit)
        .all()
    )
    n = max(len(jobs), 1)
    counts: dict[str, dict[str, int]] = {s: {"req": 0, "pref": 0, "resp": 0} for s in skills}

    for job in jobs:
        meta = merged_job_metadata(job)
        blobs = {
            "req": "\n".join(str(x) for x in (meta.get("requirements") or []) if isinstance(x, str)),
            "pref": "\n".join(str(x) for x in (meta.get("preferred") or []) if isinstance(x, str)),
            "resp": "\n".join(str(x) for x in (meta.get("responsibilities") or []) if isinstance(x, str)),
        }
        for skill in skills:
            if _mentions_skill_in_text(skill, blobs["req"]):
                counts[skill]["req"] += 1
            if _mentions_skill_in_text(skill, blobs["pref"]):
                counts[skill]["pref"] += 1
            if _mentions_skill_in_text(skill, blobs["resp"]):
                counts[skill]["resp"] += 1

    out: dict[str, dict[str, float]] = {}
    for s in skills:
        c = counts[s]
        out[s] = {
            "req_freq": c["req"] / n,
            "pref_freq": c["pref"] / n,
            "resp_freq": c["resp"] / n,
        }
    return out


def _market_fit_score(
    demand: dict[str, float],
    resume_norms: set[str],
    top_n: int = 22,
) -> float:
    """상위 수요 스킬 가중 평균 충족률 (0~100)."""
    if not demand:
        return 0.0
    ordered = sorted(demand.items(), key=lambda x: -x[1])[:top_n]
    if not ordered:
        return 0.0
    tw = sum(d for _, d in ordered) or 1.0
    mw = sum(d for s, d in ordered if s in resume_norms)
    return round(100.0 * mw / tw, 1)


def _impact_score(
    demand_val: float,
    req_f: float,
    pref_f: float,
    resp_f: float,
) -> float:
    section_combo = (
        SECTION_WEIGHT_REQ * req_f
        + SECTION_WEIGHT_PREF * pref_f
        + SECTION_WEIGHT_RESP * resp_f
    )
    return round(demand_val * max(section_combo, 0.02) * 1.2, 2)


def _classify_gap_lists(
    db: Session,
    category: str,
    demand: dict[str, float],
    interest: dict[str, float],
    resume_norms: set[str],
    freq_map: dict[str, dict[str, float]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    high_impact: list[dict[str, Any]] = []
    optional_gaps: list[dict[str, Any]] = []
    differentiator_gaps: list[dict[str, Any]] = []

    candidates = sorted(demand.keys(), key=lambda k: -demand[k])[:45]

    for skill in candidates:
        if skill in resume_norms:
            continue
        d = demand.get(skill, 0.0)
        fm = freq_map.get(skill) or {"req_freq": 0, "pref_freq": 0, "resp_freq": 0}
        imp = _impact_score(d, fm["req_freq"], fm["pref_freq"], fm["resp_freq"])
        high_impact.append(
            {
                "skill": skill,
                "impact_score": imp,
                "demand_score": round(d, 2),
                "section_profile": {
                    "requirements_ratio": round(fm["req_freq"] * 100, 1),
                    "preferred_ratio": round(fm["pref_freq"] * 100, 1),
                    "responsibilities_ratio": round(fm["resp_freq"] * 100, 1),
                },
                "reason": "자격·담당 문맥에서 반복 등장하는데 이력서 규칙 추출에 없음",
            }
        )

    high_impact.sort(key=lambda x: -x["impact_score"])

    for item in high_impact[:22]:
        fm = freq_map.get(item["skill"]) or {"req_freq": 0, "pref_freq": 0, "resp_freq": 0}
        if fm["pref_freq"] > fm["req_freq"] * 1.15 and item.get("demand_score", 0) < 70:
            optional_gaps.append(
                {
                    **item,
                    "reason": "우대 문맥 비중이 높고 필수 대비 우선순위는 상대적으로 낮을 수 있음",
                }
            )

    rows = (
        db.query(DemandSupplySummary)
        .filter(DemandSupplySummary.category == category, DemandSupplySummary.gap_type == "opportunity")
        .order_by(DemandSupplySummary.demand_score.desc())
        .limit(12)
        .all()
    )
    for r in rows:
        if r.keyword in resume_norms:
            continue
        differentiator_gaps.append(
            {
                "skill": r.keyword,
                "demand_score": round(r.demand_score, 2),
                "interest_score": round(r.interest_score, 2),
                "reason": "채용 수요 대비 검색 관심이 낮아 확보 시 차별화 여지(시장 요약 기준)",
            }
        )

    return high_impact[:12], optional_gaps[:8], differentiator_gaps[:8]


def _differentiator_assets(
    db: Session,
    category: str,
    resume_norms: set[str],
    demand: dict[str, float],
    interest: dict[str, float],
) -> list[dict[str, Any]]:
    """이력서에 있고 수요는 있는데 관심이 상대적으로 낮은 스킬(희소·실무 가치)."""
    assets: list[dict[str, Any]] = []
    summaries = (
        db.query(DemandSupplySummary)
        .filter(DemandSupplySummary.category == category)
        .all()
    )
    by_kw = {r.keyword: r for r in summaries}

    for skill in resume_norms:
        d = demand.get(skill)
        if d is None and skill in by_kw:
            d = by_kw[skill].demand_score
        if d is None:
            continue
        if d < 32:
            continue
        i = interest.get(skill)
        if skill in by_kw:
            i = by_kw[skill].interest_score
        if i is None:
            i = 40.0
        if i > d * 0.95 and i > 62:
            continue
        assets.append(
            {
                "skill": skill,
                "demand_score": round(float(d), 2),
                "interest_score": round(float(i), 2),
                "reason": "공고 수요 대비 검색·관심 히트가 상대적으로 낮아 이력서에서 강조하면 대비가 쉬움",
            }
        )

    assets.sort(key=lambda x: (-x["demand_score"], x["interest_score"]))
    return assets[:10]


def _career_path_extensions(ranked: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    if not ranked:
        return [], [], []

    best = ranked[0]
    adjacent: list[dict[str, Any]] = []
    for r in ranked[1:]:
        if best["score"] - r["score"] <= 8.5:
            adjacent.append(
                {
                    "slug": r["slug"],
                    "label_ko": r["label_ko"],
                    "score": r["score"],
                    "rationale": "1순위 직군과 점수 차가 작아 스킬·포트폴리오 보강으로 확장 가능성이 큼",
                }
            )
        if len(adjacent) >= 2:
            break

    worst = ranked[-1]
    hard = [
        {
            "slug": worst["slug"],
            "label_ko": worst["label_ko"],
            "score": worst["score"],
            "rationale": "현재 이력서 신호 대비 적합 점수가 가장 낮아 직접 전환 시 학습·경력 스토리 부담이 큼",
        }
    ]

    paths: list[str] = [
        f"현재 포지션은 「{best['label_ko']}」에 가장 가깝습니다 (내부 적합 점수 {best['score']}).",
    ]
    if len(ranked) > 1:
        sec = ranked[1]
        paths.append(
            f"「{sec['label_ko']}」 방향은 격차가 크지 않으면({best['score'] - sec['score']:.1f}점 차) "
            f"Python·ML·서비스 경험 등을 포트폴리오에 추가하며 단계적으로 확장할 수 있습니다."
        )
    paths.append(
        f"「{worst['label_ko']}」 직군은 현재 신호 대비 진입 난이도가 높아, 우선 {best['label_ko']} 포지션을 타깃으로 한 뒤 전환을 검토하는 편이 효율적입니다."
    )
    return adjacent, hard, paths


def _market_positioning_label(fit: float) -> tuple[str, str]:
    if fit >= 72:
        return "상위 충족", "핵심 요구 스킬 상당수가 이미 이력서에 드러나 있어 해당 직군 공고와 정합성이 높습니다."
    if fit >= 52:
        return "중간 충족", "주요 요구의 절반 이상을 충족합니다. 부족 분야를 우선순위로 보완하면 지원 서류 경쟁력이 빠르게 올라갑니다."
    if fit >= 32:
        return "하위~중간 충족", "핵심 스킬이 일부만 드러납니다. 자격요건 키워드 정렬과 프로젝트 근거 보강이 필요합니다."
    return "초기 단계", "해당 직군 핵심 요구 대비 이력서에 기술 신호가 부족합니다. 수요 높은 스킬부터 명시하세요."


def _rule_action_plan(
    market_fit: float,
    primary_label: str,
    high_impact: list[dict[str, Any]],
    optional_gaps: list[dict[str, Any]],
    differentiators: list[dict[str, Any]],
    ranked: list[dict[str, Any]],
) -> dict[str, list[str]]:
    immediate: list[str] = []
    mid_term: list[str] = []
    strategy: list[str] = []

    if high_impact:
        top3 = [x["skill"] for x in high_impact[:3]]
        immediate.append(
            f"이력서 자격요건·경력란에 {', '.join(top3)} 키워드를 명시하고, 각각 1줄 프로젝트 근거를 추가하세요 (현재 시장 영향도 상위 갭)."
        )
    if differentiators[:2]:
        ds = ", ".join(d["skill"] for d in differentiators[:2])
        immediate.append(
            f"차별화 가능 스킬({ds})은 상단 요약 또는 핵심 역량에 bullet로 분리해 검색·서류 스캔에 걸리게 하세요."
        )
    if market_fit < 45 and high_impact:
        mid_term.append(
            f"{primary_label} 직군 상위 수요인 「{high_impact[0]['skill']}」 — 온라인 과제·토이 프로젝트 1건을 완료해 이력서에 링크·성과 수치를 적으세요."
        )
    if len(high_impact) > 2:
        mid_term.append(
            f"추가로 {', '.join(x['skill'] for x in high_impact[1:3])} 중 하나를 4~8주 학습 로드맵으로 잡고, 부족 영역만 집중하세요."
        )
    if optional_gaps:
        mid_term.append(
            f"우대 비중 갭: {', '.join(x['skill'] for x in optional_gaps[:2])} — 필수보다 우선순위는 낮으나 서류에 ‘학습 중’이라도 적으면 유리할 수 있습니다."
        )

    if ranked and len(ranked) >= 2:
        best, worst = ranked[0], ranked[-1]
        if best["score"] - worst["score"] > 8:
            strategy.append(
                f"{worst['label_ko']} 직군으로의 직접 피벗보다 {best['label_ko']} 포지션을 먼저 공략한 뒤, 인접 스킬로 확장하는 경로가 데이터상 효율적입니다."
            )
    if market_fit >= 65:
        strategy.append("시장 적합도가 이미 높습니다. 과열 키워드만 쫓기보다 차별화 자산·성과 수치로 지원 동기를 분리하세요.")

    return {
        "immediate_actions": immediate[:4],
        "mid_term_actions": mid_term[:5],
        "strategy_actions": strategy[:4],
    }


def _llm_enrich_action_plan(
    resume_excerpt: str,
    primary_label: str,
    market_fit: float,
    high_skills: list[str],
    diff_skills: list[str],
    rule_plan: dict[str, list[str]],
) -> dict[str, list[str]]:
    system = (
        "당신은 한국 IT 채용 코치입니다. 추상적 조언·'열심히 하세요' 금지. "
        "반드시 주어진 스킬 이름과 직군·수치를 문장에 넣으세요. 한국어, 짧은 bullet 문장만."
    )
    user = (
        f"직군: {primary_label}\n시장 적합도: {market_fit}%\n"
        f"우선 갭 스킬: {', '.join(high_skills[:5])}\n"
        f"차별화 자산: {', '.join(diff_skills[:5])}\n"
        f"이력서 발췌(앞부분): {resume_excerpt[:1200]}\n\n"
        f"규칙 기반 초안:\n즉시: {rule_plan['immediate_actions']}\n중기: {rule_plan['mid_term_actions']}\n전략: {rule_plan['strategy_actions']}\n\n"
        "위 초안을 바탕으로 즉시/중기/전략 각각 2문장 이내로 다듬어 JSON만 출력:\n"
        '{"immediate_actions":[],"mid_term_actions":[],"strategy_actions":[]}'
    )
    raw = chat_completion(system, user)
    if not raw:
        return rule_plan
    try:
        import json

        m = json.loads(raw.strip().replace("```json", "").replace("```", "").strip())
        out = {
            "immediate_actions": m.get("immediate_actions") or rule_plan["immediate_actions"],
            "mid_term_actions": m.get("mid_term_actions") or rule_plan["mid_term_actions"],
            "strategy_actions": m.get("strategy_actions") or rule_plan["strategy_actions"],
        }
        for k in out:
            if isinstance(out[k], list):
                out[k] = [str(x) for x in out[k] if str(x).strip()][:6]
        return out
    except Exception:
        return rule_plan


def build_resume_insight(
    db: Session,
    *,
    resume_text: str,
    career_summary: str | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    full = _combined_text(resume_text, career_summary)
    skill_tuples = extract_resume_skills(full)
    resume_norms = {s[0] for s in skill_tuples}
    resume_skills_evidence = [{"normalized": s[0], "skill_group": s[1]} for s in skill_tuples]

    years = estimate_career_years(full)
    hint = (category or "").strip() or None
    if hint == "all":
        hint = None

    cs = build_collect_suggestions(
        db,
        resume_text=resume_text or "",
        career_summary=career_summary,
        analysis_category_hint=hint,
        career_years_override=years,
    )
    ranked = cs["category_ranked"]
    primary_slug = cs["primary_category_slug"]
    primary_label = cs["primary_category_label_ko"]

    market_cat = primary_slug
    demand = compute_demand_by_keyword(db, market_cat)
    interest = compute_interest_by_keyword(db, market_cat)

    market_fit = _market_fit_score(demand, resume_norms)
    fit_label, fit_reason = _market_positioning_label(market_fit)

    top_demand_keys = sorted(demand.keys(), key=lambda k: -demand[k])[:40]
    freq_map = _metadata_section_frequencies(db, market_cat, top_demand_keys)

    high_impact, optional_gaps, differentiator_gaps = _classify_gap_lists(
        db, market_cat, demand, interest, resume_norms, freq_map
    )
    differentiator_assets = _differentiator_assets(db, market_cat, resume_norms, demand, interest)

    adjacent, hard_transition, path_recommendations = _career_path_extensions(ranked)

    core_strengths: list[str] = []
    for s in sorted(resume_norms, key=lambda x: -demand.get(x, 0))[:6]:
        ds = demand.get(s, 0.0)
        core_strengths.append(f"{s} — 해당 직군 공고 수요 지수 상위권({ds:.0f}점대)에 이미 포함")

    matched_for_evidence = [s for s in sorted(demand.keys(), key=lambda k: -demand[k])[:25] if s in resume_norms]
    missing_for_evidence = [s for s in sorted(demand.keys(), key=lambda k: -demand[k])[:25] if s not in resume_norms]

    rule_plan = _rule_action_plan(
        market_fit,
        primary_label,
        high_impact,
        optional_gaps,
        differentiator_assets,
        ranked,
    )
    action_plan = _llm_enrich_action_plan(
        full,
        primary_label,
        market_fit,
        [x["skill"] for x in high_impact],
        [x["skill"] for x in differentiator_assets],
        rule_plan,
    )

    return {
        "summary": {
            "market_fit_score": market_fit,
            "market_fit_category_slug": market_cat,
            "market_fit_category_label": CATEGORY_LABEL.get(market_cat, market_cat),
            "current_best_fit_category": primary_slug,
            "adjacent_categories": adjacent,
            "hard_transition_categories": hard_transition,
        },
        "core_strengths": core_strengths,
        "high_impact_gaps": high_impact[:8],
        "optional_gaps": optional_gaps[:6],
        "differentiator_gaps": differentiator_gaps,
        "differentiator_assets": differentiator_assets,
        "market_positioning": {
            "fit_label": fit_label,
            "fit_reason": fit_reason,
        },
        "path_recommendations": path_recommendations,
        "action_plan": action_plan,
        "collect_suggestions": {
            "search_keywords": cs["search_keywords"],
            "primary_category_slug": cs["primary_category_slug"],
            "primary_category_label_ko": cs["primary_category_label_ko"],
            "category_ranked": cs["category_ranked"],
            "role_expansion_notes": cs["role_expansion_notes"],
            "optional_gap_keywords": cs["optional_gap_keywords"],
        },
        "evidence": {
            "resume_skills": resume_skills_evidence,
            "market_top_skills": [k for k, _ in sorted(demand.items(), key=lambda x: -x[1])[:20]],
            "matched_skills": matched_for_evidence,
            "missing_skills": missing_for_evidence[:20],
        },
    }
