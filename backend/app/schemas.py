from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    external_id: str | None = None
    search_keyword: str | None = None
    title: str
    company: str
    category: str
    location: str | None
    posted_at: date | None
    collected_at: datetime
    source_url: str | None = None
    job_metadata: dict[str, Any] | None = None


class CollectRequest(BaseModel):
    """키워드 검색으로 사람인·잡코리아에서 공고를 가져와 분석합니다."""

    keywords: list[str] = Field(..., min_length=1, description="검색 키워드 (복수)")
    category: str = Field(..., description="직군 슬러그: data_analyst | ai_engineer | backend_developer")
    sources: list[Literal["saramin", "jobkorea"]] = Field(
        default_factory=lambda: ["saramin", "jobkorea"]
    )
    max_pages: int = Field(1, ge=1, le=5, description="소스·키워드당 페이지 수")
    fetch_detail: bool = Field(
        False,
        description="상세 페이지를 열어 이미지 후보 추출(+OCR). 켜면 요청이 길어질 수 있음",
    )
    use_ocr: bool = Field(True, description="이미지에 대해 한·영 OCR 적용 (easyocr 필요)")


class CollectedJobLink(BaseModel):
    """수집 직후(또는 이번에 반환된 job_id)에 대응하는 원본 공고 링크."""

    id: int
    title: str
    company: str
    source: str
    url: str | None = None


class CollectResult(BaseModel):
    jobs_fetched: int
    jobs_new: int
    job_ids: list[int]
    errors: list[str]
    job_links: list[CollectedJobLink] = Field(default_factory=list)
    cancelled: bool = Field(False, description="스트림 수집 중 사용자 취소·연결 종료로 조기 종료")


class SkillStatOut(BaseModel):
    normalized_skill: str
    skill_group: str
    count: int


class TrendPointOut(BaseModel):
    date: date
    interest_score: float


class TrendSeriesOut(BaseModel):
    keyword: str
    points: list[TrendPointOut]


class GapItemOut(BaseModel):
    keyword: str
    demand_score: float
    interest_score: float
    gap_type: str
    gap_label_ko: str


class OverviewOut(BaseModel):
    job_counts_by_category: dict[str, int]
    top_demand_categories: list[tuple[str, int]]
    rising_interest_keywords: list[str]
    opportunity_keywords: list[str]
    oversaturated_keywords: list[str]


class RecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    target_type: str
    category: str
    title: str
    content: str
    generated_at: datetime


class ScraperLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    run_started_at: datetime
    run_finished_at: datetime | None
    status: str
    jobs_fetched: int
    jobs_new: int
    error_message: str | None


class ApplicantProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str | None = None
    career_years: int | None = None
    career_summary: str | None = None
    resume_text: str | None = None
    portfolio_urls: list[str] = Field(default_factory=list)
    extra_links: dict[str, Any] | None = None
    application_prefs: dict[str, Any] | None = None
    updated_at: datetime | None = None

    @field_validator("portfolio_urls", mode="before")
    @classmethod
    def _null_urls(cls, v: Any) -> list[str]:
        return v if isinstance(v, list) else []


class ApplicantProfileUpdate(BaseModel):
    display_name: str | None = None
    career_years: int | None = None
    career_summary: str | None = None
    resume_text: str | None = None
    portfolio_urls: list[str] | None = None
    extra_links: dict[str, Any] | None = None
    application_prefs: dict[str, Any] | None = Field(
        None,
        description="기존 application_prefs와 병합(키 단위 덮어쓰기). 예: last_dashboard_category",
    )


class FormSummaryOut(BaseModel):
    """지원 양식에 쓰이는 요약 필드(메타에서 추출)."""

    work_location: str | None = None
    salary: str | None = None
    career: dict[str, Any] | None = None
    requirements_lines: int = 0
    preferred_lines: int = 0
    responsibilities_lines: int = 0


class TechnicalTermItem(BaseModel):
    term: str
    count: int = 1
    group: str
    group_label_ko: str
    normalized: str | None = None
    section: str | None = None
    confidence: float | None = None


class SoftSkillItem(BaseModel):
    phrase: str
    section: str | None = None


class GroupDistItem(BaseModel):
    group: str
    label_ko: str
    count: int


class WordFreqItem(BaseModel):
    token: str
    count: int


class AnalyzedKeywordItemOut(BaseModel):
    keyword: str
    jobs_count: int
    mentions_count: int


class KeywordJobItemOut(BaseModel):
    id: int
    title: str
    company: str
    source: str
    source_url: str | None = None
    work_location: str | None = None
    career_label: str | None = None


class ResumeSkillItemOut(BaseModel):
    normalized: str
    skill_group: str


