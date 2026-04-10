"""PDF에서 텍스트 추출 (텍스트 레이어 기준; 스캔본은 OCR 미적용)."""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader


def extract_text_from_pdf_bytes(data: bytes) -> str:
    if not data:
        return ""
    try:
        reader = PdfReader(BytesIO(data), strict=False)
    except Exception:
        return ""
    parts: list[str] = []
    try:
        pages = reader.pages
    except Exception:
        return ""
    for page in pages:
        try:
            t = page.extract_text()
        except Exception:
            t = ""
        if t:
            parts.append(t)
    return "\n".join(parts).strip()
