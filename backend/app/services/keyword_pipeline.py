"""1단계: RAKE / YAKE / 형태소(한국어 Kiwi·선택 KoBERT 토큰) 광범위 후보.
2단계: Ollama(OpenAI 호환)·OpenAI로 기술 키워드 정제·정규화·카테고리·섹션 분류."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.config import settings
from app.services.llm_client import chat_completion, ollama_health

logger = logging.getLogger(__name__)

# --- NLTK (RAKE) ---
_nltk_ready = False


def _ensure_nltk() -> None:
    global _nltk_ready
    if _nltk_ready:
        return
    import nltk

    for pkg in ("stopwords", "punkt", "punkt_tab"):
        try:
            nltk.data.find(f"tokenizers/{pkg}" if "punkt" in pkg else f"corpora/{pkg}")
        except LookupError:
            try:
                if pkg == "stopwords":
                    nltk.download("stopwords", quiet=True)
                elif pkg == "punkt":
                    nltk.download("punkt", quiet=True)
                elif pkg == "punkt_tab":
                    nltk.download("punkt_tab", quiet=True)
            except Exception as e:
                logger.debug("nltk download %s: %s", pkg, e)
    _nltk_ready = True


def run_rake(text: str, max_phrases: int = 80) -> list[str]:
    """RAKE (영문·혼합 문단에서 구문 후보). 한국어 전용 문단에는 빈 결과일 수 있음."""
    if not (text or "").strip():
        return []
    try:
        _ensure_nltk()
        from rake_nltk import Rake

        r = Rake(max_length=8)
        r.extract_keywords_from_text(text)
        phrases = r.get_ranked_phrases()
        return phrases[:max_phrases]
    except Exception as e:
        logger.warning("RAKE 실패: %s", e)
        return []


def run_yake(text: str, lang: str, top: int = 60, ngram: int = 3) -> list[tuple[str, float]]:
    if not (text or "").strip():
        return []
    try:
        import yake

        lang = lang if lang in ("ko", "en", "fr", "de", "es") else "en"
        kw = yake.KeywordExtractor(
            lan=lang,
            n=ngram,
            dedupLim=0.7,
            top=top,
            features=None,
        )
        return kw.extract_keywords(text)
    except Exception as e:
        logger.warning("YAKE(%s) 실패: %s", lang, e)
        return []


def run_yake_bilingual(text: str, top_each: int = 50) -> list[dict[str, Any]]:
    """한국어·영어 YAKE 각각 실행 후 병합(점수는 언어별 상대값)."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for lang in ("ko", "en"):
        for phrase, score in run_yake(text, lang, top=top_each):
            key = phrase.strip().lower()
            if len(key) < 2 or key in seen:
                continue
            seen.add(key)
            out.append({"phrase": phrase.strip(), "score": float(score), "source": f"yake_{lang}"})
    return out


def run_kiwi_nouns(text: str, max_tokens: int = 120) -> list[str]:
    """Kiwi 형태소 분석: 명사·외래어 토큰 후보."""
    if not (text or "").strip():
        return []
    try:
        from kiwipiepy import Kiwi

        kiwi = Kiwi()
        toks: list[str] = []
        for tok in kiwi.tokenize(text):
            tag = tok.tag
            if tag.startswith("N") or tag == "SL" or tag.startswith("SH"):
                w = tok.form.strip()
                if len(w) >= 2 and w not in toks:
                    toks.append(w)
            if len(toks) >= max_tokens:
                break
        return toks
    except Exception as e:
        logger.warning("Kiwi 형태소 실패: %s", e)
        return []


def run_kobert_subword_candidates(text: str, max_pieces: int = 80) -> list[str]:
    """선택: KLUE/BERT 토크나이저로 서브워드 후보(환경에 transformers+torch 있을 때만)."""
    if not settings.kobert_tokenizer_enabled:
        return []
    try:
        from transformers import AutoTokenizer

        tok = AutoTokenizer.from_pretrained("klue/bert-base")
        chunk = text[:2000]
        ids = tok.encode(chunk, add_special_tokens=False)
        pieces = []
        for tid in ids[: max_pieces * 2]:
            p = tok.convert_ids_to_tokens(tid)
            if p and p not in ("[UNK]", "##"):
                p = p.replace("##", "").strip()
                if len(p) >= 2 and p.isascii() or re.search(r"[가-힣]", p):
                    pieces.append(p)
        # 중복 제거 순서 유지
        seen = set()
        out = []
        for x in pieces:
            k = x.lower()
            if k not in seen:
                seen.add(k)
                out.append(x)
            if len(out) >= max_pieces:
                break
        return out
    except Exception as e:
        logger.debug("KoBERT/토크나이저 후보 생략: %s", e)
        return []


def combine_stage1_candidates(
    *,
    rake_phrases: list[str],
    yake_items: list[dict[str, Any]],
    kiwi_tokens: list[str],
    kobert_pieces: list[str],
) -> list[str]:
    """광범위 후보 단일 리스트(순서: rake, yake, kiwi, kobert)."""
    combined: list[str] = []
    seen: set[str] = set()

    def add(s: str) -> None:
        s = s.strip()
        if len(s) < 2:
            return
        k = s.lower()
        if k in seen:
            return
        seen.add(k)
        combined.append(s)

    for p in rake_phrases:
        add(p)
    for it in yake_items:
        add(it.get("phrase", ""))
    for t in kiwi_tokens:
        add(t)
    for t in kobert_pieces:
        add(t)
    return combined


