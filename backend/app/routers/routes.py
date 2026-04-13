from __future__ import annotations

import asyncio
import json
import queue
import threading
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import (
    ApplicantProfile,
    ConsultantCustomCategory,
    DemandSupplySummary,
    ExtractedSkill,
    Job,
    Recommendation,
    ScraperRunLog,
    TrendKeyword,
)
from app.schemas import (
    AnalysisCategoryCreate,
    AnalyzedKeywordItemOut,
    ApplicantProfileOut,
    ApplicantProfileUpdate,
    CategoryItemOut,
    CollectedJobLink,
    CollectRequest,
    CollectResult,
    CollectSuggestRequest,
    CollectSuggestionsOut,
    ResumeInsightRequest,
    ResumeInsightOut,
    GapItemOut,
    JobOut,
    KeywordJobItemOut,
    KeywordAnalysisOut,
    JobCoverLetterOut,
    JobCoverLetterRequest,
    MatchJobsRequest,
    MatchJobsResponse,
    OverviewOut,
    PreparationInsightOut,
    RecommendationOut,
    ResumePdfAnalyzeOut,
    ScraperLogOut,
    SkillStatOut,
    TrendSeriesOut,
    TrendPointOut,
)
from app.services.analysis_category_keywords import (
    auto_slug_for_label,
    expand_similar_keywords,
    parse_keyword_line,
)
from app.services.category_scope import collect_category_slugs, merge_collect_keywords
from app.services.collection import collect_by_keywords, generate_collect_events
from app.services.job_links import resolve_job_listing_url
from app.services.application_draft import build_application_draft
from app.services.body_keyword_analysis import analyze_job_body_keywords
from app.services.posting_metadata import merged_job_metadata, rag_document_text
from app.services.llm_client import ollama_health
from app.services.gap_analysis import GAP_LABELS_KO, refresh_demand_supply_summary
from app.services.ai_recommend import interpretation_for_gap
from app.services.collect_suggestions import build_collect_suggestions
from app.services.resume_insight import build_resume_insight
from app.services.pdf_extract import extract_text_from_pdf_bytes
from app.services.resume_dashboard import build_resume_dashboard
from app.services.job_cover_letter import generate_job_cover_letter
from app.services.resume_match import match_jobs_for_resume, preparation_insights
from app.seed import CATEGORY_LABEL

MAX_PDF_BYTES = 12 * 1024 * 1024
MAX_RESUME_TEXT_IN_JSON = 200_000

router = APIRouter()


def _registered_post_paths(app) -> dict[str, bool]:
    """현재 프로세스에 실제로 올라간 주요 POST 라우트(진단용)."""
    want = {
        "/api/applicant/job-cover-letter": False,
        "/api/applicant/match-jobs": False,
    }
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if path in want and methods and "POST" in methods:
            want[path] = True
    return want


def _get_or_create_profile(db: Session) -> ApplicantProfile:
    p = db.query(ApplicantProfile).first()
    if not p:
        p = ApplicantProfile(
            resume_text="",
            career_summary="",
            portfolio_urls=[],
        )
        db.add(p)
        db.commit()
        db.refresh(p)
    return p


@router.get("/health")
def health(request: Request):
    posts = _registered_post_paths(request.app)
    out: dict = {"status": "ok", "routes_post": posts}
    if not posts.get("/api/applicant/job-cover-letter"):
        out["hint_ko"] = (
            "이 uvicorn 프로세스에 POST /api/applicant/job-cover-letter 가 없습니다. "
            "다른 터미널·다른 폴더에서 띄운 옛 백엔드가 포트를 잡고 있을 수 있습니다. "
            "8000 LISTEN 프로세스를 모두 종료한 뒤, 이 저장소의 backend 폴더에서 "
            "`python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload` 로 다시 실행하세요."
        )
    return out


