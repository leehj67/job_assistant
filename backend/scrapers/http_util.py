import logging
import time

import httpx

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


def is_transient_http_error(exc: BaseException) -> bool:
    """타임아웃·연결 끊김·일시적 5xx·429 등 재시도 가치가 있는 오류."""
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(
        exc,
        (
            httpx.ConnectError,
            httpx.ReadError,
            httpx.WriteError,
            httpx.RemoteProtocolError,
            httpx.NetworkError,
        ),
    ):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code in (408, 425, 429, 500, 502, 503, 504)
    return False


def get_text(
    url: str,
    params: dict | None = None,
    *,
    timeout: float = 45.0,
    max_retries: int = 3,
    base_delay_sec: float = 0.75,
) -> str:
    """
    GET 후 텍스트 반환. ``max_retries``회까지 일시적 오류 시 지수 백오프 후 재시도.
    """
    last: BaseException | None = None
    for attempt in range(1, max_retries + 1):
        try:
            r = httpx.get(
                url,
                params=params,
                headers=DEFAULT_HEADERS,
                timeout=timeout,
                follow_redirects=True,
            )
            r.raise_for_status()
            r.encoding = r.encoding or "utf-8"
            return r.text
        except Exception as e:
            last = e
            if attempt < max_retries and is_transient_http_error(e):
                wait = base_delay_sec * (2 ** (attempt - 1))
                logger.warning(
                    "HTTP GET 재시도 %s/%s %.1fs 후: %s — %s",
                    attempt,
                    max_retries,
                    wait,
                    url[:120],
                    e,
                )
                time.sleep(wait)
                continue
            raise
