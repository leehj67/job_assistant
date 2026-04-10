"""사람인 채용 검색 결과(키워드) HTML 파싱.

사이트 구조 변경 시 셀렉터 수정 필요. robots.txt·이용약관 준수는 운영자 책임."""

from __future__ import annotations

from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

from scrapers.http_util import get_text

BASE = "https://www.saramin.co.kr"


def fetch_listings(keyword: str, page: int = 1) -> list[dict]:
    html = get_text(
        f"{BASE}/zf_user/search/recruit",
        params={"searchword": keyword, "recruitPage": page},
    )
    return parse_recruit_html(html, keyword)


def parse_recruit_html(html: str, keyword: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    for item in soup.select("div.item_recruit"):
        ja = item.select_one('a[href*="relay/view"]')
        if not ja or not ja.get("href"):
            continue
        href = urljoin(BASE, ja["href"])
        q = parse_qs(urlparse(href).query)
        rid = (q.get("rec_idx") or [None])[0]
        if not rid:
            continue
        title = ja.get_text(strip=True)
        corp_a = item.select_one('a[href*="company-info/view"]')
        company = corp_a.get_text(strip=True) if corp_a else ""
        loc_a = item.select_one('a[href*="/area-recruit/area-list/area/"]')
        location = loc_a.get_text(strip=True) if loc_a else None
        # 키워드 태그 일부를 설명에 포함
        tags = [t.get_text(strip=True) for t in item.select("a[href*='job-category?cat_kewd']")[:8]]
        desc = f"검색키워드: {keyword}\n공고키워드: {', '.join(tags)}\n상세: {href}"
        out.append(
            {
                "external_id": rid,
                "title": title,
                "company": company or "(회사명 미상)",
                "description": desc,
                "location": location,
                "search_keyword": keyword,
                "source_url": href,
            }
        )
    return out
