"""이력서 텍스트 → 공고 수집용 검색 키워드·직군(3종) 적합도·확장 역할 안내."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.seed import CATEGORY_LABEL
from app.services.resume_match import extract_resume_skills, preparation_insights

SLUGS = list(CATEGORY_LABEL.keys())

# 직군별 사람인/잡코리아 검색에 쓰기 좋은 한국어 보강
_CATEGORY_SEARCH_EXTRAS: dict[str, list[str]] = {
    "data_analyst": ["데이터 분석", "데이터분석가", "BI"],
    "ai_engineer": ["AI 엔지니어", "머신러닝", "딥러닝"],
    "backend_developer": ["백엔드 개발", "서버 개발", "API"],
}

# (키워드 하위문자열, 가중, 직군, 이유 라벨)
_TEXT_SIGNALS: list[tuple[str, float, str, str]] = [
    ("데이터 분석", 3.0, "data_analyst", "데이터 분석"),
    ("데이터분석", 3.0, "data_analyst", "데이터분석"),
    ("애널리스트", 2.0, "data_analyst", "애널리스트"),
    ("리포트", 1.2, "data_analyst", "리포트"),
    ("대시보드", 2.0, "data_analyst", "대시보드"),
    ("지표", 1.2, "data_analyst", "지표"),
    ("tableau", 2.0, "data_analyst", "Tableau"),
    ("태블로", 2.0, "data_analyst", "태블로"),
    ("power bi", 2.0, "data_analyst", "Power BI"),
    ("가설", 1.0, "data_analyst", "가설검증"),
    ("머신러닝", 3.0, "ai_engineer", "머신러닝"),
    ("딥러닝", 3.0, "ai_engineer", "딥러닝"),
    ("llm", 2.5, "ai_engineer", "LLM"),
    ("생성형", 2.0, "ai_engineer", "생성형 AI"),
    ("파인튜닝", 2.0, "ai_engineer", "파인튜닝"),
    ("추천 시스템", 2.0, "ai_engineer", "추천"),
    ("cv ", 1.0, "ai_engineer", "비전"),
    ("nlp", 1.5, "ai_engineer", "NLP"),
    ("백엔드", 2.5, "backend_developer", "백엔드"),
    ("서버 개발", 2.0, "backend_developer", "서버"),
    ("api", 1.5, "backend_developer", "API"),
    ("msa", 1.5, "backend_developer", "MSA"),
    ("마이크로서비스", 1.5, "backend_developer", "MSA"),
    ("스프링", 2.0, "backend_developer", "Spring"),
    ("spring", 2.0, "backend_developer", "Spring"),
    ("fastapi", 2.0, "backend_developer", "FastAPI"),
    ("redis", 1.0, "backend_developer", "Redis"),
    ("kafka", 1.0, "backend_developer", "Kafka"),
]

_NORM_SIGNALS: list[tuple[str, float, str, str]] = [
    ("SQL", 2.0, "data_analyst", "SQL"),
    ("Excel", 1.2, "data_analyst", "Excel"),
    ("Tableau", 2.0, "data_analyst", "Tableau"),
    ("Power BI", 2.0, "data_analyst", "Power BI"),
    ("Pandas", 1.5, "data_analyst", "Pandas"),
    ("Python", 0.8, "data_analyst", "Python"),
    ("Python", 0.8, "ai_engineer", "Python"),
    ("Python", 1.0, "backend_developer", "Python"),
    ("PyTorch", 3.0, "ai_engineer", "PyTorch"),
    ("TensorFlow", 3.0, "ai_engineer", "TensorFlow"),
    ("머신러닝", 2.5, "ai_engineer", "머신러닝"),
    ("딥러닝", 2.5, "ai_engineer", "딥러닝"),
    ("LLM", 2.5, "ai_engineer", "LLM"),
    ("생성형 AI", 2.0, "ai_engineer", "생성형 AI"),
    ("Spring", 2.5, "backend_developer", "Spring"),
    ("FastAPI", 2.5, "backend_developer", "FastAPI"),
    ("Docker", 1.0, "backend_developer", "Docker"),
    ("Kubernetes", 1.2, "backend_developer", "Kubernetes"),
    ("AWS", 1.0, "backend_developer", "AWS"),
    ("Git", 0.5, "backend_developer", "Git"),
]

_GROUP_BOOST: dict[str, tuple[str, float]] = {
    "data_tool": ("data_analyst", 1.5),
    "ai_ml": ("ai_engineer", 2.5),
    "framework": ("backend_developer", 1.2),
    "infra": ("backend_developer", 1.0),
}

# 3가지 직군 슬롯에 없는 역할 → 검색·직군 선택 가이드
_EXTRA_ROLE_PATTERNS: list[tuple[tuple[str, ...], str, str]] = [
    (
        ("프론트", "frontend", "react", "vue", "angular", "next.js", "nextjs"),
        "프론트엔드",
        "프론트엔드 전용 직군 슬롯은 없습니다. 검색 키워드에 React·프론트엔드를 넣고, 저장 직군은 `백엔드 개발자`와 번갈아 수집하거나 키워드만으로 폭을 넓혀 보세요.",
    ),
    (
        ("데이터 엔지니어", "data engineer", "etl", "spark", "airflow", "dbt"),
        "데이터 엔지니어링",
        "데이터 파이프라인·ETL 성향은 `데이터 분석가` 또는 `백엔드 개발자` 중 하나를 고르고, 검색어에 Spark·ETL·파이프라인을 포함해 보세요.",
    ),
    (
        ("devops", "sre", "플랫폼 엔지니어"),
        "DevOps / SRE",
        "인프라·자동화 비중이 크면 `백엔드 개발자` 직군으로 저장하고 Kubernetes·CI/CD·모니터링 키워드를 추가하세요.",
    ),
    (
        ("mlops", "ml ops", "모델 배포"),
        "MLOps",
        "모델 운영·배포는 `AI 엔지니어`에 가깝습니다. Docker·Kubernetes와 함께 검색 키워드를 구성해 보세요.",
    ),
    (
        ("기획", "product owner", "po", "프로덕트 매니저", "서비스 기획"),
        "기획·PM",
        "개발 직군 슬롯과는 다릅니다. 기술 스택 키워드로 공고를 모을 때는 팀 내 협업 키워드를 보조로 넣는 정도를 권합니다.",
    ),
    (
        ("보안", "security", "앱센", "모의해킹"),
        "보안",
        "보안 직무는 현재 3개 직군에 직접 매핑되지 않습니다. `백엔드 개발자`로 저장 후 보안·취약점 키워드로 검색해 보세요.",
    ),
    (
        ("qa", "테스트 자동화", "품질"),
        "QA",
        "QA 전용 슬롯은 없습니다. `백엔드 개발자`와 키워드에 QA·테스트 자동화를 함께 넣는 방식을 권합니다.",
    ),
]


def _score_categories(
    text_lower: str,
    norms: set[str],
    groups: set[str],
    years: int | None,
    hint: str | None,
) -> dict[str, tuple[float, list[str]]]:
    acc: dict[str, tuple[float, list[str]]] = {s: (0.0, []) for s in SLUGS}

    for sub, w, slug, label in _TEXT_SIGNALS:
        if sub in text_lower:
            sc, rs = acc[slug]
            acc[slug] = (sc + w, rs + [label])

    for norm, w, slug, label in _NORM_SIGNALS:
        if norm in norms:
            sc, rs = acc[slug]
            acc[slug] = (sc + w, rs + [f"{norm}(스킬)"])

    for g, (slug, w) in _GROUP_BOOST.items():
        if g in groups:
            sc, rs = acc[slug]
            acc[slug] = (sc + w, rs + [f"역량군:{g}"])

    if years is not None:
        if years >= 7:
            for slug in SLUGS:
                sc, rs = acc[slug]
                acc[slug] = (sc + 0.4, rs + ["경력 7년+"])
        elif years >= 3:
            for slug in SLUGS:
                sc, rs = acc[slug]
                acc[slug] = (sc + 0.2, rs + ["경력 3년+"])

    if hint and hint in CATEGORY_LABEL:
        sc, rs = acc[hint]
        acc[hint] = (sc + 4.0, rs + ["분석 화면에서 선택한 직군 반영"])

    if all(acc[s][0] == 0 for s in SLUGS):
        for slug in SLUGS:
            acc[slug] = (1.0, ["이력서 신호 약함 — 기본 균등"])

    return acc


def _primary_and_ranked(
    acc: dict[str, tuple[float, list[str]]],
) -> tuple[str, list[dict[str, Any]]]:
    ranked = sorted(acc.items(), key=lambda x: -x[1][0])
    primary = ranked[0][0]
    out: list[dict[str, Any]] = []
    for slug, (score, reasons) in ranked:
        out.append(
            {
                "slug": slug,
                "label_ko": CATEGORY_LABEL[slug],
                "score": round(score, 2),
                "reasons": reasons[:12],
            }
        )
    return primary, out


def _expansion_notes(text_lower: str) -> list[str]:
    notes: list[str] = []
    for patterns, title, msg in _EXTRA_ROLE_PATTERNS:
        if any(p in text_lower for p in patterns):
            notes.append(f"【{title}】 {msg}")
    return notes[:8]


def _merge_search_keywords(
    norms_ordered: list[str],
    primary: str,
    ranked: list[dict[str, Any]],
    years: int | None,
) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []

    def add(x: str) -> None:
        t = x.strip()
        if not t or t.lower() in seen:
            return
        seen.add(t.lower())
        out.append(t)

    for n in norms_ordered:
        add(n)

    for kw in _CATEGORY_SEARCH_EXTRAS[primary]:
        add(kw)

    if len(ranked) >= 2:
        top_s, sec_s = ranked[0]["score"], ranked[1]["score"]
        if sec_s >= 2.0 and (top_s - sec_s) <= 5.0:
            sec = ranked[1]["slug"]
            if sec != primary:
                add(_CATEGORY_SEARCH_EXTRAS[sec][0])

    if years is not None:
        if years >= 7:
            add("시니어")
        elif years >= 5:
            add("경력")
        elif years <= 2:
            add("주니어")

    return out[:16]


def build_collect_suggestions(
    db: Session,
    resume_text: str,
    career_summary: str | None,
    analysis_category_hint: str | None,
    career_years_override: int | None = None,
) -> dict[str, Any]:
    parts = [p.strip() for p in (resume_text or "", career_summary or "") if p and p.strip()]
    full = "\n".join(parts)
    skill_tuples = extract_resume_skills(full)
    norms_ordered = [s[0] for s in skill_tuples]
    norms = set(norms_ordered)
    groups = {s[1] for s in skill_tuples}

    from app.services.resume_dashboard import estimate_career_years

    years = career_years_override if career_years_override is not None else estimate_career_years(full)

    hint = (analysis_category_hint or "").strip() or None
    if hint == "all":
        hint = None

    text_lower = full.lower()
    acc = _score_categories(text_lower, norms, groups, years, hint)
    primary, ranked = _primary_and_ranked(acc)
    keywords = _merge_search_keywords(norms_ordered, primary, ranked, years)
    notes = _expansion_notes(text_lower)

    gap_keywords: list[str] = []
    prep = preparation_insights(db, resume_text, career_summary, primary)
    for g in prep.get("gap_skills") or []:
        if g not in keywords and g.lower() not in {k.lower() for k in keywords}:
            gap_keywords.append(g)
        if len(gap_keywords) >= 6:
            break

    if not keywords:
        keywords = _CATEGORY_SEARCH_EXTRAS[primary][:]

    return {
        "search_keywords": keywords,
        "primary_category_slug": primary,
        "primary_category_label_ko": CATEGORY_LABEL[primary],
        "category_ranked": ranked,
        "role_expansion_notes": notes,
        "optional_gap_keywords": gap_keywords,
    }
