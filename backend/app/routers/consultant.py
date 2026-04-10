"""컨설턴트용: 다수 학생, 캘린더, 월간 목표, 희망 기업·지원 가능 공고."""

from __future__ import annotations

import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import get_db
from app.models import (
    ApplicantProfile,
    ConsultantCustomCategory,
    ConsultantStudent,
    Job,
    StudentCalendarEvent,
    StudentMonthlyGoal,
    StudentTargetCompany,
)
from app.schemas import (
    ConsultantCategoryCreate,
    ConsultantCategoryItemOut,
    ConsultantDashboardOut,
    ConsultantEligibleJobOut,
    ConsultantStudentCreate,
    ConsultantStudentDetailOut,
    ConsultantStudentOut,
    ConsultantStudentUpdate,
    ImportFromApplicantRequest,
    StudentCalendarEventCreate,
    StudentCalendarEventOut,
    StudentMonthlyGoalOut,
    StudentMonthlyGoalUpsert,
    StudentTargetCompanyCreate,
    StudentTargetCompanyOut,
)
from app.seed import CATEGORY_LABEL
from app.services.consultant_import import (
    apply_contact_from_resume,
    apply_llm_contact_to_student,
    build_import_memo_lines,
    choose_final_career_summary,
    combined_content_fingerprint,
    dedupe_resume_and_summary,
    extend_memo_with_llm_lines,
    find_duplicate_student_by_content,
    infer_target_category_slug,
    merge_memo_lines,
    resolve_display_name_for_new,
    resolve_display_name_for_update,
)
from app.services.consultant_llm_extract import (
    llm_extract_student_import_with_meta,
    sanitize_llm_slug,
)
from app.services.resume_dashboard import build_resume_dashboard
from app.services.resume_match import match_jobs_for_resume

router = APIRouter(prefix="/consultant", tags=["consultant"])

_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _student_or_404(db: Session, sid: int) -> ConsultantStudent:
    s = db.query(ConsultantStudent).filter(ConsultantStudent.id == sid).first()
    if not s:
        raise HTTPException(404, "학생을 찾을 수 없습니다.")
    return s


@router.get("/categories", response_model=list[ConsultantCategoryItemOut])
def list_consultant_categories(db: Session = Depends(get_db)):
    """기본 직군 + 컨설턴트가 추가한 직군."""
    out: list[ConsultantCategoryItemOut] = [
        ConsultantCategoryItemOut(slug=k, label=v, is_builtin=True, id=None)
        for k, v in sorted(CATEGORY_LABEL.items(), key=lambda x: x[1])
    ]
    customs = (
        db.query(ConsultantCustomCategory).order_by(ConsultantCustomCategory.label_ko.asc()).all()
    )
    for c in customs:
        out.append(
            ConsultantCategoryItemOut(
                slug=c.slug, label=c.label_ko, is_builtin=False, id=c.id
            )
        )
    return out


@router.post("/categories", response_model=ConsultantCategoryItemOut)
def create_consultant_category(body: ConsultantCategoryCreate, db: Session = Depends(get_db)):
    slug = body.slug.strip().lower()
    if not _SLUG_RE.match(slug):
        raise HTTPException(400, "slug는 영문 소문자로 시작하고 소문자·숫자·밑줄만 사용하세요.")
    if slug in CATEGORY_LABEL:
        raise HTTPException(400, "이미 기본으로 있는 직군 슬러그입니다.")
    if db.query(ConsultantCustomCategory).filter(ConsultantCustomCategory.slug == slug).first():
        raise HTTPException(400, "같은 slug가 이미 있습니다.")
    row = ConsultantCustomCategory(slug=slug, label_ko=body.label_ko.strip())
    db.add(row)
    db.commit()
    db.refresh(row)
    return ConsultantCategoryItemOut(
        slug=row.slug, label=row.label_ko, is_builtin=False, id=row.id
    )


