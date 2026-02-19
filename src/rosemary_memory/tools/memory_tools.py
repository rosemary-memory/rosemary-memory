from __future__ import annotations

import asyncio
import json
from typing import Any

from smolagents import tool

from rosemary_memory.memory.retrieval.retrieve import format_results
from rosemary_memory.memory.update.update import update_from_detail
from rosemary_memory.memory.store import GraphStore


def _run(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("memory tools cannot run inside an active event loop")


def build_memory_tools(store: GraphStore, model) -> list[Any]:
    @tool
    def memory_retrieve(query: str, top_k: int = 5) -> str:
        """Retrieve relevant memory clusters/summaries/details."""
        results = _run(store.retrieve(query, top_k))
        if not results:
            return "No relevant memory found."
        return format_results(results)

    @tool
    def memory_update(detail_text: str, source: str = "agent") -> str:
        """Store a detail into memory with cluster + summary."""
        result = _run(update_from_detail(store, model, detail_text, source=source))
        return json.dumps(result, ensure_ascii=True)

    return [memory_retrieve, memory_update]
