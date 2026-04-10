"""이력서·경력 텍스트 → 컨설턴트 학생 필드 JSON 추출 (OpenAI 또는 Ollama)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, NamedTuple

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import settings
from app.seed import CATEGORY_LABEL
from app.services.consultant_import import sanitize_display_name_candidate
from app.services.llm_client import chat_completion

logger = logging.getLogger(__name__)

_MAX_INPUT_RESUME = 14_000
_MAX_INPUT_SUMMARY = 4_000


class StudentImportLlmFields(BaseModel):
    """LLM이 반환하는 구조. 비어 있으면 휴리스틱으로 채움."""

    model_config = ConfigDict(extra="ignore")

    display_name: str = ""
    email: str | None = None
    phone: str | None = None
    school: str | None = None
    career_summary: str | None = None
    consultant_memo_lines: list[str] = Field(default_factory=list)
    target_category_slug: str | None = None

    @field_validator("consultant_memo_lines", mode="before")
    @classmethod
    def _coerce_memo_lines(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str) and v.strip():
            return [v.strip()]
        if isinstance(v, list):
            out: list[str] = []
            for x in v:
                if isinstance(x, str) and (t := x.strip()):
                    out.append(t)
            return out
        return []


class LlmImportExtractResult(NamedTuple):
    """가져오기 LLM 한 번 시도 결과. status는 응답 헤더·진단용."""

    fields: StudentImportLlmFields | None
    status: str  # ok | no_model_response | bad_json | empty_input


def _strip_json_fence(raw: str) -> str:
    t = raw.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\s*```\s*$", "", t)
    return t.strip()


def _parse_llm_student_json(raw: str | None) -> StudentImportLlmFields | None:
    if not raw or not raw.strip():
        return None
    cleaned = _strip_json_fence(raw.strip())

    idx = cleaned.find("{")
    if idx >= 0:
        try:
            dec = json.JSONDecoder()
            data, _ = dec.raw_decode(cleaned, idx)
            if isinstance(data, dict):
                return StudentImportLlmFields.model_validate(data)
        except (json.JSONDecodeError, ValueError) as e:
            logger.debug("컨설턴트 import LLM raw_decode 실패: %s", e)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning("컨설턴트 import LLM JSON 파싱 실패: %s", e)
        return None
    if not isinstance(data, dict):
        return None
    try:
        return StudentImportLlmFields.model_validate(data)
    except Exception as e:
        logger.warning("컨설턴트 import LLM 필드 검증 실패: %s", e)
        return None


def llm_extract_student_import_with_meta(
    resume_text: str,
    career_summary: str | None,
    dashboard_category_hint: str | None,
    profile_display_name: str | None,
) -> LlmImportExtractResult:
    """
    내장 LLM으로 이력서를 읽고 학생 레코드에 넣을 값을 정리합니다.
    OpenAI 키가 있으면 JSON 모드(temperature 낮음), 없으면 Ollama 일반 완성.
    """
    rt = (resume_text or "").strip()
    cs = (career_summary or "").strip()
    if not rt and not cs:
        return LlmImportExtractResult(None, "empty_input")

    resume_chunk = rt[:_MAX_INPUT_RESUME]
    if len(rt) > _MAX_INPUT_RESUME:
        resume_chunk += "\n\n[…이하 생략…]"

    summary_chunk = cs[:_MAX_INPUT_SUMMARY] if cs else "(없음)"

    slugs = ", ".join(sorted(CATEGORY_LABEL.keys()))
    hint_line = (
        f"대시보드에서 사용자가 고른 직군 힌트: {dashboard_category_hint}"
        if dashboard_category_hint
        else "대시보드 직군 힌트: 없음"
    )
    prof_name = (profile_display_name or "").strip() or "(없음)"

    use_openai_json = bool(settings.openai_api_key)
    system = (
        "당신은 채용·이력 컨설턴트 어시스턴트입니다. 주어진 이력서/경력 텍스트만 근거로 "
        "필드를 채웁니다. 문서에 없는 정보는 반드시 null 또는 빈 문자열로 두고 추측하지 않습니다. "
        "한국어로 작성합니다. "
    )
    if use_openai_json:
        system += "응답은 반드시 하나의 JSON 객체만 출력하세요(설명·마크다운 금지)."
    else:
        system += "응답은 JSON 객체 하나만 출력하고 다른 설명·마크다운은 넣지 마세요."

    user = f"""다음 텍스트를 읽고 컨설턴트 DB 학생 레코드에 넣을 값을 정리하세요.

규칙:
- display_name: 문서에 나온 지원자 실명(한글/영문)만. 없으면 "".
  절대 "주소","연락처","성명","이름","학력","경력" 같은 란 제목만 넣지 마세요.
- email, phone: 문서에 명시된 것만. 없으면 null.
- school: 최종 학력·교육기관·부트캠프 등을 한 줄로(중복 문장 없이). 없으면 null.
- career_summary: 핵심 경력·역량·지향을 3~7문장의 하나의 문단으로. 이력서 본문 전체를 복붙하지 말 것.
- consultant_memo_lines: 컨설턴트용 짧은 메모 0~5줄(주요 스킬·도메인·포지션). 중복 줄 금지.
- target_category_slug: 아래 중 이력과 가장 맞는 하나만. 애매하면 힌트를 참고.
  허용 값만: {slugs}
  없으면 null.

{hint_line}
프로필에 이미 있는 표시명(참고, 비어 있으면 무시): {prof_name}

--- 경력 요약(보조) ---
{summary_chunk}

--- 이력서 본문 ---
{resume_chunk}
"""

    raw = chat_completion(
        system,
        user,
        temperature=0.15,
        json_mode=use_openai_json,
    )
    if not raw or not str(raw).strip():
        logger.warning(
            "컨설턴트 가져오기 LLM: 응답 없음. OpenAI 키 또는 Ollama(%s, 모델=%s, OLLAMA_ENABLED=%s)를 확인하세요.",
            settings.ollama_base_url,
            settings.ollama_model,
            settings.ollama_enabled,
        )
        return LlmImportExtractResult(None, "no_model_response")

    parsed = _parse_llm_student_json(raw)
    if parsed is None:
        logger.warning(
            "컨설턴트 가져오기 LLM: JSON 파싱 실패. 응답 앞부분: %r",
            raw[:400].replace("\n", " "),
        )
        return LlmImportExtractResult(None, "bad_json")

    clean_dn = sanitize_display_name_candidate(parsed.display_name)
    parsed = parsed.model_copy(update={"display_name": clean_dn or ""})

    return LlmImportExtractResult(parsed, "ok")


def llm_extract_student_import_fields(
    resume_text: str,
    career_summary: str | None,
    dashboard_category_hint: str | None,
    profile_display_name: str | None,
) -> StudentImportLlmFields | None:
    """호환용: 필드만 필요할 때."""
    return llm_extract_student_import_with_meta(
        resume_text,
        career_summary,
        dashboard_category_hint,
        profile_display_name,
    ).fields


def sanitize_llm_slug(slug: str | None) -> str | None:
    if not slug or not isinstance(slug, str):
        return None
    t = slug.strip().lower().replace("-", "_")
    if t in CATEGORY_LABEL:
        return t
    # 흔한 오타/별칭
    aliases = {
        "data_analytics": "data_analyst",
        "analyst": "data_analyst",
        "ml_engineer": "ai_engineer",
        "ai": "ai_engineer",
        "be": "backend_developer",
        "backend": "backend_developer",
    }
    return aliases.get(t)