@router.delete("/categories/{category_id}")
def delete_consultant_category(category_id: int, db: Session = Depends(get_db)):
    row = db.query(ConsultantCustomCategory).filter(ConsultantCustomCategory.id == category_id).first()
    if not row:
        raise HTTPException(404, "추가 직군을 찾을 수 없습니다.")
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.post("/import-from-applicant-profile", response_model=ConsultantStudentOut)
def import_from_applicant_profile(
    response: Response,
    body: ImportFromApplicantRequest = ImportFromApplicantRequest(),
    db: Session = Depends(get_db),
):
    """메인 대시보드에 저장된 단일 ApplicantProfile → 학생 신규 또는 기존 학생에 반영."""
    p = db.query(ApplicantProfile).first()
    if not p:
        raise HTTPException(
            400,
            "저장된 지원자 프로필이 없습니다. 대시보드에서 「프로필에 저장」을 먼저 해 주세요.",
        )
    if not ((p.resume_text or "").strip() or (p.career_summary or "").strip()):
        raise HTTPException(400, "프로필에 이력서 또는 경력 요약이 비어 있습니다.")

    prefs = p.application_prefs if isinstance(p.application_prefs, dict) else None
    resume_deduped, summary_deduped = dedupe_resume_and_summary(p.resume_text, p.career_summary)
    dash_hint = None
    if prefs:
        raw = prefs.get("last_dashboard_category") or prefs.get("dashboard_category")
        if isinstance(raw, str) and (h := raw.strip()):
            dash_hint = h if h != "all" else None

    llm = None
    llm_header = "off"
    if settings.consultant_import_llm:
        meta = llm_extract_student_import_with_meta(
            resume_deduped or "",
            summary_deduped,
            dash_hint,
            p.display_name,
        )
        llm = meta.fields
        llm_header = meta.status
    response.headers["X-Consultant-Import-Llm"] = llm_header

    summary_final = choose_final_career_summary(
        llm.career_summary if llm else None,
        summary_deduped,
        resume_deduped,
    )
    content_fp = combined_content_fingerprint(resume_deduped, summary_final)
    memo_tag = "대시보드 프로필에서 가져옴 · LLM·규칙 분석 반영"
    memo_extra = extend_memo_with_llm_lines(
        build_import_memo_lines(p, memo_tag),
        llm.consultant_memo_lines if llm else None,
    )

    if body.student_id is not None:
        s = _student_or_404(db, body.student_id)
        s.resume_text = resume_deduped
        s.career_summary = summary_final
        s.display_name = resolve_display_name_for_update(
            p,
            llm.display_name if llm else None,
            s.display_name,
            resume_deduped,
            summary_final,
        )
        apply_llm_contact_to_student(
            s,
            llm.email if llm else None,
            llm.phone if llm else None,
            llm.school if llm else None,
            only_if_empty=True,
        )
        apply_contact_from_resume(s, resume_deduped, only_if_empty=True)
        s.memo = merge_memo_lines(s.memo, memo_extra)
        s.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(s)
        return ConsultantStudentOut.model_validate(s)

    dup = find_duplicate_student_by_content(db, content_fp, exclude_id=None)
    if dup:
        raise HTTPException(
            409,
            {
                "message": "동일한 이력서·경력 내용을 가진 학생이 이미 있습니다.",
                "student_id": dup.id,
                "display_name": dup.display_name,
            },
        )

    name = resolve_display_name_for_new(
        p,
        llm.display_name if llm else None,
        resume_deduped,
        summary_final,
        body.display_name_for_new,
    )
    cat = infer_target_category_slug(
        db, resume_deduped, summary_final, p.career_years, prefs
    )
    if llm and llm.target_category_slug:
        slug = sanitize_llm_slug(llm.target_category_slug)
        if slug:
            cat = slug
    s = ConsultantStudent(
        display_name=name,
        email=None,
        phone=None,
        school=None,
        memo=merge_memo_lines(None, memo_extra),
        resume_text=resume_deduped,
        career_summary=summary_final,
        target_category=cat,
        final_goal_progress=0.0,
        created_at=datetime.utcnow(),
    )
    apply_llm_contact_to_student(
        s,
        llm.email if llm else None,
        llm.phone if llm else None,
        llm.school if llm else None,
        only_if_empty=False,
    )
    apply_contact_from_resume(s, resume_deduped, only_if_empty=False)
    db.add(s)
    db.commit()
    db.refresh(s)
    return ConsultantStudentOut.model_validate(s)


@router.get("/dashboard", response_model=ConsultantDashboardOut)
def get_consultant_dashboard(
    year: int,
    month: int,
    db: Session = Depends(get_db),
):
    if not (1 <= month <= 12):
        raise HTTPException(400, "month는 1~12입니다.")
    students = db.query(ConsultantStudent).order_by(ConsultantStudent.display_name.asc()).all()
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)

    ev_rows = (
        db.query(StudentCalendarEvent)
        .options(joinedload(StudentCalendarEvent.student))
        .filter(StudentCalendarEvent.starts_at >= start, StudentCalendarEvent.starts_at < end)
        .order_by(StudentCalendarEvent.starts_at.asc())
        .all()
    )
    ym = f"{year:04d}-{month:02d}"
    goals = (
        db.query(StudentMonthlyGoal).filter(StudentMonthlyGoal.year_month == ym).all()
    )

    events_out: list[StudentCalendarEventOut] = []
    for e in ev_rows:
        sn = e.student.display_name if e.student else ""
        events_out.append(
            StudentCalendarEventOut(
                id=e.id,
                student_id=e.student_id,
                student_name=sn,
                title=e.title,
                event_type=e.event_type,
                starts_at=e.starts_at,
                ends_at=e.ends_at,
                company_name=e.company_name,
                job_id=e.job_id,
                notes=e.notes,
            )
        )

    return ConsultantDashboardOut(
        year=year,
        month=month,
        year_month=ym,
        students=[ConsultantStudentOut.model_validate(s) for s in students],
        events=events_out,
        monthly_goals=[StudentMonthlyGoalOut.model_validate(g) for g in goals],
    )


