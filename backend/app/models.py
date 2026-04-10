import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class GapType(str, enum.Enum):
    oversaturated = "oversaturated"  # 과포화 가능성
    opportunity = "opportunity"  # 기회 영역
    stable_hot = "stable_hot"  # 안정적 인기
    low_priority = "low_priority"  # 비추천


class TargetType(str, enum.Enum):
    academy = "academy"
    jobseeker = "jobseeker"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    search_keyword: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(512))
    company: Mapped[str] = mapped_column(String(256))
    category: Mapped[str] = mapped_column(String(64), index=True)
    description: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)
    posted_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # RAG용 구조화 메타(지원요건·우대·담당업무 등). 원본 HTML/긴 본문은 description에 두지 않음.
    job_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    skills: Mapped[list["ExtractedSkill"]] = relationship(back_populates="job")


class ExtractedSkill(Base):
    __tablename__ = "extracted_skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    raw_skill: Mapped[str] = mapped_column(String(128))
    normalized_skill: Mapped[str] = mapped_column(String(128), index=True)
    skill_group: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)

    job: Mapped["Job"] = relationship(back_populates="skills")


class TrendKeyword(Base):
    __tablename__ = "trend_keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(String(128), index=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    interest_score: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(32), default="demo")


class DemandSupplySummary(Base):
    __tablename__ = "demand_supply_summary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(String(128), index=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    demand_score: Mapped[float] = mapped_column(Float)
    interest_score: Mapped[float] = mapped_column(Float)
    gap_type: Mapped[str] = mapped_column(String(32), index=True)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_type: Mapped[str] = mapped_column(String(32), index=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(256))
    content: Mapped[str] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ApplicantProfile(Base):
    """단일 사용자 MVP: 경력·이력서·포트폴리오·지원 설정 (향후 RAG·자동 초안 연동)."""

    __tablename__ = "applicant_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    career_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    career_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    resume_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    portfolio_urls: Mapped[list | None] = mapped_column(JSON, nullable=True)
    extra_links: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    application_prefs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ConsultantCustomCategory(Base):
    """기본 3직군 외에 컨설턴트가 추가하는 타깃 직군 슬러그."""

    __tablename__ = "consultant_custom_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    label_ko: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ConsultantStudent(Base):
    """컨설턴트가 맡은 학생(다인 관리). 이력·목표 직군·달성률 등."""

    __tablename__ = "consultant_students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    display_name: Mapped[str] = mapped_column(String(128))
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    school: Mapped[str | None] = mapped_column(String(256), nullable=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    resume_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    career_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_category: Mapped[str] = mapped_column(String(64), default="data_analyst", index=True)
    final_goal_progress: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, onupdate=datetime.utcnow)

    events: Mapped[list["StudentCalendarEvent"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    monthly_goals: Mapped[list["StudentMonthlyGoal"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    target_companies: Mapped[list["StudentTargetCompany"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )


class StudentCalendarEvent(Base):
    """시험·지원 마감·면접 등 학생별 일정."""

    __tablename__ = "student_calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("consultant_students.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(512))
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    student: Mapped["ConsultantStudent"] = relationship(back_populates="events")


class StudentMonthlyGoal(Base):
    """학생별 이번 달 달성 목표(자격증·역량·지원 영역)."""

    __tablename__ = "student_monthly_goals"
    __table_args__ = (UniqueConstraint("student_id", "year_month", name="uq_student_monthly_goal"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("consultant_students.id", ondelete="CASCADE"), index=True
    )
    year_month: Mapped[str] = mapped_column(String(7), index=True)
    certifications: Mapped[str] = mapped_column(Text, default="")
    competencies: Mapped[str] = mapped_column(Text, default="")
    application_areas: Mapped[str] = mapped_column(Text, default="")

    student: Mapped["ConsultantStudent"] = relationship(back_populates="monthly_goals")


class StudentTargetCompany(Base):
    """학생이 지원하고 싶어하는 기업 목록."""

    __tablename__ = "student_target_companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("consultant_students.id", ondelete="CASCADE"), index=True
    )
    company_name: Mapped[str] = mapped_column(String(256))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    student: Mapped["ConsultantStudent"] = relationship(back_populates="target_companies")


class ScraperRunLog(Base):
    """사람인/잡코리아 등 수집 작업의 메타데이터·로그 (매크로/크롤러 연동용)."""

    __tablename__ = "scraper_run_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    run_started_at: Mapped[datetime] = mapped_column(DateTime)
    run_finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    jobs_fetched: Mapped[int] = mapped_column(Integer, default=0)
    jobs_new: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
