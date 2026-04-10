from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./find_my_job.db"
    cors_origins: str = (
        "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,"
        "http://127.0.0.1:3001"
    )

    # 이미지 OCR (EasyOCR: pip install easyocr)
    ocr_enabled: bool = True
    ocr_max_images_per_job: int = 3
    ocr_min_width: int = 140
    ocr_min_height: int = 100
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    # OpenAI 미설정 시 로컬 Llama (Ollama 권장: ollama serve 후 기본 http://127.0.0.1:11434/v1 )
    ollama_enabled: bool = True
    ollama_base_url: str = "http://127.0.0.1:11434/v1"
    # 로컬에 `llama3.2` 태그가 없을 수 있음 — `ollama list`에 맞춰 .env의 OLLAMA_MODEL 권장
    ollama_model: str = "llama3:latest"

    # 선택: KLUE 토크나이저로 서브워드 후보 (transformers+torch 필요, 무거움)
    kobert_tokenizer_enabled: bool = False

    # 최초 기동 시 데모 시드(더미) 적재 — 실서비스 수집만 쓸 때는 false
    seed_demo_on_empty: bool = True

    # 대시보드 → 컨설턴트 학생 가져오기 시 LLM으로 필드 정리 (false면 규칙·휴리스틱만)
    consultant_import_llm: bool = True


settings = Settings()