class MatchedJobItemOut(BaseModel):
    id: int
    title: str
    company: str
    category: str
    source: str
    source_url: str | None = None
    match_score: float
    matched_skills: list[str] = Field(default_factory=list)
    job_skill_count: int = 0
    requirements_total: int = 0
    requirements_mismatch: list[str] = Field(
        default_factory=list,
        description="자격요건(메타) 각 줄 대비 이력서·추출 스킬과 맞지 않는 항목",
    )


class MatchJobsRequest(BaseModel):
    """이력서·경력 텍스트로 공고 적합도 추천. 필드 생략 시에만 저장 프로필을 쓰고, 빈 문자열은 화면에서 비운 값으로 처리."""

    resume_text: str | None = None
    career_summary: str | None = None
    category: str | None = Field(None, description="직군 필터: data_analyst | ai_engineer | backend_developer")
    limit: int = Field(25, ge=1, le=100)


class MatchJobsResponse(BaseModel):
    resume_skills: list[ResumeSkillItemOut]
    jobs: list[MatchedJobItemOut]


class IndustrySkillDemandOut(BaseModel):
    normalized_skill: str
    skill_group: str
    job_count: int


class PreparationInsightOut(BaseModel):
    """업계(수집 공고) 요구 스킬 vs 이력서 갭·준비 제안."""

    category: str
    resume_skills: list[ResumeSkillItemOut]
    industry_top_skills: list[IndustrySkillDemandOut]
    aligned_skills: list[str]
    gap_skills: list[str]
    action_items: list[str]


class ChartBarSkillOut(BaseModel):
    skill: str
    demand_index: float
    resume_cover: float


class ChartRadarGroupOut(BaseModel):
    group_key: str
    label_ko: str
    resume_score: float
    market_score: float


class ChartPieSliceOut(BaseModel):
    name: str
    value: float


class ResumeDashboardChartsOut(BaseModel):
    """프론트 Recharts용 시리즈."""

    skill_bars: list[ChartBarSkillOut]
    group_radar: list[ChartRadarGroupOut]
    strength_gap_pie: list[ChartPieSliceOut]
    gap_priority_bars: list[ChartBarSkillOut]


class CategoryFitOut(BaseModel):
    """수집 시 선택할 직군(3종) 적합도 순위."""

    slug: str
    label_ko: str
    score: float
    reasons: list[str] = Field(default_factory=list)


class CollectSuggestionsOut(BaseModel):
    """분석 기반 공고 수집 키워드·직군 추천."""

    search_keywords: list[str]
    primary_category_slug: str
    primary_category_label_ko: str
    category_ranked: list[CategoryFitOut]
    role_expansion_notes: list[str] = Field(
        default_factory=list,
        description="3개 직군 슬롯에 없는 역할(프론트·DE 등) 검색·수집 가이드",
    )
    optional_gap_keywords: list[str] = Field(
        default_factory=list,
        description="공고 상위 수요인데 이력서에 약한 스킬 — 추가 검색어 후보",
    )


class CollectSuggestRequest(BaseModel):
    """저장 전에도 텍스트만으로 수집 추천을 받을 때. 필드 생략 시에만 프로필 폴백, 빈 문자열은 그대로 반영."""

    resume_text: str | None = None
    career_summary: str | None = None
    analysis_category_hint: str | None = Field(
        None,
        description="이력 분석 화면에서 고른 직군을 가산점으로 반영 (data_analyst | ai_engineer | backend_developer | all)",
    )


class ResumeInsightRequest(BaseModel):
    """이력서 시장 인사이트(적합도·갭·차별화·경로·액션). 필드 생략 시에만 프로필 폴백."""

    resume_text: str | None = None
    career_summary: str | None = None
    category: str | None = Field(
        None,
        description="가산 직군 힌트 (data_analyst | ai_engineer | backend_developer | all)",
    )


class ResumeInsightOut(BaseModel):
    """build_resume_insight() 결과 — 매칭 점수를 넘어선 시장 해석."""

    summary: dict[str, Any]
    core_strengths: list[str]
    high_impact_gaps: list[dict[str, Any]]
    optional_gaps: list[dict[str, Any]]
    differentiator_gaps: list[dict[str, Any]]
    differentiator_assets: list[dict[str, Any]]
    market_positioning: dict[str, str]
    path_recommendations: list[str]
    action_plan: dict[str, list[str]]
    collect_suggestions: CollectSuggestionsOut
    evidence: dict[str, Any]


class ResumePdfAnalyzeOut(BaseModel):
    """PDF 추출 + 경력 요약·강약점·공고 대비 차트 데이터."""

    extracted_char_count: int
    text_truncated: bool
    resume_text: str
    summary_paragraph: str
    career_summary_suggested: str
    core_skills: list[ResumeSkillItemOut]
    career_years_estimate: int | None = None
    applicable_areas: list[str]
    strengths: list[str]
    weaknesses: list[str]
    preparation_notes: list[str]
    charts: ResumeDashboardChartsOut
    collect_suggestions: CollectSuggestionsOut
    profile_updated: bool = False


