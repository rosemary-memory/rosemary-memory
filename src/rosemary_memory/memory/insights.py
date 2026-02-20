from __future__ import annotations

import asyncio
import json
import threading
from typing import Any

from smolagents import ToolCallingAgent, tool

from rosemary_memory.storage.age import AgeClient
from rosemary_memory.memory.store import GraphStore
from rosemary_memory.memory.embeddings import embed_text


def _run_db(database_url: str, graph_name: str, fn):
    result_container: dict[str, Any] = {}

    def _target():
        async def _inner():
            age = AgeClient(database_url)
            store = GraphStore(age, graph_name)
            await store.ensure_graph()
            result = await fn(store)
            await age.close()
            return result

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result_container["value"] = loop.run_until_complete(_inner())
            loop.close()
        except Exception as exc:
            result_container["error"] = exc

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join()
    if "error" in result_container:
        raise result_container["error"]
    return result_container.get("value")


def _safe_json(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _format_context(detail_ctx: dict[str, Any], insights: list[dict[str, Any]]) -> str:
    detail = detail_ctx.get("detail") or {}
    topics = detail_ctx.get("topics") or []
    domains = detail_ctx.get("domains") or []

    detail_text = detail.get("text", "")
    detail_id = detail.get("id", "")
    topic_texts = [f"{t.get('id','')}: {t.get('text','')}" for t in topics if isinstance(t, dict)]
    domain_labels = [f"{d.get('label','')}" for d in domains if isinstance(d, dict)]
    insight_texts = [f"{i.get('id','')}: {i.get('text','')}" for i in insights if isinstance(i, dict)]

    lines = [
        f"Detail ID: {detail_id}",
        f"Detail Text: {detail_text}",
        f"Topics: {', '.join([t for t in topic_texts if t]) or 'none'}",
        f"Domains: {', '.join([d for d in domain_labels if d]) or 'none'}",
        f"Existing insights: {', '.join([i for i in insight_texts if i]) or 'none'}",
    ]
    return "\n".join(lines)


def generate_insights(
    database_url: str,
    graph_name: str,
    model,
    limit: int = 25,
) -> dict[str, Any]:
    """Process pending details and attach insights."""
    @tool
    def list_pending_details(limit: int = 25) -> list[dict[str, Any]]:
        """List pending details with id and text.

        Args:
            limit: Maximum number of pending details to return.
        """
        async def _op(store: GraphStore):
            return await store.list_pending_details(limit)

        return _run_db(database_url, graph_name, _op)

    @tool
    def get_detail_context(detail_id: str) -> dict[str, Any]:
        """Fetch detail, topics, and domains for a detail id.

        Args:
            detail_id: Detail identifier.
        """
        async def _op(store: GraphStore):
            return await store.get_detail_context(detail_id)

        return _run_db(database_url, graph_name, _op)

    @tool
    def list_insights_for_topics(topic_ids: list[str]) -> list[dict[str, Any]]:
        """List existing insights for a list of topic ids.

        Args:
            topic_ids: Topic identifiers to fetch insights for.
        """
        async def _op(store: GraphStore):
            return await store.list_insights_for_topics(topic_ids)

        return _run_db(database_url, graph_name, _op)

    @tool
    def create_insight(text: str) -> dict[str, Any]:
        """Create a new insight with text.

        Args:
            text: Insight text content.
        """
        async def _op(store: GraphStore):
            embedding = embed_text(text)
            return await store.create_insight(text, embedding=embedding)

        result = _run_db(database_url, graph_name, _op)
        result.pop("embedding", None)
        return result

    @tool
    def update_insight(insight_id: str, new_text: str) -> dict[str, Any]:
        """Update an insight text.

        Args:
            insight_id: Insight identifier.
            new_text: New insight text.
        """
        async def _op(store: GraphStore):
            await store.update_insight_text(insight_id, new_text)
            return {"ok": True}

        return _run_db(database_url, graph_name, _op)

    @tool
    def link_insight_topic(insight_id: str, topic_id: str) -> dict[str, Any]:
        """Link an insight to a topic.

        Args:
            insight_id: Insight identifier.
            topic_id: Topic identifier.
        """
        async def _op(store: GraphStore):
            await store.link_insight_to_topic(insight_id, topic_id)
            return {"ok": True}

        return _run_db(database_url, graph_name, _op)

    @tool
    def link_insight_detail(insight_id: str, detail_id: str) -> dict[str, Any]:
        """Link an insight to a detail.

        Args:
            insight_id: Insight identifier.
            detail_id: Detail identifier.
        """
        async def _op(store: GraphStore):
            resolved = await store.resolve_detail_id(detail_id)
            if not resolved:
                return {"ok": False, "error": "detail_not_found"}
            await store.link_detail_to_insight(resolved, insight_id)
            return {"ok": True}

        return _run_db(database_url, graph_name, _op)

    @tool
    def mark_detail_processed(detail_id: str) -> dict[str, Any]:
        """Mark a detail as insight-processed.

        Args:
            detail_id: Detail identifier.
        """
        async def _op(store: GraphStore):
            resolved = await store.resolve_detail_id(detail_id)
            if not resolved:
                return {"ok": False, "error": "detail_not_found"}
            await store.mark_detail_insight_processed(resolved)
            return {"ok": True}

        return _run_db(database_url, graph_name, _op)

    agent = ToolCallingAgent(
        tools=[
            list_pending_details,
            get_detail_context,
            list_insights_for_topics,
            create_insight,
            update_insight,
            link_insight_topic,
            link_insight_detail,
            mark_detail_processed,
        ],
        model=model,
    )

    summary = {"processed": 0, "errors": 0, "details": []}
    pending = list_pending_details(limit)
    for item in pending:
        detail_id = item.get("id")
        if not detail_id:
            continue
        try:
            detail_ctx = get_detail_context(detail_id)
            topics = detail_ctx.get("topics") or []
            topic_ids = [t.get("id") for t in topics if isinstance(t, dict) and t.get("id")]
            insights = list_insights_for_topics(topic_ids)

            prompt = "\n".join(
                [
                    "You are an insight organizer.",
                    "Goal: attach 1-2 concise insights to the detail below.",
                    "Insights must be short (4-12 words) and reusable.",
                    "Prefer linking to existing insights if they already match.",
                    "If a topic can be generalized, you may update an existing insight.",
                    "Always use IDs from the context (never use raw text as IDs).",
                    "Use tools to create/link/update insights, then mark the detail processed.",
                    "",
                    _format_context(detail_ctx, insights),
                ]
            )

            response = agent.run(prompt)
            mark_detail_processed(detail_id)
            info = {"detail_id": detail_id, "response": response}
            summary["details"].append(info)
            summary["processed"] += 1
        except Exception as exc:
            mark_detail_processed(detail_id)
            summary["errors"] += 1
            summary["details"].append({"detail_id": detail_id, "error": str(exc)})

    return summary