@router.get("/categories", response_model=list[CategoryItemOut])
def categories(db: Session = Depends(get_db)):
    """기본 직군 + 사용자 등록 직군 + DB에만 존재하는 category(과거 수집)."""
    out: list[CategoryItemOut] = [
        CategoryItemOut(slug=k, label=v, is_builtin=True)
        for k, v in sorted(CATEGORY_LABEL.items(), key=lambda x: x[1])
    ]
    known = {c.slug for c in out}
    customs = (
        db.query(ConsultantCustomCategory).order_by(ConsultantCustomCategory.label_ko.asc()).all()
    )
    for row in customs:
        meta = row.meta if isinstance(row.meta, dict) else {}
        pk = [str(x) for x in (meta.get("primary_keywords") or []) if str(x).strip()]
        sk = [str(x) for x in (meta.get("similar_keywords") or []) if str(x).strip()]
        out.append(
            CategoryItemOut(
                slug=row.slug,
                label=row.label_ko,
                is_builtin=False,
                id=row.id,
                primary_keywords=pk,
                similar_keywords=sk,
            )
        )
        known.add(row.slug)
    for cat, n in (
        db.query(Job.category, func.count(Job.id)).group_by(Job.category).all()
    ):
        if not cat or cat in known:
            continue
        out.append(
            CategoryItemOut(
                slug=cat,
                label=f"{cat} (공고 {n}건)",
                is_builtin=False,
                orphan_job_bucket=True,
            )
        )
        known.add(cat)
    return out


@router.post("/applicant/analysis-categories", response_model=CategoryItemOut)
def post_applicant_analysis_category(body: AnalysisCategoryCreate, db: Session = Depends(get_db)):
    """분석 직군 추가: 라벨·검색 키워드를 저장하고 유사 검색어를 자동 부여합니다."""
    label = body.label.strip()
    primary = parse_keyword_line(body.keywords)
    if label not in primary:
        primary.insert(0, label)
    similar = expand_similar_keywords(primary, label)
    slug = auto_slug_for_label(db, label)
    row = ConsultantCustomCategory(
        slug=slug,
        label_ko=label,
        meta={"primary_keywords": primary, "similar_keywords": similar},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return CategoryItemOut(
        slug=row.slug,
        label=row.label_ko,
        is_builtin=False,
        id=row.id,
        primary_keywords=primary,
        similar_keywords=similar,
    )


@router.get("/overview", response_model=OverviewOut)
def overview(db: Session = Depends(get_db)):
    rows = db.query(Job.category, func.count(Job.id)).group_by(Job.category).all()
    job_counts = {c: n for c, n in rows}
    top_demand = sorted(job_counts.items(), key=lambda x: -x[1])[:5]

    recent_since = date.today() - timedelta(days=30)
    trend_rows = (
        db.query(TrendKeyword.keyword, func.avg(TrendKeyword.interest_score))
        .filter(TrendKeyword.date >= recent_since)
        .group_by(TrendKeyword.keyword)
        .all()
    )
    rising = sorted(trend_rows, key=lambda x: -x[1])[:8]
    rising_kw = [k for k, _ in rising]

    summaries = db.query(DemandSupplySummary).all()
    opp = [s.keyword for s in summaries if s.gap_type == "opportunity"][:8]
    over = [s.keyword for s in summaries if s.gap_type == "oversaturated"][:8]

    return OverviewOut(
        job_counts_by_category=job_counts,
        top_demand_categories=top_demand,
        rising_interest_keywords=rising_kw,
        opportunity_keywords=opp,
        oversaturated_keywords=over,
    )


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(
    category: str | None = None,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(Job)
    if category:
        q = q.filter(Job.category == category)
    return q.order_by(Job.id.desc()).limit(limit).all()


def _career_label(meta: dict) -> str | None:
    c = meta.get("career")
    if not isinstance(c, dict):
        return None
    t = c.get("type")
    y = c.get("min_years")
    if t == "경력" and y is not None:
        return f"경력 {y}년+"
    if isinstance(t, str) and t.strip():
        return t
    return None


@router.get("/keywords/analyzed", response_model=list[AnalyzedKeywordItemOut])
def analyzed_keywords(limit: int = Query(80, ge=1, le=300), db: Session = Depends(get_db)):
    rows = (
        db.query(
            ExtractedSkill.normalized_skill,
            func.count(func.distinct(ExtractedSkill.job_id)),
            func.count(),
        )
        .group_by(ExtractedSkill.normalized_skill)
        .order_by(func.count(func.distinct(ExtractedSkill.job_id)).desc(), func.count().desc())
        .limit(limit)
        .all()
    )
    return [
        AnalyzedKeywordItemOut(keyword=kw, jobs_count=int(jc), mentions_count=int(mc))
        for kw, jc, mc in rows
    ]


@router.get("/keywords/{keyword}/jobs", response_model=list[KeywordJobItemOut])
def jobs_by_keyword(
    keyword: str,
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Job)
        .join(ExtractedSkill, ExtractedSkill.job_id == Job.id)
        .filter(ExtractedSkill.normalized_skill == keyword)
        .distinct(Job.id)
        .order_by(Job.id.desc())
        .limit(limit)
        .all()
    )
    out: list[KeywordJobItemOut] = []
    for job in rows:
        meta = merged_job_metadata(job)
        out.append(
            KeywordJobItemOut(
                id=job.id,
                title=job.title,
                company=job.company,
                source=job.source,
                source_url=job.source_url,
                work_location=meta.get("work_location") or job.location,
                career_label=_career_label(meta),
            )
        )
    # 연차 > 근무지 > 최신순 정렬
    out.sort(
        key=lambda x: (
            x.career_label or "미정",
            x.work_location or "미정",
            -x.id,
        )
    )
    return out


@router.get("/jobs/{job_id}/rag-document")
def job_rag_document(job_id: int, db: Session = Depends(get_db)):
    """벡터 DB·RAG 인덱싱용 정규화 문서 (원본 HTML 미포함)."""
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "공고를 찾을 수 없습니다.")
    return {"job_id": job.id, "document": rag_document_text(job)}


