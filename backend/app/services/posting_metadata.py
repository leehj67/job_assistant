"""채용 공고 텍스트에서 지원요건·우대·근무지·연봉·경력 등 구조화 메타데이터 추출 (RAG/지원 준비용).

원본 HTML/긴 본문은 DB에 두지 않고, 이 모듈이 만든 dict만 `jobs.job_metadata`에 저장합니다."""

from __future__ import annotations

import re
from typing import Any

from app.models import Job

DEFAULT_SALARY_LABEL = "내규에 따름"

# (bucket, line-must-match regex) — 순서: 담당업무 먼저(자격과 혼동 방지)
_SECTION_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "responsibilities",
        re.compile(
            r"^\s*(?:■\s*)?(?:담당\s*업무|주요\s*업무|업무\s*내용|업무\s*소개|하는\s*일|업무\s*개요)\s*:?\s*$",
            re.I,
        ),
    ),
    (
        "requirements",
        re.compile(
            r"^\s*(?:■\s*)?(?:자격\s*요건|지원\s*자격|필수\s*자격|필수\s*요건|지원\s*요건|"
            r"필수\s*조건|필수역량|지원\s*조건|자격\s*조건)\s*:?\s*$",
            re.I,
        ),
    ),
    (
        "preferred",
        re.compile(
            r"^\s*(?:■\s*)?(?:우대\s*사항|우대\s*요건|우대\s*조건|우대조건|우대\s*경력|우대\s*기술)\s*:?\s*$",
            re.I,
        ),
    ),
    (
        "benefits",
        re.compile(
            r"^\s*(?:■\s*)?(?:복리후생|복지|혜택|제\s*공\s*내역|급여\s*조건)\s*:?\s*$",
            re.I,
        ),
    ),
    (
        "work_condition",
        re.compile(
            r"^\s*(?:■\s*)?(?:근무\s*조건|근무지|근무\s*장소|근무\s*지역|근무\s*형태|근무\s*일정|재택|출근|채용\s*형태)\s*:?\s*$",
            re.I,
        ),
    ),
    (
        "education",
        re.compile(r"^\s*(?:■\s*)?(?:학력\s*조건|학력)\s*:?\s*$", re.I),
    ),
]


def empty_job_metadata(company: str | None = None) -> dict[str, Any]:
    return {
        "company_display": (company or "").strip() or None,
        "work_location": None,
        "company_location_hint": None,
        "salary": DEFAULT_SALARY_LABEL,
        "career": {"type": "unknown", "min_years": None, "raw": None},
        "requirements": [],
        "preferred": [],
        "responsibilities": [],
        "listing_hints": [],
        "other_sections": {},
        "extraction_version": 2,
    }


def _slug_header(line: str, max_len: int = 40) -> str:
    s = re.sub(r"[^\w가-힣]+", "_", line.strip())[:max_len].strip("_")
    return s or "misc"


def parse_salary_from_text(text: str) -> str | None:
    if not text:
        return None
    t = text[:12000]
    patterns = [
        r"연봉\s*[:：]?\s*([^\n]{1,160})",
        r"급여\s*[:：]?\s*([^\n]{1,160})",
        r"보수\s*[:：]?\s*([^\n]{1,160})",
        r"(\d{2,4}\s*~\s*\d{2,4}\s*만\s*원)",
        r"(\d{3,4}\s*만\s*원\s*[~\-~～]\s*\d{3,4}\s*만\s*원)",
        r"(연\s*\d{3,4}\s*만?\s*원?\s*[~\-~～]\s*\d{3,4})",
        r"(면접\s*후\s*결정)",
        r"(협의\s*가능)",
        r"(수준에\s*따라)",
        r"(내귀에\s*따름|내규에\s*따름|회사\s*내규)",
    ]
    for pat in patterns:
        m = re.search(pat, t, re.I | re.M)
        if m:
            s = (m.group(1) if m.lastindex else m.group(0)).strip()
            return s[:200] if len(s) > 200 else s
    return None


