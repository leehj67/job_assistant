"""잡코리아 통합검색(키워드) HTML 파싱.

Next/리스트 구조 변경 시 수정 필요."""

from __future__ import annotations

import re
from collections import defaultdict
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scrapers.http_util import get_text

BASE = "https://www.jobkorea.co.kr"


def fetch_listings(keyword: str, page: int = 1) -> list[dict]:
    html = get_text(
        f"{BASE}/Search/",
        params={"stext": keyword, "Page_No": page},
    )
    return parse_search_html(html, keyword)


def parse_search_html(html: str, keyword: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    by_id: dict[str, list[str]] = defaultdict(list)
    href_by_id: dict[str, str] = {}
    for a in soup.select('a[href*="/Recruit/GI_Read/"]'):
        raw = a.get("href", "")
        m = re.search(r"/Recruit/GI_Read/(\d+)", raw)
        if not m:
            continue
        gid = m.group(1)
        txt = a.get_text(strip=True)
        if txt:
            by_id[gid].append(txt)
        href = urljoin(BASE, raw.split("&")[0])
        href_by_id.setdefault(gid, href)

    out: list[dict] = []
    for gid, texts in by_id.items():
        title = max(texts, key=len) if texts else ""
        company = ""
        if len(texts) >= 2:
            company = min(texts, key=len)
        elif len(texts) == 1:
            company = ""
        href = href_by_id.get(gid, f"{BASE}/Recruit/GI_Read/{gid}")
        desc = f"검색키워드: {keyword}\n상세: {href}"
        if not title:
            continue
        out.append(
            {
                "external_id": gid,
                "title": title,
                "company": company or "(회사명 미상)",
                "description": desc,
                "location": None,
                "search_keyword": keyword,
                "source_url": href,
            }
        )
    return out