@router.get("/jobs/{job_id}/keyword-analysis", response_model=KeywordAnalysisOut)
def job_keyword_analysis(job_id: int, db: Session = Depends(get_db)):
    """공고 메타 본문에서 기술 키워드·단어 빈도·분류 분석."""
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "공고를 찾을 수 없습니다.")
    raw = analyze_job_body_keywords(job)
    return KeywordAnalysisOut.model_validate(raw)


@router.post("/jobs/{job_id}/application-draft")
def application_draft(job_id: int, db: Session = Depends(get_db)):
    """공고 메타 + 지원자 프로필 기반 지원 준비 초안 (자동 제출 아님)."""
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "공고를 찾을 수 없습니다.")
    profile = db.query(ApplicantProfile).first()
    return build_application_draft(job, profile)


@router.get("/applicant/profile", response_model=ApplicantProfileOut)
def get_applicant_profile(db: Session = Depends(get_db)):
    return _get_or_create_profile(db)


@router.put("/applicant/profile", response_model=ApplicantProfileOut)
def put_applicant_profile(body: ApplicantProfileUpdate, db: Session = Depends(get_db)):
    p = _get_or_create_profile(db)
    data = body.model_dump(exclude_unset=True)
    if "application_prefs" in data:
        merged_prefs = {**(p.application_prefs or {}), **(data.pop("application_prefs") or {})}
        p.application_prefs = merged_prefs
    if "extra_links" in data:
        merged_links = {**(p.extra_links or {}), **(data.pop("extra_links") or {})}
        p.extra_links = merged_links
    for k, v in data.items():
        setattr(p, k, v)
    p.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(p)
    return p


def _body_field_or_profile(override: str | None, stored: str | None) -> str | None:
    """본문에 필드가 있으면 빈 문자열까지 그대로 반영. 필드 생략(None)만 DB 프로필로 대체."""
    if override is None:
        return stored
    return override.strip()


@router.post("/applicant/match-jobs", response_model=MatchJobsResponse)
def post_applicant_match_jobs(body: MatchJobsRequest, db: Session = Depends(get_db)):
    """이력서에서 추출한 키워드와 공고 ExtractedSkill·메타를 맞춰 적합 공고 순위."""
    p = _get_or_create_profile(db)
    resume = _body_field_or_profile(body.resume_text, p.resume_text)
    summary = _body_field_or_profile(body.career_summary, p.career_summary)
    raw = match_jobs_for_resume(
        db,
        resume_text=resume,
        career_summary=summary,
        category=body.category,
        limit=body.limit,
    )
    return MatchJobsResponse.model_validate(raw)


