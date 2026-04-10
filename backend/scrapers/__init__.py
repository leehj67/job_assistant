"""채용 사이트 수집 어댑터 (사람인/잡코리아 등 매크로·크롤러 연동 지점).

실제 매크로/셀레니움 연동 시 `run_source`에서 HTML/JSON을 받아 `persist_jobs`로 저장합니다.
"""

from .base import ScraperContext, run_demo_stub

__all__ = ["ScraperContext", "run_demo_stub"]
