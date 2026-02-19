from __future__ import annotations

from typing import Any

from rosemary_memory.memory.store import GraphStore


def format_results(results: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for idx, item in enumerate(results, start=1):
        cluster = item.get("cluster", {})
        summary = item.get("summary", {})
        details = item.get("details", []) or []
        lines.append(f"{idx}. Cluster: {cluster.get('label', 'unknown')}")
        lines.append(f"   Summary: {summary.get('text', '')}")
        if details:
            for detail in details[:3]:
                if isinstance(detail, dict):
                    text = detail.get("text", "")
                else:
                    text = str(detail)
                lines.append(f"   Detail: {text}")
    return "\n".join(lines).strip()


async def retrieve_memory(store: GraphStore, query: str, top_k: int = 5) -> list[dict[str, Any]]:
    return await store.retrieve(query, top_k)
