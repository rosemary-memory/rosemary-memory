from __future__ import annotations

import asyncio

from rosemary_memory.config import load_settings
from rosemary_memory.models.openai import build_openai_model
from rosemary_memory.agents.default import build_agent


async def main() -> None:
    settings = load_settings()
    model = build_openai_model(settings)
    agent = build_agent(model, settings.database_url, settings.age_graph_name)

    result = agent.run("Summarize our recent work on memory graphs.")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
