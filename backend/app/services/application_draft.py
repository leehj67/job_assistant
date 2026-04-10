"""공고 메타 + 지원자 프로필을 바탕으로 지원 준비용 초안(체크리스트·다음 단계).

자동 이력서 '제출'은 채용사이트 약관·로그인 이슈로 여기서는 URL 안내와 문구 초안만 제공."""

from __future__ import annotations

import re
from typing import Any

from app.models import ApplicantProfile, Job
from app.services.posting_metadata import merged_job_metadata


def _token_overlap(text: str, line: str) -> bool:
    if not text or not line:
        return False
    words = [w for w in re.split(r"\s+", line) if len(w) >= 2]
    if not words:
        return False
    hits = sum(1 for w in words if w in text)
    return hits >= max(1, len(words) // 3)


def resume_covers_requirement_line(resume_full_text_lower: str, requirement_line: str) -> bool:
    """이력서·경력 합본(소문자)이 자격요건 한 줄과 토큰 수준으로 겹치는지."""
    if not requirement_line or not str(requirement_line).strip():
        return True
    return _token_overlap(resume_full_text_lower, requirement_line.lower())


def build_application_draft(job: Job, profile: ApplicantProfile | None) -> dict[str, Any]:
    meta = merged_job_metadata(job)
    resume = (profile.resume_text or "") if profile else ""
    resume_l = resume.lower()
    portfolio_n = len(profile.portfolio_urls or []) if profile and profile.portfolio_urls else 0

    req_check: list[dict[str, Any]] = []
    for line in meta.get("requirements") or []:
        if not isinstance(line, str):
            continue
        req_check.append(
            {
                "requirement": line.strip(),
                "resume_keyword_overlap": _token_overlap(resume_l, line.lower()),
            }
        )

    pref_check: list[dict[str, Any]] = []
    for line in meta.get("preferred") or []:
        if not isinstance(line, str):
            continue
        pref_check.append(
            {
                "preferred": line.strip(),
                "resume_keyword_overlap": _token_overlap(resume_l, line.lower()),
            }
        )

    return {
        "job": {
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "source_url": job.source_url,
            "category": job.category,
        },
        "normalized_job": {
            "work_location": meta.get("work_location"),
            "salary": meta.get("salary"),
            "career": meta.get("career"),
            "requirements": meta.get("requirements") or [],
            "preferred": meta.get("preferred") or [],
        },
        "requirements_checklist": req_check,
        "preferred_checklist": pref_check,
        "profile": {
            "loaded": profile is not None,
            "career_years": profile.career_years if profile else None,
            "has_resume_text": bool(resume.strip()),
            "portfolio_count": portfolio_n,
        },
        "suggested_cover_letter_sections": [
            "지원 동기 (회사·포지션과의 적합성)",
            "핵심 경력·프로젝트 (요구사항과의 연결)",
            "우대사항 부합 사례",
            "근무·급여·형태에 대한 질문 또는 마무리",
        ],
        "next_steps": [
            {
                "step": 1,
                "action": "원본 공고 페이지에서 지원 형식 확인",
                "url": job.source_url,
            },
            {
                "step": 2,
                "action": "이력서·자기소개서 초안을 프로필의 경력·이력서·포트폴리오와 매칭해 작성 (LLM 연동 예정)",
            },
            {
                "step": 3,
                "action": "지원 사이트에 직접 제입력 또는 첨부 (자동 제출은 미지원)",
            },
        ],
        "note": "자동 제출은 각 채용 플랫폼 약관·인증이 필요해 API로 대행하지 않습니다. 이 응답은 정리·체크용입니다.",
    }
