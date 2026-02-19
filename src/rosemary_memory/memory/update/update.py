from __future__ import annotations

import json
from typing import Any

from rosemary_memory.memory.store import GraphStore


def _safe_json_loads(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _infer_cluster_and_summary(
    model,
    detail_text: str,
    existing_clusters: list[str],
) -> tuple[str, str]:
    cluster_list = ", ".join(existing_clusters[:20]) if existing_clusters else "(none)"
    prompt = (
        "You are clustering memory details into coarse topics. "
        "Given existing cluster labels, pick the best label or create a new concise label (3-5 words). "
        "Also write a short, single-sentence summary.\n\n"
        f"Existing clusters: {cluster_list}\n"
        f"Detail: {detail_text}\n\n"
        'Return JSON: {"cluster_label": "...", "summary": "..."}'
    )

    response = model(
        [
            {"role": "system", "content": "You output only valid JSON."},
            {"role": "user", "content": prompt},
        ]
    )

    data = _safe_json_loads(response) if isinstance(response, str) else None
    if isinstance(data, dict):
        cluster_label = str(data.get("cluster_label", "general")).strip() or "general"
        summary = str(data.get("summary", "")).strip()
        if summary:
            return cluster_label, summary

    fallback_summary = detail_text.strip().replace("\n", " ")[:200]
    return "general", fallback_summary


async def update_from_detail(
    store: GraphStore,
    model,
    detail_text: str,
    source: str = "agent",
) -> dict[str, Any]:
    existing = await store.list_cluster_labels()
    cluster_label, summary = _infer_cluster_and_summary(model, detail_text, existing)
    return await store.insert_cluster_summary_detail(
        cluster_label=cluster_label,
        summary_text=summary,
        detail_text=detail_text,
        source=source,
    )
