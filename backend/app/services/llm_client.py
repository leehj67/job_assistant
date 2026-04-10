"""OpenAI 우선, 미설정 시 Ollama(OpenAI 호환 /v1) 로컬 Llama."""

from __future__ import annotations

import logging

import httpx
from openai import APIConnectionError, OpenAI

from app.config import settings

logger = logging.getLogger(__name__)


def chat_completion(
    system: str,
    user: str,
    *,
    temperature: float = 0.4,
    json_mode: bool = False,
) -> str | None:
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    if settings.openai_api_key:
        try:
            client = OpenAI(api_key=settings.openai_api_key)
            kwargs: dict = {
                "model": settings.openai_model,
                "messages": messages,
                "temperature": temperature,
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            r = client.chat.completions.create(**kwargs)
            return r.choices[0].message.content
        except Exception as e:
            logger.warning("OpenAI 호출 실패, Ollama 폴백 시도: %s", e)

    if not settings.ollama_enabled:
        logger.warning(
            "LLM 사용 불가: OPENAI_API_KEY 없음이고 OLLAMA_ENABLED=false 입니다. "
            "컨설턴트 가져오기 LLM은 동작하지 않습니다."
        )
        return None

    try:
        client = OpenAI(
            base_url=settings.ollama_base_url.rstrip("/"),
            api_key="ollama",
        )
        r = client.chat.completions.create(
            model=settings.ollama_model,
            messages=messages,
            temperature=temperature,
        )
        return r.choices[0].message.content
    except APIConnectionError:
        logger.warning(
            "Ollama에 연결할 수 없습니다. %s 에 모델 %s 가 떠 있는지 확인하세요.",
            settings.ollama_base_url,
            settings.ollama_model,
        )
    except Exception as e:
        logger.warning("Ollama 호출 실패: %s", e)
    return None


def ollama_health() -> bool:
    if not settings.ollama_enabled:
        return False
    try:
        base = settings.ollama_base_url.rstrip("/").replace("/v1", "")
        r = httpx.get(f"{base}/api/tags", timeout=3.0)
        return r.status_code == 200
    except Exception:
        return False
