# Find My Job Insight

채용 시장 **수요**(공고 기반 요구 역량)와 **관심**(검색·트렌드 지표)을 비교해, 교육기관과 취업준비생에게 **무엇을 가르치고 무엇을 공부할지** 방향을 제시하는 웹 서비스 MVP입니다.

## 문제 정의

- 교육기관은 어떤 강의를 열어야 시장과 맞는지 알기 어렵다.
- 취업준비생은 무엇을 준비해야 할지 방향을 잡기 어렵다.
- 특정 직군은 관심은 높지만 채용 수요가 적어 **과포화**가 발생하고, 반대로 수요는 높은데 준비 인원이 적은 분야도 있다.

본 서비스는 수요와 관심을 같은 축에서 비교해 **과포화 / 기회 / 안정 인기 / 비추천** 영역으로 나누고, 그에 맞는 교육·학습 전략 문장을 제공한다.

## 빠른 시작 (자동 설치)

처음 클론한 PC에서 Python·pip 패키지·(선택) OCR·NLTK·프론트 npm·(선택) Ollama와 기본 Llama 모델까지 한 번에 맞출 수 있습니다.

**Windows (PowerShell, 저장소 루트에서):**

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force   # 스크립트 실행이 막혀 있을 때만
.\scripts\setup.ps1
```

옵션: `-SkipOllama` (Ollama winget/pull 생략), `-SkipOcr` (EasyOCR 등 대용량 OCR 패키지 생략), `-SkipFrontend` (npm 생략).

**macOS / Linux:**

```bash
chmod +x scripts/setup.sh   # 최초 1회
./scripts/setup.sh
```

옵션: `--skip-ollama`, `--skip-ocr`, `--skip-frontend`.

설치 후에는 아래 **실행 방법**대로 백엔드·프론트를 각각 터미널에서 띄우면 됩니다. Ollama를 쓰는 경우 Windows에서는 트레이의 Ollama 앱이 떠 있어야 하며, `backend/.env`의 `OLLAMA_MODEL`은 `ollama list`에 나온 이름과 **정확히** 같아야 합니다(스크립트 기본 pull: `llama3:latest`).

## 프로그램이 동작하는 방식

1. **백엔드 (FastAPI, 기본 `127.0.0.1:8000`)** 가 SQLite에 채용 공고·트렌드·메타데이터를 저장하고, 수집·분석·추천 API를 제공합니다.
2. **프론트 (Next.js)** 는 브라우저에서 `/api/...` 로만 호출하고, `frontend/src/app/api/[...path]/route.ts`의 프록시가 동일 요청을 백엔드로 넘깁니다. 따라서 CORS 없이 로컬 개발이 가능합니다.
3. **AI 추천 문장** 은 `OPENAI_API_KEY`가 있으면 OpenAI를 쓰고, 없으면 Ollama(OpenAI 호환 `/v1`)로 로컬 Llama를 호출합니다. 둘 다 실패하면 규칙 기반 문장으로 폴백합니다 (`backend/app/services/llm_client.py`).
4. **OCR** 은 수집 시 상세+이미지 옵션을 켠 경우에만 EasyOCR로 이미지에서 텍스트를 붙입니다. 패키지가 없으면 해당 기능만 조용히 빠집니다 (`backend/app/services/ocr_service.py`).
5. **수집** 은 사람인·잡코리아 검색 HTML을 파싱해 DB에 적재합니다. 사이트 구조 변경 시 스크래퍼 수정이 필요할 수 있습니다.

**주요 URL (로컬):**

| 구분 | 주소 |
|------|------|
| 웹 UI | `http://localhost:3000` (또는 터미널에 표시된 포트) |
| API 문서 | http://127.0.0.1:8000/docs |
| LLM 상태 확인 | `GET http://127.0.0.1:8000/api/llm/status` |

## 서비스 대상

| 구분 | 대상 |
|------|------|
| 메인 | 학원·부트캠프·교육기관 운영자, 교육과정 기획자 |
| 서브 | 취업준비생, 직무 전환 준비자 |

## 핵심 기능 (MVP)

- **키워드 기반 채용 공고 수집**: 사람인·잡코리아 검색 결과 목록을 `POST /api/collect` 또는 대시보드 폼으로 가져와 DB에 저장 (소스+공고ID 중복 제외)
- 채용 공고 저장 및 직군·키워드별 통계
- 공고 텍스트에서 스킬 키워드 추출·정규화 (규칙 기반)
- 검색 트렌드용 시계열 데이터 저장·조회 (데모 트렌드 시드)
- 직군별 **수요 vs 관심** 격차 분석 및 4분류
- 학원용 / 취준생용 추천 문장 (**OpenAI → 없으면 Ollama 로컬 Llama → 없으면 규칙 기반**)
- 대시보드: 바 차트, 라인 차트, 수요·관심 비교 바 차트, 격차 카드

**주의:** 구직 사이트 HTML 구조는 수시로 바뀔 수 있으며, 이용약관·로봇 배제 정책을 반드시 확인한 뒤 합법적 범위에서 사용하세요.

**MVP 직군 범위:** 데이터 분석가, AI 엔지니어, 백엔드 개발자 (3종)

## AI가 개입하는 단계