@router.get("/students", response_model=list[ConsultantStudentOut])
def list_consultant_students(db: Session = Depends(get_db)):
    rows = db.query(ConsultantStudent).order_by(ConsultantStudent.display_name.asc()).all()
    return [ConsultantStudentOut.model_validate(s) for s in rows]


@router.post("/students", response_model=ConsultantStudentOut)
def create_consultant_student(body: ConsultantStudentCreate, db: Session = Depends(get_db)):
    s = ConsultantStudent(
        display_name=body.display_name.strip(),
        email=body.email,
        phone=body.phone,
        school=body.school,
        memo=body.memo,
        resume_text=body.resume_text,
        career_summary=body.career_summary,
        target_category=(body.target_category or "data_analyst").strip(),
        final_goal_progress=body.final_goal_progress,
        created_at=datetime.utcnow(),
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return ConsultantStudentOut.model_validate(s)


@router.get("/students/{student_id}", response_model=ConsultantStudentOut)
def get_consultant_student(student_id: int, db: Session = Depends(get_db)):
    return ConsultantStudentOut.model_validate(_student_or_404(db, student_id))


@router.patch("/students/{student_id}", response_model=ConsultantStudentOut)
def patch_consultant_student(
    student_id: int,
    body: ConsultantStudentUpdate,
    db: Session = Depends(get_db),
):
    s = _student_or_404(db, student_id)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        if k == "display_name" and isinstance(v, str):
            v = v.strip()
        setattr(s, k, v)
    s.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(s)
    return ConsultantStudentOut.model_validate(s)


@router.delete("/students/{student_id}")
def delete_consultant_student(student_id: int, db: Session = Depends(get_db)):
    s = _student_or_404(db, student_id)
    db.delete(s)
    db.commit()
    return {"ok": True}


@router.get("/students/{student_id}/detail", response_model=ConsultantStudentDetailOut)
def get_consultant_student_detail(student_id: int, db: Session = Depends(get_db)):
    s = (
        db.query(ConsultantStudent)
        .options(
            joinedload(ConsultantStudent.target_companies),
        )
        .filter(ConsultantStudent.id == student_id)
        .first()
    )
    if not s:
        raise HTTPException(404, "학생을 찾을 수 없습니다.")

    cat = s.target_category if s.target_category != "all" else None
    full_resume = "\n".join(
        p for p in (s.resume_text or "", s.career_summary or "") if p and p.strip()
    )
    appeal: list[str] = []
    improvement: list[str] = []
    prep_notes: list[str] = []
    if full_resume.strip():
        dash = build_resume_dashboard(db, full_resume, cat)
        appeal = list(dash.get("strengths") or [])[:12]
        improvement = list(dash.get("weaknesses") or [])[:12]
        prep_notes = list(dash.get("preparation_notes") or [])[:10]

    raw_match = match_jobs_for_resume(
        db,
        resume_text=s.resume_text,
        career_summary=s.career_summary,
        category=cat,
        limit=25,
    )
    eligible: list[ConsultantEligibleJobOut] = []
    for j in raw_match.get("jobs") or []:
        eligible.append(
            ConsultantEligibleJobOut(
                job_id=j["id"],
                title=j["title"],
                company=j["company"],
                category=j.get("category", ""),
                match_score=float(j.get("match_score", 0)),
                matched_skills=list(j.get("matched_skills") or []),
                requirements_mismatch=list(j.get("requirements_mismatch") or []),
            )
        )

    tset = {c.company_name.strip().lower() for c in s.target_companies}
    target_aligned = [x for x in eligible if x.company.strip().lower() in tset]

    evs = (
        db.query(StudentCalendarEvent)
        .filter(StudentCalendarEvent.student_id == student_id)
        .order_by(StudentCalendarEvent.starts_at.desc())
        .limit(80)
        .all()
    )
    personal_events = [
        StudentCalendarEventOut(
            id=e.id,
            student_id=e.student_id,
            student_name=s.display_name,
            title=e.title,
            event_type=e.event_type,
            starts_at=e.starts_at,
            ends_at=e.ends_at,
            company_name=e.company_name,
            job_id=e.job_id,
            notes=e.notes,
        )
        for e in evs
    ]

    now = datetime.utcnow()
    ym = f"{now.year:04d}-{now.month:02d}"
    mg = (
        db.query(StudentMonthlyGoal)
        .filter(StudentMonthlyGoal.student_id == student_id, StudentMonthlyGoal.year_month == ym)
        .first()
    )
    current_goal = StudentMonthlyGoalOut.model_validate(mg) if mg else None

    targets = sorted(s.target_companies, key=lambda x: (-x.priority, x.company_name))
    target_out = [StudentTargetCompanyOut.model_validate(t) for t in targets]

    return ConsultantStudentDetailOut(
        student=ConsultantStudentOut.model_validate(s),
        appeal_points=appeal,
        improvement_points=improvement,
        preparation_notes=prep_notes,
        target_companies=target_out,
        eligible_jobs=eligible[:20],
        target_aligned_jobs=target_aligned[:15],
        personal_events=personal_events,
        current_month_goal=current_goal,
    )


@router.post("/students/{student_id}/events", response_model=StudentCalendarEventOut)
def add_student_event(
    student_id: int,
    body: StudentCalendarEventCreate,
    db: Session = Depends(get_db),
):
    s = _student_or_404(db, student_id)
    if body.job_id is not None:
        if not db.query(Job.id).filter(Job.id == body.job_id).first():
            raise HTTPException(400, "job_id가 존재하지 않습니다.")
    e = StudentCalendarEvent(
        student_id=student_id,
        title=body.title.strip(),
        event_type=body.event_type,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        company_name=body.company_name,
        job_id=body.job_id,
        notes=body.notes,
    )
    db.add(e)
    s.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(e)
    return StudentCalendarEventOut(
        id=e.id,
        student_id=e.student_id,
        student_name=s.display_name,
        title=e.title,
        event_type=e.event_type,
        starts_at=e.starts_at,
        ends_at=e.ends_at,
        company_name=e.company_name,
        job_id=e.job_id,
        notes=e.notes,
    )


@router.delete("/events/{event_id}")
def delete_student_event(event_id: int, db: Session = Depends(get_db)):
    e = db.query(StudentCalendarEvent).filter(StudentCalendarEvent.id == event_id).first()
    if not e:
        raise HTTPException(404, "일정을 찾을 수 없습니다.")
    db.delete(e)
    db.commit()
    return {"ok": True}


@router.put("/students/{student_id}/goals/{year_month}", response_model=StudentMonthlyGoalOut)
def upsert_monthly_goal(
    student_id: int,
    year_month: str,
    body: StudentMonthlyGoalUpsert,
    db: Session = Depends(get_db),
):
    s = _student_or_404(db, student_id)
    if len(year_month) != 7 or year_month[4] != "-":
        raise HTTPException(400, "year_month는 YYYY-MM 형식입니다.")
    g = (
        db.query(StudentMonthlyGoal)
        .filter(StudentMonthlyGoal.student_id == student_id, StudentMonthlyGoal.year_month == year_month)
        .first()
    )
    if not g:
        g = StudentMonthlyGoal(
            student_id=student_id,
            year_month=year_month,
            certifications=body.certifications,
            competencies=body.competencies,
            application_areas=body.application_areas,
        )
        db.add(g)
    else:
        g.certifications = body.certifications
        g.competencies = body.competencies
        g.application_areas = body.application_areas
    s.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(g)
    return StudentMonthlyGoalOut.model_validate(g)


@router.post("/students/{student_id}/target-companies", response_model=StudentTargetCompanyOut)
def add_target_company(
    student_id: int,
    body: StudentTargetCompanyCreate,
    db: Session = Depends(get_db),
):
    s = _student_or_404(db, student_id)
    t = StudentTargetCompany(
        student_id=student_id,
        company_name=body.company_name.strip(),
        notes=body.notes,
        priority=body.priority,
    )
    db.add(t)
    s.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(t)
    return StudentTargetCompanyOut.model_validate(t)


@router.delete("/target-companies/{company_id}")
def delete_target_company(company_id: int, db: Session = Depends(get_db)):
    t = db.query(StudentTargetCompany).filter(StudentTargetCompany.id == company_id).first()
    if not t:
        raise HTTPException(404, "항목을 찾을 수 없습니다.")
    db.delete(t)
    db.commit()
    return {"ok": True}
