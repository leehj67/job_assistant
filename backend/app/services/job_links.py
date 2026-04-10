"""공고 원본(목록) URL — DB 컬럼 또는 설명 텍스트에 포함된 `상세: https://...` 에서 복구."""

from __future__ import annotations

import re

from app.models import Job

_DETAIL_URL_RE = re.compile(r"상세:\s*(https?://[^\s]+)")


def resolve_job_listing_url(job: Job) -> str | None:
    u = (job.source_url or "").strip()
    if u:
        return u
    m = _DETAIL_URL_RE.search(job.description or "")
    return m.group(1) if m else None
