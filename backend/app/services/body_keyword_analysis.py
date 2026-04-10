"""공고 본문(메타 텍스트) 키워드 분석: RAKE/YAKE/Kiwi 1단계 + LLM 2단계 + 레거시 차트용 집계."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

from app.models import Job
from app.services.keyword_pipeline import run_full_pipeline
from app.services.posting_metadata import merged_job_metadata, metadata_text_for_skills
from app.services.skill_normalize import SkillGroup, _ALIASES, extract_skills_from_text


def _group_for_normalized_skill(norm: str) -> SkillGroup:
    for _alias, (n, g) in _ALIASES.items():
        if n == norm:
            return g
    return "soft_qual"


SKILL_GROUP_LABEL_KO: dict[str, str] = {
    "language": "언어·런타임",
    "data_tool": "데이터·BI",
    "ai_ml": "AI·ML",
    "collab": "협업·도구",
    "soft_qual": "기타·소프트",
    "infra": "인프라·클라우드",
    "framework": "프레임워크",
}

LLM_CAT_LABEL_KO: dict[str, str] = {
    "language": "언어",
    "framework": "프레임워크",
    "tool": "도구·플랫폼",
    "soft_skill": "소프트스킬",
    "domain": "도메인",
}

_KO_STOP = frozenset(
    """
    및 등 수 위 을 를 이 가 은 는 에 의 로 으로 와 과 도 만 을 통한 대한 관련 경우 통해
    있는 없는 하며 또는 그 이상 이하 이상 미만 해당 각종 담당 주요 예정 가능 환영 지원
    우대 필수 경력 신입 무관 년 차 회 이상 이하 개월 주 일 시 분 명 명의
    있습니다 합니다 입니다 됩니다 있는 없습니다 같은 위한 통해 대해 대하여
    """.split()
)


def _full_analysis_text(job: Job) -> str:
    base = metadata_text_for_skills(job)
    m = merged_job_metadata(job)
    extra: list[str] = []
    for key in ("requirements", "preferred", "responsibilities"):
        for line in m.get(key) or []:
            if isinstance(line, str) and line.strip():
                extra.append(line)
    return f"{job.title}\n{job.company}\n{base}\n" + "\n".join(extra)


def _tokenize_general(text: str) -> list[str]:
    raw = text.lower()
    parts = re.findall(r"[a-z0-9+#.]{2,32}|[가-힣]{2,12}", raw)
    out: list[str] = []
    for p in parts:
        if p in _KO_STOP or len(p) < 2:
            continue
        if p.isdigit():
            continue
        out.append(p)
    return out


def _technical_term_counts(text: str) -> tuple[dict[str, int], dict[SkillGroup, int]]:
    lower = text.lower()
    norm_hits: dict[str, int] = defaultdict(int)
    group_hits: dict[SkillGroup, int] = defaultdict(int)

    for alias, (norm, group) in _ALIASES.items():
        c = lower.count(alias)
        if c == 0 and alias in text:
            c = 1
        if c > 0:
            norm_hits[norm] += c
            group_hits[group] += c

    for _raw, norm, group, _conf in extract_skills_from_text(text):
        if norm_hits.get(norm, 0) == 0:
            norm_hits[norm] += 1
            group_hits[group] += 1

    return dict(norm_hits), dict(group_hits)


def _legacy_charts(
    text: str,
    m: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    norm_hits, group_hits = _technical_term_counts(text)
    tech_sorted = sorted(norm_hits.items(), key=lambda x: -x[1])[:40]

    general_tokens = _tokenize_general(text)
    freq = Counter(general_tokens)
    for norm in norm_hits:
        lk = norm.lower()
        if lk in freq:
            del freq[lk]
    word_top = [{"token": w, "count": c} for w, c in freq.most_common(35)]

    technical_terms = []
    for norm, cnt in tech_sorted:
        grp = _group_for_normalized_skill(norm)
        gs = str(grp)
        technical_terms.append(
            {
                "term": norm,
                "count": cnt,
                "group": gs,
                "group_label_ko": SKILL_GROUP_LABEL_KO.get(gs, gs),
            }
        )

    group_distribution = []
    for g, cnt in sorted(group_hits.items(), key=lambda x: -x[1]):
        gs = str(g)
        group_distribution.append(
            {
                "group": gs,
                "label_ko": SKILL_GROUP_LABEL_KO.get(gs, gs),
                "count": cnt,
            }
        )
    return technical_terms, group_distribution, word_top


def analyze_job_body_keywords(job: Job) -> dict[str, Any]:
    text = _full_analysis_text(job)
    m = merged_job_metadata(job)

    pipe = run_full_pipeline(full_text=text, job_metadata=m)
    llm = pipe.get("stage2", {}).get("llm") if pipe.get("stage2") else None

    legacy_terms, legacy_groups, word_top = _legacy_charts(text, m)

    technical_terms: list[dict[str, Any]] = []
    group_distribution: list[dict[str, Any]] = []
    soft_skills: list[dict[str, Any]] = []

    use_llm = (
        llm
        and isinstance(llm.get("keywords"), list)
        and any(isinstance(x, dict) for x in llm["keywords"])
    )

    if use_llm:
        gh: dict[str, int] = defaultdict(int)
        for kw in llm["keywords"]:
            if not isinstance(kw, dict):
                continue
            cat = (kw.get("category") or "tool").strip()
            if cat == "soft_skill":
                continue
            disp = kw.get("display_ko") or kw.get("normalized") or ""
            if not str(disp).strip():
                continue
            technical_terms.append(
                {
                    "term": str(disp),
                    "count": 1,
                    "group": cat,
                    "group_label_ko": LLM_CAT_LABEL_KO.get(
                        cat, SKILL_GROUP_LABEL_KO.get(cat, cat)
                    ),
                    "normalized": kw.get("normalized"),
                    "section": kw.get("section"),
                    "confidence": kw.get("confidence"),
                }
            )
            gh[cat] += 1
        for cat, cnt in sorted(gh.items(), key=lambda x: -x[1]):
            group_distribution.append(
                {
                    "group": cat,
                    "label_ko": LLM_CAT_LABEL_KO.get(cat, cat),
                    "count": cnt,
                }
            )
        for s in llm.get("soft_skills") or []:
            if isinstance(s, dict) and s.get("phrase"):
                soft_skills.append(
                    {"phrase": str(s["phrase"]), "section": s.get("section")}
                )

    if not technical_terms:
        technical_terms = legacy_terms
        group_distribution = legacy_groups

    form_summary = {
        "work_location": m.get("work_location"),
        "salary": m.get("salary"),
        "career": m.get("career"),
        "requirements_lines": len(m.get("requirements") or []),
        "preferred_lines": len(m.get("preferred") or []),
        "responsibilities_lines": len(m.get("responsibilities") or []),
    }

    return {
        "job_id": job.id,
        "title": job.title,
        "company": job.company,
        "category": job.category,
        "form_summary": form_summary,
        "analyzed_char_length": len(text),
        "technical_terms": technical_terms,
        "group_distribution": group_distribution,
        "word_frequency": word_top,
        "soft_skills": soft_skills,
        "pipeline": pipe,
    }