def parse_work_location_from_text(text: str) -> str | None:
    if not text:
        return None
    t = text[:12000]
    patterns = [
        r"(?:근무지|근무\s*장소|근무지역|근무\s*지역|채용\s*지역|근무\s*위치)\s*[:：]?\s*([^\n]{1,100})",
        r"(?:근무지)\s*[:：]\s*([^\n]{1,100})",
    ]
    for pat in patterns:
        m = re.search(pat, t, re.I)
        if m:
            s = m.group(1).strip()
            if len(s) >= 2:
                return s[:120]
    return None


def parse_career_from_text(text: str) -> dict[str, Any]:
    """신입 / 경력무관 / 경력 n년 이상 등 (휴리스틱)."""
    if not text:
        return {"type": "unknown", "min_years": None, "raw": None}
    t = text[:8000]
    if re.search(r"경력\s*무관|경력무관", t):
        return {"type": "경력무관", "min_years": None, "raw": "경력무관"}
    m = re.search(
        r"(?:경력|경험)\s*(\d+)\s*년\s*이상|(\d+)\s*년\s*이상\s*(?:의\s*)?(?:경력|경험)|"
        r"(?:최소|최소\s*경력)\s*(\d+)\s*년",
        t,
    )
    if m:
        years = int(next(g for g in m.groups() if g is not None))
        return {"type": "경력", "min_years": years, "raw": m.group(0)[:100]}
    m2 = re.search(r"경력\s*(\d+)\s*[~\-~～]\s*(\d+)\s*년", t)
    if m2:
        y = int(m2.group(1))
        return {"type": "경력", "min_years": y, "raw": m2.group(0)[:100]}
    if re.search(
        r"신입\s*(?:지원|가능|모집|채용)|모집\s*신입|신입\s*우대|신입\s*환영",
        t,
    ) or (
        re.search(r"(?<![\w가-힣])신입(?![\w가-힣])", t[:1200])
        and not re.search(r"\d+\s*년\s*이상", t[:1200])
    ):
        return {"type": "신입", "min_years": 0, "raw": "신입"}
    return {"type": "unknown", "min_years": None, "raw": None}


def enrich_employment_fields(
    meta: dict[str, Any],
    full_text: str,
    *,
    listing_location: str | None,
) -> dict[str, Any]:
    text = full_text or ""
    wl = parse_work_location_from_text(text)
    if not wl and listing_location and listing_location.strip():
        wl = listing_location.strip()
    meta["work_location"] = wl[:200] if wl else None
    meta["company_location_hint"] = (listing_location or "").strip() or None
    sal = parse_salary_from_text(text)
    meta["salary"] = sal if sal else DEFAULT_SALARY_LABEL
    meta["career"] = parse_career_from_text(text)
    meta["extraction_version"] = 2
    return meta


def normalize_job_metadata(raw: dict[str, Any] | None, *, job_location: str | None = None) -> dict[str, Any]:
    """구버전 메타·부분 누락 필드를 최신 스키마로 맞춤."""
    m = dict(raw) if isinstance(raw, dict) else {}
    base = empty_job_metadata()
    for k, v in base.items():
        if k not in m or m[k] is None:
            m[k] = v
    if not isinstance(m.get("career"), dict):
        m["career"] = {"type": "unknown", "min_years": None, "raw": None}
    if m.get("salary") in (None, ""):
        m["salary"] = DEFAULT_SALARY_LABEL
    if not m.get("work_location") and job_location:
        m["work_location"] = job_location.strip()[:200]
    return m


def merged_job_metadata(job: Job) -> dict[str, Any]:
    return normalize_job_metadata(job.job_metadata, job_location=job.location)


