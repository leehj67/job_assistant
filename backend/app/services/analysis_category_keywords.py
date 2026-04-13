"""사용자 정의 분석 직군: 검색 키워드 파싱 및 유사 검색어 확장(규칙 기반, LLM 없음)."""

from __future__ import annotations

import hashlib
import re
import unicodedata
# (하위문자열 트리거…), 확장 후보
_CLUSTERS: list[tuple[tuple[str, ...], list[str]]] = [
    (
        ("프론트", "frontend", "react", "vue", "angular", "next", "웹퍼블"),
        ["프론트엔드", "React", "Vue", "웹개발", "TypeScript", "SPA", "UI개발"],
    ),
    (
        ("백엔드", "backend", "서버", "api", "spring", "fastapi", "django"),
        ["백엔드개발", "REST API", "MSA", "Spring", "FastAPI", "서버개발"],
    ),
    (
        ("데이터 엔지", "data engineer", "etl", "spark", "airflow", "dbt"),
        ["데이터엔지니어", "ETL", "파이프라인", "Spark", "Airflow", "DW"],
    ),
    (
        ("devops", "sre", "인프라", "쿠버", "kubernetes", "terraform"),
        ["DevOps", "CI/CD", "Kubernetes", "AWS", "모니터링", "IaC"],
    ),
    (
        ("qa", "품질", "테스트 자동화", "셀레니움"),
        ["QA", "테스트엔지니어", "자동화테스트", "Jest", "Cypress"],
    ),
    (
        ("보안", "security", "모의해킹", "취약점"),
        ["보안엔지니어", "정보보안", "네트워크보안", "앱보안"],
    ),
    (
        ("ios", "swift", "안드로이드", "android", "kotlin", "flutter"),
        ["모바일개발", "앱개발", "iOS", "Android", "Flutter", "React Native"],
    ),
    (
        ("임베디드", "firmware", "rtos", "mcu"),
        ["펌웨어", "임베디드", "C언어", "하드웨어"],
    ),
]


def parse_keyword_line(s: str | None) -> list[str]:
    return [x.strip() for x in re.split(r"[,，\n]+", s or "") if x.strip()]


def expand_similar_keywords(primary: list[str], label: str) -> list[str]:
    """primary·label 텍스트에 반응해 추가 검색 후보(중복 제거)."""
    blob = " ".join(primary + [label]).lower()
    extra: list[str] = []
    for triggers, words in _CLUSTERS:
        if any(t in blob for t in triggers):
            extra.extend(words)
    # 라벨·키워드에서 짧은 토큰 변형
    for p in primary + [label]:
        t = p.strip()
        if len(t) >= 2 and t not in extra:
            if t.endswith("개발") and len(t) > 2:
                extra.append(t[:-2])
            elif len(t) >= 3 and not t.endswith("개발"):
                extra.append(f"{t} 개발")
    seen: set[str] = set()
    out: list[str] = []
    for x in extra:
        k = x.strip()
        if len(k) < 2:
            continue
        lk = k.lower()
        if lk in seen:
            continue
        if k.lower() in {p.lower() for p in primary} or k.lower() == label.strip().lower():
            continue
        seen.add(lk)
        out.append(k)
    return out[:14]


def auto_slug_for_label(db, label: str) -> str:
    """영문·숫자·밑줄 슬러그. 충돌 시 해시 접미."""
    from app.models import ConsultantCustomCategory
    from app.seed import CATEGORY_LABEL

    raw = unicodedata.normalize("NFKD", label)
    ascii_part = raw.encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^a-z0-9]+", "_", ascii_part.lower()).strip("_")[:18] or "role"
    h6 = hashlib.sha1(label.encode("utf-8")).hexdigest()[:6]
    cand = f"c_{base}_{h6}"[:62]
    n = 0
    while True:
        s = cand if n == 0 else f"c_{base}_{h6}_{n}"[:62]
        if s not in CATEGORY_LABEL and not db.query(ConsultantCustomCategory).filter(ConsultantCustomCategory.slug == s).first():
            return s
        n += 1
        if n > 50:
            return f"c_{hashlib.sha1((label + str(n)).encode()).hexdigest()[:16]}"[:62]
