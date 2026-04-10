"""상세 페이지 HTML에서 본문 이미지 후보를 골라 OCR 텍스트를 덧붙입니다.

공고 본문이 이미지(스캔 공고)인 경우가 많아, 텍스트가 거의 없을 때 이미지에서 추출합니다."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.config import settings
from app.services.ocr_service import ocr_available, ocr_image_url
from scrapers.http_util import get_text

_SKIP_SUBSTR = (
    "logo",
    "icon",
    "banner",
    "loading",
    "btn_",
    "bul_",
    "/common/",
    "star",
    "spinner",
    "LogoImage",
    "saraminbanner",
    "adserver",
    "favicon",
)


def _abs_url(base: str, src: str) -> str:
    if not src:
        return ""
    return urljoin(base, src)


def extract_candidate_image_urls(html: str, page_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    seen: set[str] = set()
    out: list[str] = []
    for img in soup.find_all("img"):
        for attr in ("data-src", "src", "data-original"):
            src = img.get(attr)
            if not src or not isinstance(src, str):
                continue
            src = src.strip()
            if not re.search(r"\.(png|jpe?g|webp)(\?|$)", src, re.I):
                continue
            low = src.lower()
            if any(s in low for s in _SKIP_SUBSTR):
                continue
            full = _abs_url(page_url, src)
            if full and full not in seen:
                seen.add(full)
                out.append(full)
    # raw url in scripts (some SPAs)
    for m in re.finditer(
        r"https?://[^\s\"'<>]+\.(?:png|jpe?g|webp)",
        html,
        re.I,
    ):
        u = m.group(0)
        low = u.lower()
        if any(s in low for s in _SKIP_SUBSTR):
            continue
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def enrich_description_with_detail(
    *,
    detail_url: str,
    base_description: str,
    use_ocr: bool = True,
) -> str:
    """상세 HTML을 받아 본문 이미지 OCR을 description에 추가."""
    try:
        html = get_text(detail_url)
    except Exception:
        return base_description

    imgs = extract_candidate_image_urls(html, detail_url)
    if not imgs:
        return base_description

    ocr_parts: list[str] = []
    if use_ocr and ocr_available():
        for u in imgs[: settings.ocr_max_images_per_job]:
            txt = ocr_image_url(u)
            if txt and len(txt) > 15:
                ocr_parts.append(txt)

    if not ocr_parts:
        return base_description

    return (
        base_description
        + "\n\n[공고 관련 이미지 OCR · ko/en]\n"
        + "\n---\n".join(ocr_parts)
    )


def html_to_plain_text(html: str) -> str:
    """상세 페이지 HTML에서 본문 위주 텍스트만 추출 (메타데이터 파싱용)."""
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "noscript", "svg", "iframe"]):
        t.decompose()
    candidates = soup.select(
        "main, article, #recruit_info, .user_content, .artView, .viewWrapper, "
        "[class*='Viewer'], [class*='Detail'], .detail-view, .tb_row"
    )
    root = candidates[0] if candidates else (soup.body or soup)
    text = root.get_text("\n", strip=True)
    lines: list[str] = []
    prev_empty = False
    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            if not prev_empty:
                lines.append("")
            prev_empty = True
        else:
            lines.append(s)
            prev_empty = False
    return "\n".join(lines).strip()


def gather_recruit_text_for_parsing(
    *,
    detail_url: str,
    preamble: str = "",
    use_ocr: bool = True,
) -> str:
    """상세 URL에서 본문 텍스트(+선택 OCR)를 모아 한 덩어리로 반환. DB 저장용이 아님."""
    preamble = (preamble or "").strip()
    try:
        html = get_text(detail_url)
    except Exception:
        return preamble
    plain = html_to_plain_text(html)
    imgs = extract_candidate_image_urls(html, detail_url)
    ocr_parts: list[str] = []
    if use_ocr and ocr_available():
        for u in imgs[: settings.ocr_max_images_per_job]:
            txt = ocr_image_url(u)
            if txt and len(txt) > 15:
                ocr_parts.append(txt)
    chunks: list[str] = []
    if preamble:
        chunks.append(preamble)
    if plain:
        chunks.append(plain)
    if ocr_parts:
        chunks.append("[이미지 OCR]\n" + "\n---\n".join(ocr_parts))
    return "\n\n".join(chunks)
