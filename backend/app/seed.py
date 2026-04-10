"""MVP 더미 데이터 적재."""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import (
    ExtractedSkill,
    Job,
    Recommendation,
    ScraperRunLog,
    TrendKeyword,
)
from app.services.gap_analysis import refresh_demand_supply_summary
from app.services.posting_metadata import extract_posting_metadata, metadata_text_for_skills
from app.services.skill_normalize import extract_skills_from_text
from app.config import settings
from app.services.ai_recommend import ensure_recommendations


CATEGORY_LABEL = {
    "data_analyst": "데이터 분석가",
    "ai_engineer": "AI 엔지니어",
    "backend_developer": "백엔드 개발자",
}

JOB_TEMPLATES: list[tuple[str, str, str]] = [
    (
        "saramin",
        "[데이터] 리테일 데이터 분석가 채용",
        "python pandas sql tableau 경험자 우대. 엑셀 실무 필수. 머신러닝 기초 이해.",
    ),
    (
        "jobkorea",
        "금융권 데이터 분석 / 리스크 모델링",
        "SQL, Python, Power BI. 딥러닝은 우대. AWS 환경 경험.",
    ),
    (
        "wanted",
        "그로스 데이터 애널리스트",
        "Python, SQL, Excel, Amplitude 유사 툴. A/B 테스트 경험.",
    ),
    (
        "saramin",
        "AI 엔지니어 (추천/검색)",
        "pytorch tensorflow 딥러닝 LLM 파인튜닝. Python, Docker, Kubernetes.",
    ),
    (
        "jobkorea",
        "생성형 AI 서비스 백엔드",
        "FastAPI, AWS, 머신러닝 배포 경험. 생성형 AI 관심사.",
    ),
    (
        "wanted",
        "ML Ops 엔지니어",
        "Docker, Kubernetes, ETL 파이프라인. Python.",
    ),
    (
        "saramin",
        "백엔드 개발자 (Java/Spring)",
        "Spring, SQL, Docker. AWS 운영. Git, Jira 협업.",
    ),
    (
        "jobkorea",
        "백엔드 (Python/FastAPI)",
        "FastAPI, SQL, Redis. AWS. Kubernetes 우대.",
    ),
    (
        "wanted",
        "플랫폼 백엔드 엔지니어",
        "Spring 또는 FastAPI. Docker, Kubernetes. SQL 튜닝.",
    ),
]


def _assign_category(idx: int) -> str:
    if idx % 3 == 0:
        return "data_analyst"
    if idx % 3 == 1:
        return "ai_engineer"
    return "backend_developer"


def seed_if_empty(db: Session) -> None:
    if not settings.seed_demo_on_empty:
        return
    if db.query(Job).first():
        return

    random.seed(42)
    base = date.today() - timedelta(days=45)

    for i in range(36):
        src, title, desc_extra = JOB_TEMPLATES[i % len(JOB_TEMPLATES)]
        cat = _assign_category(i)
        title_full = f"{title} ({i+1})"
        company = random.choice(["테크코프", "핀테크A", "이커머스B", "스타트업C", "클라우드D"])
        raw_demo = f"{desc_extra}\n\n주요 업무: 데이터 파이프라인 및 협업 툴 활용."
        loc = random.choice(["서울", "판교", "강남", "원격"])
        meta = extract_posting_metadata(raw_demo, company=company, listing_location=loc)
        j = Job(
            source=src,
            external_id=f"demo-seed-{i}",
            search_keyword=None,
            title=title_full,
            company=company,
            category=cat,
            description="",
            job_metadata=meta,
            location=loc,
            posted_at=base + timedelta(days=i % 30),
            collected_at=datetime.utcnow(),
        )
        db.add(j)
    db.commit()

    jobs = db.query(Job).all()
    for j in jobs:
        for raw, norm, group, conf in extract_skills_from_text(
            metadata_text_for_skills(j) + " " + j.title
        ):
            db.add(
                ExtractedSkill(
                    job_id=j.id,
                    raw_skill=raw,
                    normalized_skill=norm,
                    skill_group=group,
                    confidence=conf,
                )
            )
    db.commit()

    # 트렌드: 직군별 키워드 × 주간 (12주)
    keywords = [
        "Python",
        "SQL",
        "Excel",
        "Tableau",
        "Power BI",
        "Pandas",
        "머신러닝",
        "딥러닝",
        "ETL",
        "Docker",
        "FastAPI",
        "Spring",
        "PyTorch",
        "TensorFlow",
        "Kubernetes",
        "AWS",
        "생성형 AI",
    ]
    for cat in CATEGORY_LABEL:
        for w in range(12):
            d = date.today() - timedelta(weeks=11 - w)
            for kw in keywords:
                # 직군별로 관심도 패턴 다르게
                base_i = 30 + random.random() * 40
                if cat == "ai_engineer" and kw in ("생성형 AI", "딥러닝", "PyTorch"):
                    base_i += 20
                if cat == "data_analyst" and kw in ("Excel", "Tableau", "Power BI"):
                    base_i += 15
                if cat == "backend_developer" and kw in ("Spring", "Docker", "Kubernetes"):
                    base_i += 15
                if kw == "생성형 AI" and cat != "ai_engineer":
                    base_i += 25  # 과포화 시나리오: 관심만 높음
                noise = random.uniform(-8, 8)
                score = max(5, min(100, base_i + noise + w * 0.8))
                db.add(
                    TrendKeyword(
                        keyword=kw,
                        category=cat,
                        date=d,
                        interest_score=round(score, 2),
                        source="demo_trend",
                    )
                )
    db.commit()

    for cat in CATEGORY_LABEL:
        refresh_demand_supply_summary(db, cat)
        db.query(Recommendation).filter(Recommendation.category == cat).delete()
        db.commit()
        ensure_recommendations(db, cat, use_llm=False)

    db.add(
        ScraperRunLog(
            source="saramin",
            run_started_at=datetime.utcnow() - timedelta(hours=2),
            run_finished_at=datetime.utcnow() - timedelta(hours=2) + timedelta(minutes=3),
            status="success",
            jobs_fetched=120,
            jobs_new=14,
            error_message=None,
            meta={"macro_version": "demo-1", "query": "데이터/AI/백엔드"},
        )
    )
    db.add(
        ScraperRunLog(
            source="jobkorea",
            run_started_at=datetime.utcnow() - timedelta(days=1),
            run_finished_at=datetime.utcnow() - timedelta(days=1) + timedelta(minutes=5),
            status="success",
            jobs_fetched=95,
            jobs_new=8,
            meta={"macro_version": "demo-1"},
        )
    )
    db.commit()
