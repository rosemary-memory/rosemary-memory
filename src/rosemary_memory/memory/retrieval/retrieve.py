from __future__ import annotations

from typing import Any

from rosemary_memory.memory.embeddings import embed_text, cosine_similarity
from rosemary_memory.memory.store import GraphStore


def _score_item(query_vec: list[float], item: dict[str, Any]) -> float:
    best = 0.0
    summary = item.get("summary", {}) if isinstance(item.get("summary"), dict) else {}
    details = item.get("details", []) if isinstance(item.get("details"), list) else []

    summary_vec = summary.get("embedding")

    if isinstance(summary_vec, list):
        best = max(best, cosine_similarity(query_vec, summary_vec))
    for detail in details:
        if isinstance(detail, dict):
            detail_vec = detail.get("embedding")
            if isinstance(detail_vec, list):
                best = max(best, cosine_similarity(query_vec, detail_vec))

    return best


def format_results(results: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for idx, item in enumerate(results, start=1):
        cluster = item.get("cluster", {})
        summary = item.get("summary", {})
        details = item.get("details", [])
        lines.append(f"{idx}. Cluster: {cluster.get('label', 'unknown')}")
        lines.append(f"   Summary: {summary.get('text', '')}")
        if details:
            for detail in details[:3]:
                if isinstance(detail, dict):
                    text = detail.get("text", "")
                else:
                    text = str(detail)
                if text:
                    lines.append(f"   Detail: {text}")
    return "\n".join(lines).strip()


async def retrieve_memory(
    store: GraphStore,
    query: str,
    top_k: int = 5,
    min_score: float = 0.35,
) -> list[dict[str, Any]]:
    candidates = await store.retrieve(query, top_k * 10)
    if not candidates:
        return []

    # Normalize raw rows into grouped items with details list.
    if any(isinstance(item, dict) and "detail" in item for item in candidates):
        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        for row in candidates:
            if not isinstance(row, dict):
                continue
            cluster = row.get("cluster") or {}
            summary = row.get("summary") or {}
            detail = row.get("detail") or {}
            cluster_id = str(cluster.get("id") or cluster.get("label") or "cluster")
            summary_id = str(summary.get("id") or summary.get("text") or "topic")
            key = (cluster_id, summary_id)
            if key not in grouped:
                grouped[key] = {"cluster": cluster, "summary": summary, "details": []}
            if detail:
                grouped[key]["details"].append(detail)
        candidates = list(grouped.values())

    query_vec = embed_text(query)
    scored = [(item, _score_item(query_vec, item)) for item in candidates]
    scored = [(item, score) for item, score in scored if score >= min_score]
    if not scored:
        return []
    scored.sort(key=lambda x: x[1], reverse=True)
    return [item for item, _score in scored[:top_k]]
