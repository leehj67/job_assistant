"""대시보드 ApplicantProfile → 컨설턴트 학생 반영 시 이름·직군 추론, 필드 중복 제거, 이력 중복 학생 방지."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from sqlalchemy.orm import Session

from app.models import ApplicantProfile, ConsultantStudent
from app.seed import CATEGORY_LABEL
from app.services.collect_suggestions import build_collect_suggestions

_PLACEHOLDER_NAMES = frozenset({"대시보드에서 가져옴", "지원자"})

# 이력서 양식에서 단독 줄·란 제목으로 자주 나오는 단어(이름으로 오인 방지)
_INVALID_DISPLAY_NAME_TOKENS = frozenset(
    {
        "주소",
        "성명",
        "이름",
        "연락",
        "연락처",
        "휴대폰",
        "전화",
        "핸드폰",
        "이메일",
        "이메일주소",
        "e메일",
        "팩스",
        "학력",
        "학벌",
        "경력",
        "경력사항",
        "자격",
        "자격증",
        "면허",
        "스킬",
        "기술",
        "기술스택",
        "소개",
        "자기소개",
        "프로필",
        "인적",
        "인적사항",
        "사진",
        "병역",
        "보훈",
        "특기",
        "취미",
        "생년월일",
        "국적",
        "영문명",
        "한글명",
        "지원분야",
        "희망직무",
        "희망연봉",
        "직무",
        "담당업무",
        "제목",
        "내용",
        "기본정보",
        "개인정보",
    }
)


def normalize_ws(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def sanitize_display_name_candidate(name: str | None) -> str | None:
    """란 제목·빈 값이면 None. 그 외는 길이 제한만."""
    t = normalize_ws(name)
    if not t:
        return None
    if t in _INVALID_DISPLAY_NAME_TOKENS:
        return None
    if t in _PLACEHOLDER_NAMES:
        return None
    # "주소:" 처럼 콜론만 붙은 라벨
    t2 = re.sub(r"\s*[：:]\s*$", "", t)
    if t2 in _INVALID_DISPLAY_NAME_TOKENS:
        return None
    return t[:128]


def resume_fingerprint(text: str | None) -> str:
    n = normalize_ws(text)
    if not n:
        return ""
    return hashlib.sha256(n.encode("utf-8")).hexdigest()


def combined_content_fingerprint(resume: str | None, summary: str | None) -> str:
    parts = [normalize_ws(x) for x in (resume, summary) if normalize_ws(x)]
    return resume_fingerprint("\n\n".join(parts)) if parts else ""


_SKIP_HEAD_LINE = re.compile(
    r"^\s*(이력서|Resume|CV|Curriculum\s*Vitae|경력기술서|자기소개서)\s*$",
    re.IGNORECASE,
)

_NAME_LINE_PATTERNS = [
    re.compile(r"(?:성명|이름)\s*[：:]\s*([가-힣·ㆍ]{2,24})"),
    re.compile(
        r"(?:Name|NAME)\s*[：:]\s*([A-Za-z가-힣][A-Za-z가-힣·\s]{1,38})(?:\s*$|\s*[|｜])"
    ),
    re.compile(r"(?m)^([가-힣]{2,6})\s*[\(（,，]\s*\d{4}"),  # 김철수 (1990
]

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+82[-\s]?)?0?1[016789][-\s]?\d{3,4}[-\s]?\d{4}")


def _extract_email(text: str) -> str | None:
    m = _EMAIL_RE.search(text)
    return m.group(0) if m else None


def _extract_phone(text: str) -> str | None:
    m = _PHONE_RE.search(text)
    return re.sub(r"\s+", "", m.group(0)) if m else None


def is_auto_generated_display_name(name: str | None) -> bool:
    n = (name or "").strip()
    if not n:
        return True
    if n in _PLACEHOLDER_NAMES:
        return True
    if n.startswith("이력서 지원자"):
        return True
    if sanitize_display_name_candidate(n) is None:
        return True
    return False


def guess_display_name(
    profile: ApplicantProfile,
    resume_text: str | None,
    career_summary: str | None,
    explicit_override: str | None,
) -> str:
    o = sanitize_display_name_candidate(explicit_override)
    if o:
        return o

    pdn = sanitize_display_name_candidate(profile.display_name)
    if pdn:
        return pdn

    head = (resume_text or "")[:8000]
    for pat in _NAME_LINE_PATTERNS:
        m = pat.search(head)
        if m:
            cand = m.group(1).strip()
            if 2 <= len(cand) <= 40 and not re.search(r"\d{5,}", cand):
                ok = sanitize_display_name_candidate(cand)
                if ok:
                    return ok

    for raw in head.splitlines()[:35]:
        line = raw.strip()
        if not line or len(line) > 18:
            continue
        if _SKIP_HEAD_LINE.match(line):
            continue
        if re.fullmatch(r"[가-힣]{2,6}", line):
            ok = sanitize_display_name_candidate(line)
            if ok:
                return ok

    em = _extract_email(head)
    if em:
        local, _, _ = em.partition("@")
        if 2 <= len(local) <= 48 and re.match(r"^[A-Za-z가-힣._-]+$", local):
            return local[:128]

    cs = normalize_ws(career_summary)
    if cs and len(cs) <= 40 and not re.search(r"[.!?。！？]{2,}", cs):
        return cs[:128]

    fp = combined_content_fingerprint(resume_text, career_summary)[:10]
    return f"이력서 지원자 ({fp})" if fp else "이력서 지원자"


def dedupe_resume_and_summary(
    resume: str | None, summary: str | None
) -> tuple[str | None, str | None]:
    r = (resume or "").strip() or None
    s = (summary or "").strip() or None
    if not r:
        return None, s
    if not s:
        return r, None
    nr, ns = normalize_ws(r), normalize_ws(s)
    if nr == ns:
        return r, None
    if len(ns) >= 12 and ns in nr:
        return r, None
    if len(nr) >= 12 and nr in ns and len(s) <= len(r) * 1.05:
        return r, None
    return r, s


def build_import_memo_lines(profile: ApplicantProfile, tag: str) -> list[str]:
    lines: list[str] = []
    if tag:
        lines.append(tag)
    if profile.career_years is not None:
        lines.append(f"경력 추정(대시보드): 약 {profile.career_years}년")
    urls = profile.portfolio_urls
    if isinstance(urls, list):
        for u in urls:
            if isinstance(u, str) and (t := u.strip()):
                lines.append(f"포트폴리오·링크: {t}")
    seen: set[str] = set()
    out: list[str] = []
    for L in lines:
        if L not in seen:
            seen.add(L)
            out.append(L)
    return out


def merge_memo_lines(existing: str | None, new_lines: list[str]) -> str | None:
    old = [x.strip() for x in (existing or "").splitlines() if x.strip()]
    seen = set(old)
    for L in new_lines:
        if L not in seen:
            seen.add(L)
            old.append(L)
    return "\n".join(old) if old else None


def infer_target_category_slug(
    db: Session,
    resume_text: str | None,
    career_summary: str | None,
    career_years: int | None,
    prefs: dict[str, Any] | None,
) -> str:
    hint: str | None = None
    if isinstance(prefs, dict):
        raw = prefs.get("last_dashboard_category") or prefs.get("dashboard_category")
        if isinstance(raw, str):
            hint = raw.strip() or None
            if hint == "all" or hint not in CATEGORY_LABEL:
                hint = None
    sug = build_collect_suggestions(
        db,
        resume_text or "",
        career_summary,
        hint,
        career_years_override=career_years,
    )
    return str(sug["primary_category_slug"])


def find_duplicate_student_by_content(
    db: Session, fingerprint: str, exclude_id: int | None
) -> ConsultantStudent | None:
    if not fingerprint:
        return None
    q = db.query(ConsultantStudent)
    if exclude_id is not None:
        q = q.filter(ConsultantStudent.id != exclude_id)
    for row in q.all():
        if combined_content_fingerprint(row.resume_text, row.career_summary) == fingerprint:
            return row
    return None


def apply_contact_from_resume(
    student: ConsultantStudent, resume_text: str | None, only_if_empty: bool
) -> None:
    rt = resume_text or ""
    email = _extract_email(rt[:16000])
    phone = _extract_phone(rt[:16000])
    if email:
        if not only_if_empty or not (student.email or "").strip():
            student.email = email[:256]
    if phone:
        if not only_if_empty or not (student.phone or "").strip():
            student.phone = phone[:64]


def summary_not_redundant_vs_resume(candidate: str, resume: str | None) -> bool:
    """경력 요약이 이력서 본문과 사실상 동일하면 False."""
    if not candidate.strip():
        return False
    if not resume or not resume.strip():
        return True
    nc, nr = normalize_ws(candidate), normalize_ws(resume)
    if not nc:
        return False
    if nc == nr:
        return False
    if len(nc) >= 15 and nc in nr:
        return False
    return True


def safe_contact_email(s: str | None) -> str | None:
    t = (s or "").strip()
    if not t or "@" not in t or len(t) < 5:
        return None
    return t[:256]


def safe_contact_phone(s: str | None) -> str | None:
    t = (s or "").strip()
    if not t:
        return None
    digits = re.sub(r"\D", "", t)
    if len(digits) < 9 or len(digits) > 16:
        return None
    return t[:64]


def safe_school(s: str | None) -> str | None:
    t = (s or "").strip()
    if not t:
        return None
    return t[:256]


def choose_final_career_summary(
    llm_summary: str | None,
    heuristic_summary: str | None,
    resume: str | None,
) -> str | None:
    c = (llm_summary or "").strip()
    if c and summary_not_redundant_vs_resume(c, resume):
        return c[:12000]
    h = (heuristic_summary or "").strip() or None
    return h


def extend_memo_with_llm_lines(
    base_lines: list[str],
    llm_lines: list[str] | None,
) -> list[str]:
    seen = set(base_lines)
    out = list(base_lines)
    if not llm_lines:
        return out
    for line in llm_lines:
        t = (line or "").strip()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def resolve_display_name_for_new(
    profile: ApplicantProfile,
    llm_name: str | None,
    resume: str | None,
    summary: str | None,
    explicit_override: str | None,
) -> str:
    o = sanitize_display_name_candidate(explicit_override)
    if o:
        return o
    ln = sanitize_display_name_candidate(llm_name)
    if ln:
        return ln
    return guess_display_name(profile, resume, summary, None)


def resolve_display_name_for_update(
    profile: ApplicantProfile,
    llm_name: str | None,
    current_name: str,
    resume: str | None,
    summary: str | None,
) -> str:
    pdn = sanitize_display_name_candidate(profile.display_name)
    if pdn:
        return pdn
    ln = sanitize_display_name_candidate(llm_name)
    if ln:
        return ln
    if is_auto_generated_display_name(current_name):
        return guess_display_name(profile, resume, summary, None)
    cur_ok = sanitize_display_name_candidate(current_name)
    if cur_ok:
        return cur_ok
    return guess_display_name(profile, resume, summary, None)


def apply_llm_contact_to_student(
    student: ConsultantStudent,
    email: str | None,
    phone: str | None,
    school: str | None,
    only_if_empty: bool,
) -> None:
    em = safe_contact_email(email)
    if em and (not only_if_empty or not (student.email or "").strip()):
        student.email = em
    ph = safe_contact_phone(phone)
    if ph and (not only_if_empty or not (student.phone or "").strip()):
        student.phone = ph
    sc = safe_school(school)
    if sc and (not only_if_empty or not (student.school or "").strip()):
        student.school = sc
