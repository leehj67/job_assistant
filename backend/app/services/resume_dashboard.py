"""이력서 전체 텍스트 → 요약·강약점·차트용 시리즈(공고 DB와 비교)."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import ExtractedSkill, Job
from app.services.collect_suggestions import build_collect_suggestions
from app.services.llm_client import chat_completion
from app.services.resume_match import extract_resume_skills

GROUP_LABEL_KO: dict[str, str] = {
    "language": "언어·스크립트",
    "data_tool": "데이터·분석 도구",
    "ai_ml": "AI·ML",
    "collab": "협업·도구",
    "soft_qual": "기타·소프트",
    "infra": "인프라·클라우드",
    "framework": "프레임워크",
}

ALL_GROUPS = list(GROUP_LABEL_KO.keys())

_YEARS_RE = re.compile(
    r"(?:경력|총|약)\s*(\d{1,2})\s*년|(\d{1,2})\s*년\s*차|(\d{1,2})\s*\+?\s*years?\s+of\s+experience",
    re.IGNORECASE,
)


def estimate_career_years(text: str) -> int | None:
    if not text:
        return None
    best: int | None = None
    for m in _YEARS_RE.finditer(text):
        for g in m.groups():
            if g is None:
                continue
            try:
                y = int(g)
            except ValueError:
                continue
            if 0 < y <= 40:
                best = max(best or 0, y)
    return best


def _fallback_summary_snippet(text: str, max_len: int = 480) -> str:
    one = re.sub(r"\s+", " ", text).strip()
    if len(one) <= max_len:
        return one
    return one[: max_len - 1] + "…"


def generate_summary_paragraph(text: str) -> str:
    snippet = text[:8000]
    system = "당신은 채용 담당자 관점의 이력서 코치입니다. 한국어로 간결하게 작성합니다."
    user = (
        "다음 이력서 텍스트만 보고 핵심 경력·역할·성과를 3~5문장으로 요약하세요. "
        "목록·마크다운 없이 하나의 문단으로만 출력하세요.\n\n---\n"
        f"{snippet}\n---"
    )
    r = chat_completion(system, user)
    if r and r.strip():
        return r.strip()[:2200]
    return _fallback_summary_snippet(text)


def applicable_areas(category: str | None, skill_groups: set[str]) -> list[str]:
    out: list[str] = []
    if category == "data_analyst":
        out.extend(["데이터 분석·리포팅", "지표·대시보드 설계"])
    elif category == "ai_engineer":
        out.extend(["ML·딥러닝 모델 개발", "LLM·생성형 AI 응용"])
    elif category == "backend_developer":
        out.extend(["백엔드·API 서비스 개발", "시스템 설계·연동"])
    else:
        out.append("복수 직군 공고와의 교차 비교(전체 범위)")

    if "data_tool" in skill_groups:
        out.append("SQL·BI·분석 파이프라인")
    if "ai_ml" in skill_groups:
        out.append("머신러닝·모델 운영")
    if "infra" in skill_groups:
        out.append("클라우드·컨테이너 운영")
    if "framework" in skill_groups:
        out.append("웹·서비스 프레임워크 기반 개발")
    if "language" in skill_groups:
        out.append("주력 언어 기반 구현·자동화")

    seen: set[str] = set()
    uniq = []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq[:10]


def _industry_skills(
    db: Session, category: str | None, limit: int = 36
) -> list[dict[str, Any]]:
    q = (
        db.query(
            ExtractedSkill.normalized_skill,
            ExtractedSkill.skill_group,
            func.count(func.distinct(ExtractedSkill.job_id)),
        )
        .join(Job, Job.id == ExtractedSkill.job_id)
    )
    if category:
        q = q.filter(Job.category == category)
    rows = (
        q.group_by(ExtractedSkill.normalized_skill, ExtractedSkill.skill_group)
        .order_by(func.count(func.distinct(ExtractedSkill.job_id)).desc())
        .limit(limit)
        .all()
    )
    return [
        {"normalized_skill": r[0], "skill_group": r[1], "job_count": int(r[2])}
        for r in rows
    ]


def build_resume_dashboard(
    db: Session,
    resume_text: str,
    category: str | None,
) -> dict[str, Any]:
    text = resume_text.strip()
    skill_tuples = extract_resume_skills(text)
    resume_norms = {s[0] for s in skill_tuples}
    skill_groups_resume = {s[1] for s in skill_tuples}

    industry = _industry_skills(db, category, limit=36)
    max_jobs = max((r["job_count"] for r in industry), default=1)

    top_for_compare = industry[:12]
    aligned_n = sum(1 for r in top_for_compare if r["normalized_skill"] in resume_norms)
    gap_n = len(top_for_compare) - aligned_n

    strengths: list[str] = []
    for r in top_for_compare:
        if r["normalized_skill"] in resume_norms:
            strengths.append(f"{r['normalized_skill']} (수집 공고 {r['job_count']}건에서 요구)")

    weaknesses: list[str] = []
    for r in top_for_compare:
        if r["normalized_skill"] not in resume_norms:
            weaknesses.append(f"{r['normalized_skill']} — 상위 수요인데 이력서 규칙 추출에 없음")

    skill_bars: list[dict[str, Any]] = []
    for r in industry[:10]:
        jc = r["job_count"]
        demand = round(100.0 * jc / max_jobs, 1)
        cover = 100.0 if r["normalized_skill"] in resume_norms else 12.0
        skill_bars.append(
            {
                "skill": r["normalized_skill"],
                "demand_index": demand,
                "resume_cover": cover,
            }
        )

    group_market: dict[str, int] = defaultdict(int)
    for r in industry:
        group_market[str(r["skill_group"])] += r["job_count"]

    group_resume_count: dict[str, int] = defaultdict(int)
    for _n, g, _ in skill_tuples:
        group_resume_count[str(g)] += 1

    max_m = max(group_market.values()) if group_market else 1
    max_r = max(group_resume_count.values()) if group_resume_count else 1

    group_radar: list[dict[str, Any]] = []
    for g in ALL_GROUPS:
        group_radar.append(
            {
                "group_key": g,
                "label_ko": GROUP_LABEL_KO[g],
                "resume_score": round(min(100.0, group_resume_count.get(g, 0) / max_r * 100), 1),
                "market_score": round(min(100.0, group_market.get(g, 0) / max_m * 100), 1),
            }
        )

    if not top_for_compare:
        strength_gap_pie = [{"name": "공고 스킬 데이터 없음", "value": 1.0}]
    else:
        strength_gap_pie = [
            {"name": "시장 상위 스킬 중 보유", "value": float(aligned_n)},
            {"name": "시장 상위 스킬 중 보완", "value": float(max(gap_n, 0))},
        ]

    gap_priority: list[dict[str, Any]] = []
    for r in industry:
        if r["normalized_skill"] not in resume_norms:
            jc = r["job_count"]
            gap_priority.append(
                {
                    "skill": r["normalized_skill"],
                    "demand_index": round(100.0 * jc / max_jobs, 1),
                    "resume_cover": 0.0,
                }
            )
        if len(gap_priority) >= 10:
            break

    years = estimate_career_years(text)
    summary_para = generate_summary_paragraph(text) if text else ""
    areas = applicable_areas(category, skill_groups_resume)

    prep_notes: list[str] = []
    if not industry:
        prep_notes.append(
            "해당 범위에 수집된 공고·스킬 데이터가 없습니다. 키워드 수집 후 다시 분석해 보세요."
        )
    for r in gap_priority[:5]:
        prep_notes.append(
            f"「{r['skill']}」 수요 지수 {r['demand_index']:.0f} — 프로젝트·교육 이력을 이력서에 명시하면 유리합니다."
        )

    career_summary_block = _build_career_summary_block(
        summary_para=summary_para,
        skill_tuples=skill_tuples,
        years=years,
        areas=areas,
        strengths=strengths,
        weaknesses=weaknesses,
    )

    collect_suggestions = build_collect_suggestions(
        db,
        resume_text=text,
        career_summary=None,
        analysis_category_hint=category,
        career_years_override=years,
    )

    return {
        "core_skills": [{"normalized": s[0], "skill_group": s[1]} for s in skill_tuples],
        "career_years_estimate": years,
        "summary_paragraph": summary_para,
        "career_summary_suggested": career_summary_block,
        "applicable_areas": areas,
        "strengths": strengths[:10],
        "weaknesses": weaknesses[:10],
        "preparation_notes": prep_notes,
        "charts": {
            "skill_bars": skill_bars,
            "group_radar": group_radar,
            "strength_gap_pie": strength_gap_pie,
            "gap_priority_bars": gap_priority,
        },
        "collect_suggestions": collect_suggestions,
    }


def _build_career_summary_block(
    summary_para: str,
    skill_tuples: list[tuple[str, str, str]],
    years: int | None,
    areas: list[str],
    strengths: list[str],
    weaknesses: list[str],
) -> str:
    skills_line = ", ".join(s[0] for s in skill_tuples) or "(규칙 기반으로 잡힌 기술 키워드 없음 — Python, SQL 등을 본문에 명시해 주세요)"
    y_line = (
        f"약 {years}년 (이력서 문구 기반 추정)"
        if years is not None
        else "연차를 자동으로 읽지 못했습니다. 숫자로 명시하거나 아래에 수동 입력하세요."
    )
    lines = [
        "【경력·역량 요약】",
        summary_para,
        "",
        "【핵심 기술 및 역량】",
        skills_line,
        "",
        "【경력 연차(추정)】",
        y_line,
        "",
        "【지원 가능 영역(추정)】",
        ", ".join(areas) if areas else "—",
        "",
        "【강점 — 현재 수집 공고 상위 스킬 대비】",
        "; ".join(strengths[:6]) if strengths else "일치 항목이 적거나 공고 데이터가 부족합니다.",
        "",
        "【보완점 — 공고 대비 준비】",
        "; ".join(weaknesses[:6]) if weaknesses else "—",
    ]
    return "\n".join(lines)
