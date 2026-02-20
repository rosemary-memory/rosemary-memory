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
    detail_map: dict[str, dict[str, set[str]]] = {}

    for item in results:
        cluster = item.get("cluster", {}) if isinstance(item.get("cluster"), dict) else {}
        summary = item.get("summary", {}) if isinstance(item.get("summary"), dict) else {}
        details = item.get("details", []) if isinstance(item.get("details"), list) else []
        insights = item.get("insights", []) if isinstance(item.get("insights"), list) else []

        domain = str(cluster.get("label", "")).strip()
        topic = str(summary.get("text", "")).strip()
        insight_texts = []
        for insight in insights:
            if isinstance(insight, dict):
                text = str(insight.get("text", "")).strip()
            else:
                text = str(insight).strip()
            if text:
                insight_texts.append(text)

        for detail in details:
            if isinstance(detail, dict):
                detail_text = str(detail.get("text", "")).strip()
            else:
                detail_text = str(detail).strip()
            if not detail_text:
                continue
            bucket = detail_map.setdefault(
                detail_text,
                {"topics": set(), "domains": set(), "insights": set()},
            )
            if topic:
                bucket["topics"].add(topic)
            if domain:
                bucket["domains"].add(domain)
            for text in insight_texts:
                bucket["insights"].add(text)

    if not detail_map:
        return ""

    lines: list[str] = []
    for idx, (detail_text, meta) in enumerate(detail_map.items(), start=1):
        lines.append(f"{idx}. Detail: {detail_text}")
        if meta["topics"]:
            lines.append(f"   Topics: {', '.join(sorted(meta['topics']))}")
        if meta["domains"]:
            lines.append(f"   Domains: {', '.join(sorted(meta['domains']))}")
        if meta["insights"]:
            lines.append(f"   Insights: {', '.join(sorted(meta['insights']))}")

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
    results = [item for item, _score in scored[:top_k]]

    # Attach insights for each topic.
    for item in results:
        summary = item.get("summary", {}) if isinstance(item.get("summary"), dict) else {}
        topic_id = summary.get("id")
        if not topic_id:
            item["insights"] = []
            continue
        insights = await store.list_insights_for_topic(str(topic_id))
        item["insights"] = insights

    return results