STAGE2_SYSTEM_PROMPT = """당신은 채용 공고에서 기술 키워드를 정제하는 도우미입니다.
입력은 1단계에서 넓게 뽑은 후보 목록과, 공고의 섹션별 원문(필수/우대/업무)입니다.

반드시 JSON만 출력하세요. 마크다운 코드펜스 금지.

규칙:
1) 기술·도구·언어·프레임워크·인프라·도메인(데이터/금융 등)만 keywords에 넣습니다.
2) 순수 일반 표현("우대사항", "지원자격" 같은 제목만), 빈 섹션 헤더는 넣지 않습니다.
3) soft_skill은 "커뮤니케이션", "문제 해결" 등 비기술 역량만 넣습니다.
4) keywords 각 항목:
   - normalized: 영문 스네이크케이스 또는 소문자 통일 (예: python, sql, power_bi, machine_learning)
   - category: language | framework | tool | soft_skill | domain (soft_skill은 keywords에 넣지 말고 soft_skills 배열로)
   - category가 soft_skill이면 keywords가 아니라 soft_skills로 보냄
5) section: required | preferred | work | unknown (원문 섹션과 문맥으로 추정)
6) 표기 통합: Python/python/파이썬 → normalized "python", Power BI/PowerBI → power_bi

출력 스키마:
{
  "keywords": [
    {"normalized": "python", "display_ko": "Python", "category": "language", "section": "preferred", "confidence": 0.9}
  ],
  "soft_skills": [
    {"phrase": "커뮤니케이션", "section": "preferred"}
  ],
  "noise_removed_examples": ["우대사항", "지원자격"]
}
"""


def _truncate(s: str, n: int) -> str:
    s = s.strip()
    return s if len(s) <= n else s[: n - 3] + "..."


def run_stage2_llm(
    *,
    stage1_phrases: list[str],
    sectioned_context: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Ollama 또는 OpenAI. 실패 시 (None, reason)."""
    body = {
        "candidates_stage1": stage1_phrases[:200],
        "sectioned_job_text": _truncate(sectioned_context, 12000),
    }
    user = json.dumps(body, ensure_ascii=False)
    raw = chat_completion(STAGE2_SYSTEM_PROMPT, user)
    if not raw:
        reason = "LLM 응답 없음(OpenAI 미설정·Ollama 미기동 시 발생)"
        if not ollama_health():
            reason += " — Ollama /api/tags 미응답"
        return None, reason
    try:
        text = raw.strip()
        if "```" in text:
            m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
            if m:
                text = m.group(1).strip()
        data = json.loads(text)
        if not isinstance(data, dict):
            return None, "LLM JSON 루트가 객체가 아님"
        return data, None
    except json.JSONDecodeError as e:
        logger.warning("LLM JSON 파싱 실패: %s", e)
        return None, f"JSON 파싱 실패: {e}"


def build_sectioned_context(job_metadata: dict[str, Any] | None) -> str:
    m = job_metadata if isinstance(job_metadata, dict) else {}
    parts = []
    for label, key in (
        ("[필수·자격]", "requirements"),
        ("[우대]", "preferred"),
        ("[담당업무]", "responsibilities"),
    ):
        lines = m.get(key) or []
        if not isinstance(lines, list):
            continue
        blob = "\n".join(x for x in lines if isinstance(x, str) and x.strip())
        if blob:
            parts.append(f"{label}\n{blob}")
    hints = m.get("listing_hints") or []
    if isinstance(hints, list) and hints:
        parts.append("[기타]\n" + "\n".join(str(x) for x in hints[:30]))
    return "\n\n".join(parts)


def run_full_pipeline(
    *,
    full_text: str,
    job_metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    rake_phrases = run_rake(full_text)
    yake_items = run_yake_bilingual(full_text)
    kiwi_tokens = run_kiwi_nouns(full_text)
    kobert_pieces = run_kobert_subword_candidates(full_text)
    combined = combine_stage1_candidates(
        rake_phrases=rake_phrases,
        yake_items=yake_items,
        kiwi_tokens=kiwi_tokens,
        kobert_pieces=kobert_pieces,
    )

    sectioned = build_sectioned_context(job_metadata)
    stage2, err = run_stage2_llm(stage1_phrases=combined, sectioned_context=sectioned + "\n\n" + _truncate(full_text, 4000))

    return {
        "stage1": {
            "rake_phrases": rake_phrases,
            "yake": yake_items,
            "kiwi_morph_tokens": kiwi_tokens,
            "kobert_subword_candidates": kobert_pieces,
            "combined_candidates": combined,
            "counts": {
                "rake": len(rake_phrases),
                "yake": len(yake_items),
                "kiwi": len(kiwi_tokens),
                "kobert": len(kobert_pieces),
                "combined": len(combined),
            },
        },
        "stage2": {
            "llm": stage2,
            "error": err,
            "ollama_reachable": ollama_health(),
            "openai_configured": bool(settings.openai_api_key),
        },
    }
