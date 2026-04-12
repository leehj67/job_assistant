"""이미지 URL/바이트에서 한글·영어 OCR (EasyOCR). 미설치 시 조용히 비활성화."""

from __future__ import annotations

import io
import logging
import time

import httpx
from PIL import Image

from app.config import settings

logger = logging.getLogger(__name__)

_reader_singleton: object | None = None  # None=미시도, False=실패, Reader=성공


def _ocr_init_transient_error(exc: BaseException) -> bool:
    """Windows에서 모델 temp.zip 잠금(WinError 32) 등 일시적 실패."""
    win = getattr(exc, "winerror", None)
    if win == 32:
        return True
    msg = str(exc).lower()
    return "being used by another process" in msg or "temp.zip" in msg


def _get_reader():
    global _reader_singleton
    if _reader_singleton is not None:
        return _reader_singleton if _reader_singleton is not False else None
    if not settings.ocr_enabled:
        _reader_singleton = False
        return None
    try:
        import easyocr  # noqa: WPS433
    except ModuleNotFoundError as e:
        logger.warning("easyocr 미설치(OCR 비활성): %s", e)
        _reader_singleton = False
        return None

    for attempt in range(3):
        try:
            _reader_singleton = easyocr.Reader(["ko", "en"], gpu=False, verbose=False)
            return _reader_singleton
        except Exception as e:
            if _ocr_init_transient_error(e) and attempt < 2:
                logger.warning(
                    "EasyOCR 초기화 잠금/경합(재시도 %s/3): %s", attempt + 1, e
                )
                time.sleep(1.5)
                continue
            logger.warning("EasyOCR 초기화 실패(OCR 비활성): %s", e)
            _reader_singleton = False
            return None


def ocr_available() -> bool:
    return _get_reader() is not None


def ocr_image_bytes(data: bytes) -> str:
    r = _get_reader()
    if not r:
        return ""
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
        w, h = img.size
        if w < settings.ocr_min_width or h < settings.ocr_min_height:
            return ""
        lines = r.readtext(img)
        parts = [t[1] for t in lines if t and len(t) > 1 and t[1].strip()]
        return "\n".join(parts).strip()
    except Exception as e:
        logger.debug("OCR 실패: %s", e)
        return ""


def ocr_image_url(url: str, timeout: float = 25.0) -> str:
    if not url.startswith("http"):
        url = "https:" + url if url.startswith("//") else url
    try:
        r = httpx.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
                "Referer": "https://www.jobkorea.co.kr/",
            },
            timeout=timeout,
            follow_redirects=True,
        )
        r.raise_for_status()
        return ocr_image_bytes(r.content)
    except Exception as e:
        logger.debug("이미지 다운로드/OCR URL 실패 %s: %s", url[:80], e)
        return ""
