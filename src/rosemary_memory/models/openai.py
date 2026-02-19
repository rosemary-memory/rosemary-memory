from __future__ import annotations

from smolagents import OpenAIModel

from rosemary_memory.config import Settings


def build_openai_model(settings: Settings) -> OpenAIModel:
    kwargs = {}
    if settings.openai_base_url:
        kwargs["api_base"] = settings.openai_base_url

    return OpenAIModel(
        model_id=settings.openai_model,
        api_key=settings.openai_api_key,
        **kwargs,
    )