class KeywordAnalysisOut(BaseModel):
    """공고 본문(메타) 키워드·기술어 분석 결과."""

    job_id: int
    title: str
    company: str
    category: str
    form_summary: FormSummaryOut
    analyzed_char_length: int
    technical_terms: list[TechnicalTermItem]
    group_distribution: list[GroupDistItem]
    word_frequency: list[WordFreqItem]
    soft_skills: list[SoftSkillItem] = Field(
        default_factory=list,
        description="2단계 LLM이 분리한 소프트스킬(비기술)",
    )
    pipeline: dict[str, Any] = Field(
        default_factory=dict,
        description="1단계 RAKE/YAKE/Kiwi + 2단계 LLM 원본·오류",
    )


# --- 컨설턴트(다인 학생 관리) ---


class ConsultantStudentCreate(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=128)
    email: str | None = None
    phone: str | None = None
    school: str | None = None
    memo: str | None = None
    resume_text: str | None = None
    career_summary: str | None = None
    target_category: str = Field(default="data_analyst", max_length=64)
    final_goal_progress: float = Field(0.0, ge=0.0, le=100.0)


class ConsultantStudentUpdate(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=128)
    email: str | None = None
    phone: str | None = None
    school: str | None = None
    memo: str | None = None
    resume_text: str | None = None
    career_summary: str | None = None
    target_category: str | None = Field(None, max_length=64)
    final_goal_progress: float | None = Field(None, ge=0.0, le=100.0)


class ConsultantStudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str
    email: str | None = None
    phone: str | None = None
    school: str | None = None
    memo: str | None = None
    resume_text: str | None = None
    career_summary: str | None = None
    target_category: str
    final_goal_progress: float
    created_at: datetime
    updated_at: datetime | None = None


class StudentCalendarEventCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    event_type: Literal["exam", "application_deadline", "interview", "other"] = "other"
    starts_at: datetime
    ends_at: datetime | None = None
    company_name: str | None = Field(None, max_length=256)
    job_id: int | None = None
    notes: str | None = None


class StudentCalendarEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    student_name: str = ""
    title: str
    event_type: str
    starts_at: datetime
    ends_at: datetime | None = None
    company_name: str | None = None
    job_id: int | None = None
    notes: str | None = None


class StudentMonthlyGoalUpsert(BaseModel):
    certifications: str = ""
    competencies: str = ""
    application_areas: str = ""


class StudentMonthlyGoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    year_month: str
    certifications: str
    competencies: str
    application_areas: str


class StudentTargetCompanyCreate(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=256)
    notes: str | None = None
    priority: int = 0


class StudentTargetCompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    company_name: str
    notes: str | None = None
    priority: int


class ConsultantDashboardOut(BaseModel):
    """캘린더 + 학생 목록 + 해당 월 목표 한 번에."""

    year: int
    month: int
    year_month: str
    students: list[ConsultantStudentOut]
    events: list[StudentCalendarEventOut]
    monthly_goals: list[StudentMonthlyGoalOut]


class ConsultantEligibleJobOut(BaseModel):
    job_id: int
    title: str
    company: str
    category: str
    match_score: float
    matched_skills: list[str] = Field(default_factory=list)
    requirements_mismatch: list[str] = Field(default_factory=list)


class ConsultantStudentDetailOut(BaseModel):
    student: ConsultantStudentOut
    appeal_points: list[str]
    improvement_points: list[str]
    preparation_notes: list[str]
    target_companies: list[StudentTargetCompanyOut]
    eligible_jobs: list[ConsultantEligibleJobOut]
    target_aligned_jobs: list[ConsultantEligibleJobOut]
    personal_events: list[StudentCalendarEventOut]
    current_month_goal: StudentMonthlyGoalOut | None = None


class ConsultantCategoryItemOut(BaseModel):
    slug: str
    label: str
    is_builtin: bool
    id: int | None = None


class ConsultantCategoryCreate(BaseModel):
    slug: str = Field(..., min_length=2, max_length=64)
    label_ko: str = Field(..., min_length=1, max_length=128)


class ImportFromApplicantRequest(BaseModel):
    """대시보드 단일 프로필 → 학생 신규 또는 기존 학생 덮어쓰기."""

    student_id: int | None = Field(None, description="있으면 해당 학생에 이력·경력만 반영")
    display_name_for_new: str | None = Field(
        None, description="신규 생성 시 이름(미입력 시 프로필 표시명 또는 기본문구)"
    )