@router.post("/applicant/job-cover-letter", response_model=JobCoverLetterOut)
def post_applicant_job_cover_letter(body: JobCoverLetterRequest, db: Session = Depends(get_db)):
    """맞춤 공고 옆 버튼 전용. 이력서·경력만 근거로 해당 공고 맞춤 자기소개서(약 1000자) LLM 생성."""
    p = _get_or_create_profile(db)
    resume = _body_field_or_profile(body.resume_text, p.resume_text)
    summary = _body_field_or_profile(body.career_summary, p.career_summary)
    if not (resume or "").strip() and not (summary or "").strip():
        raise HTTPException(
            status_code=400,
            detail="이력서 또는 경력 요약이 필요합니다. 입력란에 적거나 프로필에 저장하세요.",
        )
    job = db.query(Job).filter(Job.id == body.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다.")
    resume_use = (resume or "")[:MAX_RESUME_TEXT_IN_JSON]
    summary_use = (summary or "")[: min(80_000, MAX_RESUME_TEXT_IN_JSON)]
    raw = generate_job_cover_letter(job, resume_use, summary_use)
    return JobCoverLetterOut.model_validate(raw)


@router.get("/applicant/preparation", response_model=PreparationInsightOut)
def get_applicant_preparation(
    category: str | None = None,
    db: Session = Depends(get_db),
):
    """수집 공고 기준 업계 요구 스킬 상위와 이력서 대비 갭·준비 문장."""
    p = _get_or_create_profile(db)
    raw = preparation_insights(
        db,
        resume_text=p.resume_text,
        career_summary=p.career_summary,
        category=category,
    )
    return PreparationInsightOut.model_validate(raw)


def _collect_suggestions_response(
    db: Session,
    resume: str | None,
    summary: str | None,
    hint: str | None,
    career_years_override: int | None,
) -> CollectSuggestionsOut:
    h = (hint or "").strip() or None
    if h == "all":
        h = None
    raw = build_collect_suggestions(
        db,
        resume_text=resume or "",
        career_summary=summary,
        analysis_category_hint=h,
        career_years_override=career_years_override,
    )
    return CollectSuggestionsOut.model_validate(raw)


@router.get("/applicant/collect-suggestions", response_model=CollectSuggestionsOut)
def get_applicant_collect_suggestions(
    analysis_category_hint: str | None = None,
    db: Session = Depends(get_db),
):
    """저장된 프로필 이력서·경력 기준 수집 키워드·직군 추천."""
    p = _get_or_create_profile(db)
    return _collect_suggestions_response(
        db,
        p.resume_text,
        p.career_summary,
        analysis_category_hint,
        p.career_years,
    )


def _post_applicant_collect_suggestions_impl(
    body: CollectSuggestRequest,
    db: Session,
) -> CollectSuggestionsOut:
    p = _get_or_create_profile(db)
    resume = _body_field_or_profile(body.resume_text, p.resume_text)
    summary = _body_field_or_profile(body.career_summary, p.career_summary)
    return _collect_suggestions_response(
        db,
        resume,
        summary,
        body.analysis_category_hint,
        p.career_years,
    )


@router.post("/applicant/collect-suggestions", response_model=CollectSuggestionsOut)
def post_applicant_collect_suggestions(
    body: CollectSuggestRequest,
    db: Session = Depends(get_db),
):
    """화면에 입력 중인 이력서·경력(미저장)까지 반영해 수집 추천."""
    return _post_applicant_collect_suggestions_impl(body, db)


@router.post("/applicant/collect_suggestions", response_model=CollectSuggestionsOut)
def post_applicant_collect_suggestions_underscore(
    body: CollectSuggestRequest,
    db: Session = Depends(get_db),
):
    """하이픈 경로와 동일(구버전·일부 프록시 호환)."""
    return _post_applicant_collect_suggestions_impl(body, db)


@router.get("/resume/insight", response_model=ResumeInsightOut)
def get_resume_insight(
    resume_text: str | None = Query(None),
    career_summary: str | None = Query(None),
    category: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """이력서 시장 인사이트(적합도·영향도 갭·차별화 자산·경로·액션). 쿼리 미전달 시 저장된 프로필 사용."""
    p = _get_or_create_profile(db)
    rt = resume_text if resume_text is not None else p.resume_text
    cs = career_summary if career_summary is not None else p.career_summary
    if not (rt or "").strip() and not (cs or "").strip():
        raise HTTPException(
            400,
            "이력서 또는 경력 요약이 필요합니다. 프로필을 저장하거나 쿼리 파라미터로 전달하세요.",
        )
    raw = build_resume_insight(db, resume_text=rt or "", career_summary=cs, category=category)
    return ResumeInsightOut.model_validate(raw)


@router.post("/resume/insight", response_model=ResumeInsightOut)
def post_resume_insight(body: ResumeInsightRequest, db: Session = Depends(get_db)):
    """긴 이력서 본문은 POST로 전달하는 것을 권장합니다."""
    p = _get_or_create_profile(db)
    rt = _body_field_or_profile(body.resume_text, p.resume_text)
    cs = _body_field_or_profile(body.career_summary, p.career_summary)
    if not (rt or "").strip() and not (cs or "").strip():
        raise HTTPException(
            400,
            "resume_text 또는 career_summary 중 최소 하나가 필요합니다.",
        )
    raw = build_resume_insight(db, resume_text=rt or "", career_summary=cs, category=body.category)
    return ResumeInsightOut.model_validate(raw)


@router.post("/applicant/resume/analyze-pdf", response_model=ResumePdfAnalyzeOut)
async def post_applicant_resume_analyze_pdf(
    file: UploadFile = File(...),
    category: str | None = Form(None),
    apply_to_profile: str = Form("false"),
    db: Session = Depends(get_db),
):
    """PDF 업로드 → 텍스트 추출 → 요약·강약점·공고 대비 차트 데이터. 선택 시 프로필에 반영."""
    data = await file.read()
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(413, "PDF 파일은 12MB 이하만 업로드할 수 있습니다.")
    raw_text = extract_text_from_pdf_bytes(data)
    if not raw_text.strip():
        raise HTTPException(
            422,
            "PDF에서 텍스트를 읽지 못했습니다. 텍스트 레이어가 있는 PDF을 사용하거나, 본문을 직접 붙여 넣어 주세요.",
        )

    cat = (category or "").strip() or None
    if cat == "all":
        cat = None

    dash = build_resume_dashboard(db, raw_text, cat)

    apply = (apply_to_profile or "").strip().lower() in ("1", "true", "yes", "on")
    profile_updated = False
    if apply:
        p = _get_or_create_profile(db)
        p.resume_text = raw_text
        p.career_summary = dash["career_summary_suggested"]
        if dash.get("career_years_estimate") is not None:
            p.career_years = dash["career_years_estimate"]
        prefs = dict(p.application_prefs or {})
        if cat and cat in CATEGORY_LABEL:
            prefs["last_dashboard_category"] = cat
        p.application_prefs = prefs
        p.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(p)
        profile_updated = True

    text_out = raw_text
    text_truncated = False
    if len(text_out) > MAX_RESUME_TEXT_IN_JSON:
        text_out = text_out[:MAX_RESUME_TEXT_IN_JSON]
        text_truncated = True

    payload = {
        "extracted_char_count": len(raw_text),
        "text_truncated": text_truncated,
        "resume_text": text_out,
        "summary_paragraph": dash["summary_paragraph"],
        "career_summary_suggested": dash["career_summary_suggested"],
        "core_skills": dash["core_skills"],
        "career_years_estimate": dash["career_years_estimate"],
        "applicable_areas": dash["applicable_areas"],
        "strengths": dash["strengths"],
        "weaknesses": dash["weaknesses"],
        "preparation_notes": dash["preparation_notes"],
        "charts": dash["charts"],
        "collect_suggestions": dash["collect_suggestions"],
        "profile_updated": profile_updated,
    }
    return ResumePdfAnalyzeOut.model_validate(payload)


@router.get("/jobs/stats/skills", response_model=list[SkillStatOut])
def job_skill_stats(category: str, db: Session = Depends(get_db)):
    rows = (
        db.query(ExtractedSkill.normalized_skill, ExtractedSkill.skill_group, func.count())
        .join(Job, Job.id == ExtractedSkill.job_id)
        .filter(Job.category == category)
        .group_by(ExtractedSkill.normalized_skill, ExtractedSkill.skill_group)
        .order_by(func.count().desc())
        .limit(20)
        .all()
    )
    return [
        SkillStatOut(normalized_skill=r[0], skill_group=r[1], count=r[2]) for r in rows
    ]


@router.get("/trends/series", response_model=list[TrendSeriesOut])
def trend_series(
    category: str,
    keywords: str = Query(
        ...,
        description="쉼표로 구분된 키워드 목록",
    ),
    days: int = Query(90, le=365),
    db: Session = Depends(get_db),
):
    since = date.today() - timedelta(days=days)
    kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
    out: list[TrendSeriesOut] = []
    for kw in kw_list[:8]:
        pts = (
            db.query(TrendKeyword.date, TrendKeyword.interest_score)
            .filter(
                TrendKeyword.category == category,
                TrendKeyword.keyword == kw,
                TrendKeyword.date >= since,
            )
            .order_by(TrendKeyword.date)
            .all()
        )
        out.append(
            TrendSeriesOut(
                keyword=kw,
                points=[TrendPointOut(date=d, interest_score=s) for d, s in pts],
            )
        )
    return out


@router.get("/analysis/gap", response_model=list[GapItemOut])
def analysis_gap(category: str, db: Session = Depends(get_db)):
    refresh_demand_supply_summary(db, category)
    rows = (
        db.query(DemandSupplySummary)
        .filter(DemandSupplySummary.category == category)
        .order_by(DemandSupplySummary.demand_score.desc())
        .all()
    )
    return [
        GapItemOut(
            keyword=r.keyword,
            demand_score=r.demand_score,
            interest_score=r.interest_score,
            gap_type=r.gap_type,
            gap_label_ko=GAP_LABELS_KO.get(r.gap_type, r.gap_type),
        )
        for r in rows
    ]


@router.get("/analysis/interpret/{keyword}")
def analysis_interpret(category: str, keyword: str, db: Session = Depends(get_db)):
    return {"keyword": keyword, "text": interpretation_for_gap(db, category, keyword)}


@router.get("/recommendations", response_model=list[RecommendationOut])
def get_recommendations(
    category: str,
    target_type: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Recommendation).filter(Recommendation.category == category)
    if target_type:
        q = q.filter(Recommendation.target_type == target_type)
    return q.order_by(Recommendation.generated_at.desc()).all()


@router.get("/scraper/logs", response_model=list[ScraperLogOut])
def scraper_logs(limit: int = 20, db: Session = Depends(get_db)):
    return (
        db.query(ScraperRunLog)
        .order_by(ScraperRunLog.run_started_at.desc())
        .limit(limit)
        .all()
    )


@router.post("/admin/recompute")
def admin_recompute(category: str | None = None, db: Session = Depends(get_db)):
    if category:
        cats = [category]
    else:
        cats = list(CATEGORY_LABEL.keys()) + [
            r.slug for r in db.query(ConsultantCustomCategory.slug).all()
        ]
        cats = list(dict.fromkeys(cats))
    for c in cats:
        refresh_demand_supply_summary(db, c)
    return {"ok": True, "categories": cats}


def _collect_result_from_payload(db: Session, result: dict) -> CollectResult:
    job_links: list[CollectedJobLink] = []
    for jid in result["job_ids"]:
        job = db.get(Job, jid)
        if not job:
            continue
        job_links.append(
            CollectedJobLink(
                id=job.id,
                title=job.title,
                company=job.company,
                source=job.source,
                url=resolve_job_listing_url(job),
            )
        )
    return CollectResult(
        jobs_fetched=result["jobs_fetched"],
        jobs_new=result["jobs_new"],
        job_ids=result["job_ids"],
        errors=result.get("errors", []),
        job_links=job_links,
        cancelled=bool(result.get("cancelled", False)),
    )


@router.get("/collect/sources-health")
def collect_sources_health():
    """사람인·잡코리아 목록 1회 GET·파싱 스모크(저장 없음). 대시보드에서 연결 상태 확인용."""
    import time as time_mod

    from scrapers.jobkorea_search import fetch_listings as jk_list
    from scrapers.saramin_search import fetch_listings as sr_list

    out: dict[str, dict] = {}
    for key, fn in (("saramin", sr_list), ("jobkorea", jk_list)):
        t0 = time_mod.perf_counter()
        try:
            rows = fn("Python", 1)
            ms = round((time_mod.perf_counter() - t0) * 1000, 1)
            out[key] = {"ok": True, "listings": len(rows), "ms": ms}
        except Exception as e:
            ms = round((time_mod.perf_counter() - t0) * 1000, 1)
            out[key] = {"ok": False, "listings": 0, "ms": ms, "error": str(e)[:400]}
    return out


@router.post("/collect", response_model=CollectResult)
def collect_jobs(body: CollectRequest, db: Session = Depends(get_db)):
    allowed = collect_category_slugs(db)
    if body.category not in allowed:
        raise HTTPException(
            400,
            f"알 수 없는 category: {body.category}. 직군을 추가하거나 기존 슬러그를 선택하세요.",
        )
    if not body.sources:
        raise HTTPException(400, "sources가 비었습니다.")
    merged_kw = merge_collect_keywords(db, body.category, list(body.keywords))
    result = collect_by_keywords(
        db,
        keywords=merged_kw,
        category=body.category,
        sources=body.sources,
        max_pages=body.max_pages,
        fetch_detail=body.fetch_detail,
        use_ocr=body.use_ocr,
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    return _collect_result_from_payload(db, result)


@router.post("/collect/stream")
async def collect_jobs_stream(request: Request, body: CollectRequest, db: Session = Depends(get_db)):
    """NDJSON 스트림으로 진행 이벤트를 보냅니다. 클라이언트가 연결을 끊으면 취소로 간주합니다."""
    allowed = collect_category_slugs(db)
    if body.category not in allowed:
        raise HTTPException(
            400,
            f"알 수 없는 category: {body.category}. 직군을 추가하거나 기존 슬러그를 선택하세요.",
        )
    if not body.sources:
        raise HTTPException(400, "sources가 비었습니다.")
    merged_kw = merge_collect_keywords(db, body.category, list(body.keywords))

    sync_q: queue.Queue[dict | None] = queue.Queue(maxsize=128)
    cancel_evt = threading.Event()

    async def watch_disconnect() -> None:
        try:
            while not cancel_evt.is_set():
                if await request.is_disconnected():
                    cancel_evt.set()
                    return
                await asyncio.sleep(0.25)
        except asyncio.CancelledError:
            return

    async def byte_stream():
        # 첫 청크 즉시 전송(클라이언트·프록시가 응답을 열고 스트림을 기다리게 함)
        yield b'{"type":"progress","phase":"connecting"}\n'
        watcher = asyncio.create_task(watch_disconnect())

        def producer() -> None:
            """수집은 전용 OS 스레드 + 별도 DB 세션( asyncio 기본 스레드 풀과 분리 — 풀 고갈 교착 방지 )."""
            db_worker = SessionLocal()
            try:
                for ev in generate_collect_events(
                    db_worker,
                    keywords=merged_kw,
                    category=body.category,
                    sources=body.sources,
                    max_pages=body.max_pages,
                    fetch_detail=body.fetch_detail,
                    use_ocr=body.use_ocr,
                    cancel_check=cancel_evt.is_set,
                    emit=None,
                ):
                    sync_q.put(ev)
            finally:
                db_worker.close()
                sync_q.put(None)

        prod_thread = threading.Thread(target=producer, name="collect-stream", daemon=True)
        prod_thread.start()
        try:
            while True:
                ev = await asyncio.to_thread(sync_q.get)
                if ev is None:
                    break
                if ev.get("type") in ("done", "cancelled") and isinstance(ev.get("payload"), dict):
                    cr = _collect_result_from_payload(db, ev["payload"])
                    ev = {**ev, "payload": cr.model_dump()}
                line = json.dumps(ev, ensure_ascii=False) + "\n"
                yield line.encode("utf-8")
        finally:
            cancel_evt.set()
            watcher.cancel()
            try:
                await watcher
            except asyncio.CancelledError:
                pass
            prod_thread.join(timeout=2.0)

    return StreamingResponse(
        byte_stream(),
        media_type="application/x-ndjson; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/llm/status")
def llm_status():
    from app.config import settings

    return {
        "openai_configured": bool(settings.openai_api_key),
        "ollama_enabled": settings.ollama_enabled,
        "ollama_base_url": settings.ollama_base_url,
        "ollama_model": settings.ollama_model,
        "ollama_reachable": ollama_health(),
    }
