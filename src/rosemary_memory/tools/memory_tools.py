from __future__ import annotations

import asyncio
import json
from typing import Any

from smolagents import tool

from rosemary_memory.memory.retrieval.retrieve import format_results
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
    age = AgeClient(database_url)
    store = GraphStore(age, graph_name)
    await store.ensure_graph()
    results = await store.retrieve(query, top_k)
    await age.close()
    if not results:
        return "No relevant memory found."
    return format_results(results)


async def _update_once(
    database_url: str,
    graph_name: str,
    model,
    detail_text: str,
    source: str,
) -> str:
    age = AgeClient(database_url)
    store = GraphStore(age, graph_name)
    await store.ensure_graph()
    result = await update_from_detail(store, model, detail_text, source=source)
    await age.close()
    return json.dumps(result, ensure_ascii=True)


def build_memory_tools(database_url: str, graph_name: str, model) -> list[Any]:
    @tool
    def memory_retrieve(query: str, top_k: int = 5) -> str:
        """Retrieve relevant memory clusters/summaries/details."""
        return _run(_retrieve_once(database_url, graph_name, query, top_k))

    @tool
    def memory_update(detail_text: str, source: str = "agent") -> str:
        """Store a detail into memory with cluster + summary."""
        return _run(_update_once(database_url, graph_name, model, detail_text, source))

    return [memory_retrieve, memory_update]
