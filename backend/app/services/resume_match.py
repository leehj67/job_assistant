"""이력서 텍스트와 수집된 공고(ExtractedSkill·메타)를 맞춰 적합도·갭을 계산."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import ExtractedSkill, Job
from app.services.application_draft import resume_covers_requirement_line
from app.services.posting_metadata import merged_job_metadata
from app.services.skill_normalize import extract_skills_from_text


def _requirement_line_met(resume_lower: str, line: str, resume_norms_lower: set[str]) -> bool:
    """토큰 겹침 + 이력서에서 추출한 정규 스킬명이 요건 문장에 포함되는지."""
    if resume_covers_requirement_line(resume_lower, line):
        return True
    low = line.lower()
    for n in resume_norms_lower:
        if len(n) >= 2 and n in low:
            return True
    return False


def _combined_resume_text(resume_text: str | None, career_summary: str | None) -> str:
    parts = [p.strip() for p in (resume_text or "", career_summary or "") if p and p.strip()]
    return "\n".join(parts)


def extract_resume_skills(text: str) -> list[tuple[str, str, str]]:
    """(normalized, skill_group) 리스트, 중복 제거 순서 유지."""
    found = extract_skills_from_text(text)
    seen: set[str] = set()
    out: list[tuple[str, str, str]] = []
    for _raw, norm, group, _conf in found:
        if norm in seen:
            continue
        seen.add(norm)
        out.append((norm, str(group), norm))
    return out


def _title_bonus(resume_lower: str, title: str) -> float:
    if not resume_lower or not title:
        return 0.0
    tl = title.lower()
    toks = [t for t in re.split(r"[^\w가-힣]+", tl) if len(t) >= 2]
    if not toks:
        return 0.0
    hits = sum(1 for t in toks if t in resume_lower)
    return min(15.0, hits * 3.0)


def _metadata_skill_hits(meta: dict[str, Any], resume_norms_lower: set[str]) -> float:
    bonus = 0.0
    for key in ("requirements", "preferred", "responsibilities"):
        lines = meta.get(key) or []
        if not isinstance(lines, list):
            continue
        for line in lines:
            if not isinstance(line, str):
                continue
            low = line.lower()
            for n in resume_norms_lower:
                if len(n) >= 2 and n.lower() in low:
                    bonus += 2.0
                    break
    return min(bonus, 25.0)


def score_job(
    job: Job,
    job_skills: set[str],
    resume_norms: set[str],
    resume_norms_lower: set[str],
    resume_lower: str,
) -> tuple[float, list[str]]:
    if not resume_norms:
        return 0.0, []
    matched = sorted(resume_norms & job_skills)
    union = resume_norms | job_skills
    jaccard = len(matched) / max(len(union), 1)
    base = 100.0 * jaccard + 8.0 * len(matched)
    base += _title_bonus(resume_lower, job.title)
    meta = merged_job_metadata(job)
    base += _metadata_skill_hits(meta, resume_norms_lower)
    return round(base, 2), matched


def match_jobs_for_resume(
    db: Session,
    resume_text: str | None,
    career_summary: str | None,
    category: str | None,
    limit: int,
) -> dict[str, Any]:
    text = _combined_resume_text(resume_text, career_summary)
    skill_rows = extract_resume_skills(text)
    resume_norms = {s[0] for s in skill_rows}
    resume_norms_lower = {n.lower() for n in resume_norms}
    resume_lower = text.lower()

    q = db.query(Job).order_by(Job.id.desc())
    if category:
        q = q.filter(Job.category == category)
    jobs = q.limit(400).all()
    if not jobs:
        return {
            "resume_skills": [{"normalized": s[0], "skill_group": s[1]} for s in skill_rows],
            "jobs": [],
        }

    job_ids = [j.id for j in jobs]
    skill_q = (
        db.query(ExtractedSkill.job_id, ExtractedSkill.normalized_skill)
        .filter(ExtractedSkill.job_id.in_(job_ids))
        .all()
    )
    job_to_skills: dict[int, set[str]] = defaultdict(set)
    for jid, ns in skill_q:
        job_to_skills[jid].add(ns)

    scored: list[tuple[float, Job, list[str], int]] = []
    for job in jobs:
        js = job_to_skills.get(job.id, set())
        sc, matched = score_job(job, js, resume_norms, resume_norms_lower, resume_lower)
        scored.append((sc, job, matched, len(js)))

    scored.sort(key=lambda x: (-x[0], -x[1].id))
    top = scored[:limit]

    jobs_out: list[dict[str, Any]] = []
    for sc, j, matched, jcnt in top:
        meta = merged_job_metadata(j)
        req_lines = [
            str(l).strip()
            for l in (meta.get("requirements") or [])
            if isinstance(l, str) and str(l).strip()
        ]
        mismatches = [
            line
            for line in req_lines
            if not _requirement_line_met(resume_lower, line, resume_norms_lower)
        ]
        jobs_out.append(
            {
                "id": j.id,
                "title": j.title,
                "company": j.company,
                "category": j.category,
                "source": j.source,
                "source_url": j.source_url,
                "match_score": sc,
                "matched_skills": matched,
                "job_skill_count": jcnt,
                "requirements_total": len(req_lines),
                "requirements_mismatch": mismatches,
            }
        )

    return {
        "resume_skills": [{"normalized": s[0], "skill_group": s[1]} for s in skill_rows],
        "jobs": jobs_out,
    }


def preparation_insights(
    db: Session,
    resume_text: str | None,
    career_summary: str | None,
    category: str | None,
    top_n: int = 28,
    gap_take: int = 8,
) -> dict[str, Any]:
    text = _combined_resume_text(resume_text, career_summary)
    skill_rows = extract_resume_skills(text)
    resume_norms = {s[0] for s in skill_rows}

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
        .limit(top_n)
        .all()
    )

    industry = [
        {"normalized_skill": r[0], "skill_group": r[1], "job_count": int(r[2])}
        for r in rows
    ]
    aligned = [s for s in industry if s["normalized_skill"] in resume_norms]
    aligned_names = [s["normalized_skill"] for s in aligned]

    gap_skills: list[str] = []
    for s in industry:
        if s["normalized_skill"] not in resume_norms:
            gap_skills.append(s["normalized_skill"])
        if len(gap_skills) >= gap_take:
            break

    action_items: list[str] = []
    cat_label = category or "전체 직군"
    if not text.strip():
        action_items.append(
            "이력서 또는 경력 요약을 입력하면, 수집된 공고와 비교해 부족한 역량을 더 정확히 짚을 수 있습니다."
        )
    for name in gap_skills[:6]:
        action_items.append(
            f"「{name}」은(는) 최근 {cat_label} 공고에서 자주 요구됩니다. "
            "관련 프로젝트·교육 이력을 이력서에 구체적으로 적어 두면 지원 적합도가 올라갑니다."
        )
    if resume_norms and aligned_names:
        action_items.insert(
            0,
            f"이력서에서 확인된 강점 키워드: {', '.join(aligned_names[:8])}"
            + (" …" if len(aligned_names) > 8 else "")
            + ". 공고의 자격요건·우대사항에 이 키워드를 연결해 서술해 보세요.",
        )

    return {
        "category": category or "all",
        "resume_skills": [{"normalized": s[0], "skill_group": s[1]} for s in skill_rows],
        "industry_top_skills": industry,
        "aligned_skills": aligned_names,
        "gap_skills": gap_skills,
        "action_items": action_items,
    }
