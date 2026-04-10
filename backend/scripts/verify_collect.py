"""수집 API 스모크 테스트 (네트워크 필요)."""

from fastapi.testclient import TestClient

from app.main import app

with TestClient(app) as c:
    r = c.post(
        "/api/collect",
        json={
            "keywords": ["Python"],
            "category": "data_analyst",
            "sources": ["jobkorea"],
            "max_pages": 1,
            "fetch_detail": False,
        },
    )
    print("status", r.status_code)
    print(r.json())
