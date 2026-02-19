from __future__ import annotations

import asyncio
import json
from typing import Any

from smolagents import tool

from rosemary_memory.config import load_settings
from rosemary_memory.memory.retrieval.retrieve import format_results, retrieve_memory
from rosemary_memory.memory.update.update import update_from_detail
from rosemary_memory.memory.store import GraphStore
from rosemary_memory.storage.age import AgeClient


def _run(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("memory tools cannot run inside an active event loop")


async def _retrieve_once(database_url: str, graph_name: str, query: str, top_k: int) -> str:
    settings = load_settings()
    age = AgeClient(database_url)
    store = GraphStore(age, graph_name)
    await store.ensure_graph()
    results = await retrieve_memory(
        store,
        query,
        top_k,
        min_score=settings.retrieval_min_score,
    )
    await age.close()
    if not results:
        return "No relevant memory found."
    return format_results(results)


def _update_once(
    database_url: str,
    graph_name: str,
    model,
    detail_text: str,
    source: str,
) -> str:
    result = update_from_detail(database_url, graph_name, model, detail_text, source=source)
    return json.dumps(result, ensure_ascii=True)


def build_memory_tools(database_url: str, graph_name: str, model) -> list[Any]:
    @tool
    def memory_retrieve(query: str, top_k: int = 5) -> str:
        """Retrieve relevant memory clusters/summaries/details."""
        return _run(_retrieve_once(database_url, graph_name, query, top_k))

    @tool
    def memory_update(detail_text: str, source: str = "agent") -> str:
        """Store a detail into memory with cluster + summary."""
        return _update_once(database_url, graph_name, model, detail_text, source)

    return [memory_retrieve, memory_update]
