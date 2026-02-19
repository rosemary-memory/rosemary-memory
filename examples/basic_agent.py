from __future__ import annotations

import asyncio

from rosemary_memory.config import load_settings
from rosemary_memory.models.openai import build_openai_model
from rosemary_memory.storage.age import AgeClient
from rosemary_memory.memory.store import GraphStore
from rosemary_memory.agents.default import build_agent


async def main() -> None:
    settings = load_settings()
    age = AgeClient(settings.database_url)
    store = GraphStore(age, settings.age_graph_name)
    await store.ensure_graph()

    model = build_openai_model(settings)
    agent = build_agent(model, store)

    result = agent.run("Summarize our recent work on memory graphs.")
    print(result)

    await age.close()


if __name__ == "__main__":
    asyncio.run(main())