def extract_posting_metadata(
    raw: str,
    *,
    company: str | None = None,
    listing_location: str | None = None,
) -> dict[str, Any]:
    """목록 단계 텍스트·상세 본문·OCR 합쳐진 문자열에서 섹션별 bullet을 분리합니다."""
    text = raw.strip() if raw else ""
    meta = empty_job_metadata(company)
    if not text:
        return enrich_employment_fields(meta, "", listing_location=listing_location)

    lines = text.splitlines()
    core_keys = frozenset({"requirements", "preferred", "responsibilities"})
    current: str = "listing_hints"
    other_key: str | None = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        matched_bucket: str | None = None
        for bucket, pat in _SECTION_RULES:
            if pat.match(line):
                matched_bucket = bucket
                break
        if matched_bucket:
            if matched_bucket in core_keys:
                current = matched_bucket
                other_key = None
            else:
                current = "other"
                other_key = matched_bucket
            continue

        if len(line) < 2:
            continue

        if current in core_keys:
            meta[current].append(line)
        elif current == "other" and other_key:
            meta["other_sections"].setdefault(other_key, []).append(line)
        elif current == "other":
            k = _slug_header(line.split(":", 1)[0] if ":" in line else line)
            meta["other_sections"].setdefault(k, []).append(line)
        else:
            meta["listing_hints"].append(line)

    return enrich_employment_fields(meta, text, listing_location=listing_location)


def metadata_text_for_skills(job: Job) -> str:
    """스킬 추출·임베딩용 짧은 텍스트 (원본 description 미사용)."""
    parts: list[str] = [job.title or "", job.company or ""]
    m = merged_job_metadata(job)
    if isinstance(m, dict):
        for key in ("responsibilities", "requirements", "preferred"):
            for line in m.get(key) or []:
                if isinstance(line, str) and line.strip():
                    parts.append(line.strip())
        for line in m.get("listing_hints") or []:
            if isinstance(line, str) and line.strip():
                parts.append(line.strip())
        other = m.get("other_sections")
        if isinstance(other, dict):
            for _sec, lines in other.items():
                if isinstance(lines, list):
                    for line in lines:
                        if isinstance(line, str) and line.strip():
                            parts.append(line.strip())
    cr = m.get("career")
    if isinstance(cr, dict) and cr.get("type") and cr["type"] != "unknown":
        parts.append(
            f"경력: {cr['type']}"
            + (f" ({cr.get('min_years')}년 이상)" if cr.get("min_years") is not None else "")
        )
    if m.get("salary"):
        parts.append(f"연봉: {m['salary']}")
    if m.get("work_location"):
        parts.append(f"근무지: {m['work_location']}")
    return "\n".join(p for p in parts if p)


def rag_document_text(job: Job) -> str:
    """추후 벡터 DB/RAG 인덱싱용 단일 문서 문자열."""
    m = merged_job_metadata(job)
    lines = [
        f"기업: {job.company}",
        f"포지션: {job.title}",
        f"직군: {job.category}",
    ]
    if m.get("work_location"):
        lines.append(f"근무지: {m['work_location']}")
    if m.get("salary"):
        lines.append(f"연봉: {m['salary']}")
    cr = m.get("career")
    if isinstance(cr, dict) and cr.get("type") and cr["type"] != "unknown":
        lines.append(
            f"경력: {cr['type']}"
            + (f" (최소 {cr.get('min_years')}년)" if cr.get("min_years") is not None else "")
        )
    if job.source_url:
        lines.append(f"원본URL: {job.source_url}")

    def block(title: str, items: list) -> None:
        if not items:
            return
        lines.append(f"\n[{title}]")
        for it in items:
            if isinstance(it, str) and it.strip():
                lines.append(f"- {it.strip()}")

    block("담당업무", m.get("responsibilities") or [])
    block("요구사항", m.get("requirements") or [])
    block("우대사항", m.get("preferred") or [])
    block("목록_힌트", m.get("listing_hints") or [])
    other = m.get("other_sections") or {}
    if isinstance(other, dict):
        for sec, items in sorted(other.items()):
            block(sec, items if isinstance(items, list) else [])
    return "\n".join(lines).strip()
