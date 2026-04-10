"""단계별 키워드 파이프라인 스모크 테스트."""

from app.services.keyword_pipeline import (
    run_full_pipeline,
    run_kiwi_nouns,
    run_rake,
    run_yake_bilingual,
)
from app.services.llm_client import ollama_health

def main() -> None:
    t = "Python SQL data analysis machine learning experience communication"
    print("1 RAKE sample:", run_rake(t)[:5])
    print("2 YAKE count:", len(run_yake_bilingual(t)))
    print("3 Kiwi (KO):", run_kiwi_nouns("Python SQL 데이터 분석 경험")[:10])
    print("4 Ollama reachable:", ollama_health())
    meta = {
        "requirements": ["SQL required"],
        "preferred": ["Python preferred"],
        "responsibilities": ["ETL pipeline"],
    }
    p = run_full_pipeline(full_text=t + "\nextra context", job_metadata=meta)
    print("5 stage1 counts:", p["stage1"]["counts"])
    print("6 stage2 error:", p["stage2"].get("error"))
    llm = p["stage2"].get("llm")
    print("7 stage2 llm:", "yes" if llm else "no")
    print("OK")


if __name__ == "__main__":
    main()