1. **채용 공고 텍스트 분석** — 스킬 추출·정규화·그룹화 (현재는 규칙 기반 + 확장 훅; OpenAI로 교체 가능)
2. **키워드 구조화** — 프로그래밍 언어, 데이터 도구, AI/ML, 인프라 등 그룹 라벨
3. **트렌드 해석** — 수요·관심 격차에 따른 한 줄 해석 (`/api/analysis/interpret/{keyword}`)
4. **전략 추천 생성** — OpenAI API 키가 있으면 우선 사용, 없으면 **Ollama**(`OLLAMA_BASE_URL`, 기본 `http://127.0.0.1:11434/v1`)로 로컬 Llama, 둘 다 불가면 규칙 기반 문장

## 기술 스택

| 영역 | 사용 |
|------|------|
| 프론트엔드 | Next.js 15 (App Router), TypeScript, Tailwind CSS, Recharts |
| 백엔드 | FastAPI, SQLAlchemy, SQLite (MVP), httpx, BeautifulSoup |
| AI (선택) | OpenAI API 또는 Ollama 호환 엔드포인트 (`llama3:latest` 등) |

## 실행 방법

### 1. 백엔드

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- 최초 실행 시 SQLite DB가 생성되고, `SEED_DEMO_ON_EMPTY=true`(기본)이면 **데모 트렌드·샘플 공고**가 적재된다. 실데이터만 쓰려면 `.env`에 `SEED_DEMO_ON_EMPTY=false` 후 빈 DB로 시작한다.
- 로컬 Llama: [Ollama](https://ollama.com/) 설치 후 `ollama pull llama3:latest` (또는 `ollama list`에 맞는 태그) · Ollama 앱/서비스 실행(기본 11434). `OLLAMA_MODEL`은 pull한 이름과 일치해야 합니다.
- API 문서: http://127.0.0.1:8000/docs  
- 수집 API 예시: `POST /api/collect` — body에 `keywords`, `category`, `sources`, `max_pages`

### 2. 프론트엔드

```bash
cd frontend
copy .env.local.example .env.local
npm install
npm run dev
```

- 브라우저: `npm run dev` 실행 후 터미널에 나온 주소를 쓰면 됩니다. (보통 `http://localhost:3000`, 3000이 점유 중이면 `http://localhost:3001` 등으로 자동 변경)  
- **프록시:** `frontend/src/app/api/[...path]/route.ts`가 `/api/*` 요청을 백엔드(`BACKEND_URL` 또는 `NEXT_PUBLIC_API_URL`, 기본 `http://127.0.0.1:8000`)로 넘깁니다. 브라우저는 동일 출처 `/api/...`만 호출하면 됩니다.  
- **환경 변수:** `NEXT_PUBLIC_API_URL`에 `.../api` 까지 넣지 마세요. 끝에 `/api`가 붙어 있으면 `/api/api/...` 로 가서 FastAPI가 `{"detail":"Not Found"}` 를 반환할 수 있습니다. (코드에서 자동 제거 처리함)

## 환경 변수

루트 및 `backend/.env.example`, `frontend/.env.local.example` 참고.

- **외부 API 키는 저장소에 넣지 말 것.** `.env` / `.env.local`은 `.gitignore`에 포함됨.
- `OPENAI_API_KEY`는 선택 사항이다. 없으면 Ollama(로컬)로 추천 문장을 생성한다.
- `GET /api/llm/status` 로 OpenAI 설정 여부·Ollama 연결 가능 여부를 확인할 수 있다.

## 배포 주소

- 공모전 제출 시 여기에 실제 배포 URL을 적어 주세요. (예: Vercel + Render/Fly.io 등)
- 현재 저장소 기본값: _(로컬 데모)_

## 데모 화면

1. **메인 대시보드** (`/`) — 서비스 소개, 직군별 공고 수 바 차트, 기회·과포화 키워드 요약, 직군 링크  
2. **직군 상세** (`/category/data_analyst` 등) — 상위 역량, 관심도 라인 차트, 수요 vs 관심 비교, 격차 카드, 학원/취준 요약  
3. **교육기관 인사이트** (`/academy`) — 신규 강의·커리큘럼 관점 카드 + 추천 문장  
4. **취준생 인사이트** (`/jobseeker`) — 우선순위·과포화·유망 방향 + 추천 문장  

## 수집·OCR

- `POST /api/collect` — 키워드로 사람인·잡코리아 **검색 목록**을 가져와 저장합니다. 기본은 목록만(빠름).  
- **「상세 페이지 + 이미지 OCR」**을 켜면 각 공고 상세 HTML을 열어 이미지 URL 후보를 모은 뒤, **EasyOCR(ko+en)** 으로 텍스트를 붙입니다. (사이트가 JS로 본문을 그리면 이미지가 없을 수 있음.)  
- OCR 사용 시: `pip install easyocr opencv-python-headless` (용량 큼, 최초 실행 시 모델 다운로드). 미설치 시 목록·키워드 기반 분석만 수행합니다.

## 수집 파이프라인 (확장)

`backend/scrapers/` 에 사람인·잡코리아 등 **매크로/크롤러**를 연결할 수 있는 스텁과 `ScraperRunLog` 메타데이터 테이블이 있다.  
일일 배치에서 `persist_jobs`로 `jobs`에 적재하고, 동일한 분석 API를 재사용하면 된다.

## 라이선스

공모전·포트폴리오 용도로 자유롭게 수정해 사용할 수 있습니다.
