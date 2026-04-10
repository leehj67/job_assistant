"""키워드 정규화 및 스킬 그룹 매핑 (MVP: 규칙 기반, 추후 AI 확장)."""

import re
from typing import Literal

SkillGroup = Literal[
    "language",
    "data_tool",
    "ai_ml",
    "collab",
    "soft_qual",
    "infra",
    "framework",
]

_ALIASES: dict[str, tuple[str, SkillGroup]] = {
    "python": ("Python", "language"),
    "파이썬": ("Python", "language"),
    "sql": ("SQL", "data_tool"),
    "엑셀": ("Excel", "data_tool"),
    "excel": ("Excel", "data_tool"),
    "tableau": ("Tableau", "data_tool"),
    "태블로": ("Tableau", "data_tool"),
    "power bi": ("Power BI", "data_tool"),
    "powerbi": ("Power BI", "data_tool"),
    "pandas": ("Pandas", "data_tool"),
    "판다스": ("Pandas", "data_tool"),
    "머신러닝": ("머신러닝", "ai_ml"),
    "machine learning": ("머신러닝", "ai_ml"),
    "ml": ("머신러닝", "ai_ml"),
    "딥러닝": ("딥러닝", "ai_ml"),
    "deep learning": ("딥러닝", "ai_ml"),
    "dl": ("딥러닝", "ai_ml"),
    "etl": ("ETL", "data_tool"),
    "docker": ("Docker", "infra"),
    "도커": ("Docker", "infra"),
    "fastapi": ("FastAPI", "framework"),
    "spring": ("Spring", "framework"),
    "스프링": ("Spring", "framework"),
    "pytorch": ("PyTorch", "ai_ml"),
    "tensorflow": ("TensorFlow", "ai_ml"),
    "kubernetes": ("Kubernetes", "infra"),
    "k8s": ("Kubernetes", "infra"),
    "aws": ("AWS", "infra"),
    "생성형 ai": ("생성형 AI", "ai_ml"),
    "generative ai": ("생성형 AI", "ai_ml"),
    "llm": ("LLM", "ai_ml"),
    "git": ("Git", "collab"),
    "jira": ("Jira", "collab"),
}


def normalize_token(raw: str) -> tuple[str, SkillGroup] | None:
    t = raw.strip()
    if not t:
        return None
    key = re.sub(r"\s+", " ", t.lower())
    if key in _ALIASES:
        return _ALIASES[key]
    # 짧은 영문 토큰
    if re.fullmatch(r"[a-zA-Z0-9+#.]+", t) and len(t) <= 24:
        lk = key
        if lk in _ALIASES:
            return _ALIASES[lk]
    return (t[:1].upper() + t[1:] if len(t) > 1 else t.upper(), "soft_qual")


def extract_skills_from_text(text: str) -> list[tuple[str, str, SkillGroup, float]]:
    """본문에서 키워드 스캔 (데모용 규칙 기반)."""
    lower = text.lower()
    found: list[tuple[str, str, SkillGroup, float]] = []
    for alias, (norm, group) in _ALIASES.items():
        if alias in lower or alias in text:
            found.append((alias, norm, group, 0.92))
    # 중복 제거 by normalized
    seen: set[str] = set()
    out: list[tuple[str, str, SkillGroup, float]] = []
    for raw, norm, group, conf in found:
        if norm in seen:
            continue
        seen.add(norm)
        out.append((raw, norm, group, conf))
    return out
