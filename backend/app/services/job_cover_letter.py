"""공고별 자기소개서 초안 — 사용자 이력서·경력만 근거로 LLM 생성 (버튼 클릭 시에만 호출)."""

from __future__ import annotations

from app.models import Job
from app.services.llm_client import chat_completion
from app.services.posting_metadata import merged_job_metadata, rag_document_text


def _truncate(s: str, max_len: int) -> str:
    s = (s or "").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 20] + "\n…(이하 생략)"


def _fallback_letter(job: Job, resume: str, summary: str) -> str:
    meta = merged_job_metadata(job)
    reqs = meta.get("requirements") or []
    pref = meta.get("preferred") or []
    head = (
        "[자동 생성 불가] OpenAI 키 또는 Ollama(로컬 LLM) 연결이 없어 본문을 생성하지 못했습니다.\n"
        "Ollama를 켠 뒤 다시 시도하거나, 아래 요지를 바탕으로 직접 작성해 주세요.\n\n"
    )
    body = (
        f"지원 회사: {job.company}\n"
        f"포지션: {job.title}\n\n"
        f"제가 이력서·경력에 적어 둔 내용을 바탕으로, 위 포지션의 핵심 요건과 연결되는 경험을 "
        f"구체 사례와 수치 중심으로 서술하고자 합니다.\n\n"
    )
    if reqs:
        body += "[공고 자격요건 중 이력서와 맞물릴 수 있는 키워드]\n"
        for line in reqs[:8]:
            if isinstance(line, str) and line.strip():
                body += f"- {line.strip()}\n"
        body += "\n"
    if pref:
        body += "[우대사항 참고]\n"
        for line in pref[:6]:
            if isinstance(line, str) and line.strip():
                body += f"- {line.strip()}\n"
    if resume[:400]:
        body += f"\n[이력서 발췌]\n{_truncate(resume, 600)}\n"
    if summary.strip():
        body += f"\n[경력 요약]\n{_truncate(summary, 400)}\n"
    return head + body


def generate_job_cover_letter(job: Job, resume_text: str, career_summary: str) -> dict:
    resume = (resume_text or "").strip()
    summary = (career_summary or "").strip()
    meta_doc = rag_document_text(job)
    desc_excerpt = _truncate(job.description or "", 4500)

    system = (
        "당신은 취업 자기소개서 코치이다. 사용자가 제공한 이력서·경력 텍스트에 실제로 나타난 "
        "사실·역량·경험만 근거로 삼아, 특정 채용 공고에 맞춘 자기소개서 본문을 작성한다.\n"
        "규칙:\n"
        "- 한국어, 격식 있는 자기소개서 문체.\n"
        "- 공백 포함 약 950~1050자로 분량을 맞춘다(±50자 허용). 분량을 맞추기 위해 불필요한 반복은 피한다.\n"
        "- 공고의 직무·요구 스킬·자격·우대 키워드 중, 사용자 텍스트에서 뒷받침할 수 있는 것만 골라 어필한다.\n"
        "- 이력서·경력에 없는 학위, 자격증, 프로젝트, 회사 경력, 기술 스택은 절대 지어내지 않는다.\n"
        "- 추측·과장 금지. 애매하면 일반적 동기·학습 의지로만 표현한다.\n"
        "- 마크다운, 번호 목록, 글머리표 없이 순수 본문만 출력한다(문단 나눔은 빈 줄로 가능)."
    )

    user = (
        f"[채용 공고]\n"
        f"회사: {job.company}\n"
        f"공고 제목: {job.title}\n"
        f"직군 태그: {job.category}\n\n"
        f"[공고 구조화 정보]\n{meta_doc}\n\n"
        f"[공고 본문 발췌]\n{desc_excerpt}\n\n"
        f"[내 이력서 전문]\n{resume or '(없음)'}\n\n"
        f"[내 경력 요약]\n{summary or '(없음)'}\n"
    )

    text = chat_completion(system, user, temperature=0.42)
    if text and len(text.strip()) >= 80:
        out = text.strip()
        return {
            "job_id": job.id,
            "title": job.title,
            "company": job.company,
            "text": out,
            "generated_by": "llm",
            "char_count": len(out),
        }

    fb = _fallback_letter(job, resume, summary)
    return {
        "job_id": job.id,
        "title": job.title,
        "company": job.company,
        "text": fb,
        "generated_by": "fallback",
        "char_count": len(fb),
    }
