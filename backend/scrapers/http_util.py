import httpx

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


def get_text(url: str, params: dict | None = None, timeout: float = 45.0) -> str:
    r = httpx.get(url, params=params, headers=DEFAULT_HEADERS, timeout=timeout, follow_redirects=True)
    r.raise_for_status()
    r.encoding = r.encoding or "utf-8"
    return r.text
