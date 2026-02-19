from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str
    openai_base_url: str | None
    database_url: str
    age_graph_name: str


def load_settings() -> Settings:
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    database_url = os.getenv("DATABASE_URL", "").strip()

    if not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")

    openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
    openai_base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None
    age_graph_name = os.getenv("AGE_GRAPH_NAME", "gmemory").strip()

    return Settings(
        openai_api_key=openai_api_key,
        openai_model=openai_model,
        openai_base_url=openai_base_url,
        database_url=database_url,
        age_graph_name=age_graph_name,
    )
