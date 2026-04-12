from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine, SessionLocal
from app.migrate_sqlite import run_sqlite_migrations
from app.routers import consultant, routes
from app.seed import seed_if_empty


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    run_sqlite_migrations()
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
    yield


app = FastAPI(title="Find My Job API", version="0.1.0", lifespan=lifespan)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
# LAN·로컬에서 프론트와 API 포트가 다를 때 브라우저 직접 호출 CORS 통과
_cors_origin_regex = (
    r"^https?://(localhost|127\.0\.0\.1|\[::1\]|::1)(:\d+)?$"
    r"|^https?://192\.168\.\d{1,3}\.\d{1,3}(:\d+)?$"
    r"|^https?://10\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?$"
    r"|^https?://172\.(1[6-9]|2[0-9]|3[01])\.\d{1,3}\.\d{1,3}(:\d+)?$"
    r"|^https?://[a-zA-Z0-9.-]+\.local(:\d+)?$"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_origin_regex=_cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Consultant-Import-Llm"],
)

app.include_router(routes.router, prefix="/api")
app.include_router(consultant.router, prefix="/api")


def _registered_path_methods() -> dict[str, list[str]]:
    """진단용: 현재 프로세스에 실제로 올라간 /api 라우트."""
    out: dict[str, list[str]] = {}
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not path or not methods or not path.startswith("/api"):
            continue
        out.setdefault(path, []).extend(sorted(m for m in methods if m))
    for path in out:
        out[path] = sorted(set(out[path]))
    return out


@app.get("/")
def root():
    """브라우저에서 루트만 열면 이 JSON이 보입니다. API는 /api 아래입니다."""
    caps = _registered_path_methods()
    post_collect = caps.get("/api/applicant/collect-suggestions", [])
    return {
        "service": "find_my_job",
        "message_ko": "정상 동작 중입니다. 데이터 API는 /api 경로를 사용하세요. Swagger는 /docs 입니다.",
        "docs": "/docs",
        "openapi_json": "/openapi.json",
        "api_health": "/api/health",
        "api_overview": "/api/overview",
        "hint": "브라우저에서 http://127.0.0.1:8000/docs 또는 http://127.0.0.1:8000/api/health 를 열어 보세요.",
        "diagnostics": {
            "post_collect_suggestions_registered": "POST" in post_collect,
            "if_false_restart_backend": "이 프로젝트 backend 폴더에서 uvicorn을 다시 띄우세요. 오래된 프로세스는 POST /api/applicant/collect-suggestions 가 없습니다.",
        },
    }
