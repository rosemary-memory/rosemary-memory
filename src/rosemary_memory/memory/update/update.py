from __future__ import annotations

import json
import difflib
import os
import asyncio
import threading
from typing import Any

from smolagents import ToolCallingAgent, tool

from rosemary_memory.storage.age import AgeClient
from rosemary_memory.memory.store import GraphStore


def _safe_json_loads(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _log_llm(name: str, prompt: str, response: str | None) -> None:
    if os.getenv("MEMORY_DEBUG", "").lower() not in {"1", "true", "yes"}:
        return
    print(f"[memory][{name}] prompt:\n{prompt}\n")
    if response is not None:
        print(f"[memory][{name}] response:\n{response}\n")


DEFAULT_DOMAINS = [
    "Realistic",
    "Investigative",
    "Artistic",
    "Social",
    "Enterprising",
    "Conventional",
]



def _normalize_label(text: str) -> str:
    clean = " ".join(text.strip().split())
    if not clean:
        return "General"
    return clean[:1].upper() + clean[1:].lower()


def _summary_lookup(existing: list[dict[str, Any]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for item in existing:
        text = str(item.get("text", "")).strip()
        summary_id = str(item.get("id", "")).strip()
        if text and summary_id:
            lookup[text.lower()] = summary_id
    return lookup


def _too_similar(a: str, b: str, threshold: float = 0.7) -> bool:
    ratio = difflib.SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()
    return ratio >= threshold


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


def update_from_detail(
    database_url: str,
    graph_name: str,
    model,
    detail_text: str,
    source: str = "agent",
) -> dict[str, Any]:
    def _seed_domains() -> None:
        async def _op(store: GraphStore):
            for label in DEFAULT_DOMAINS:
                try:
                    await store.create_domain(_normalize_label(label))
                except Exception:
                    # Best-effort seeding; ignore duplicates.
                    await asyncio.sleep(0)
            return None

        _run_db(database_url, graph_name, _op)

    _seed_domains()

    @tool
    def list_domains() -> list[str]:
        """List existing domain labels."""
        async def _op(store: GraphStore):
            return await store.list_clusters()

        rows = _run_db(database_url, graph_name, _op)
        return [row.get("label") for row in rows if row.get("label")]

    @tool
    def list_topics() -> list[dict[str, Any]]:
        """List existing topics with id and text."""
        async def _op(store: GraphStore):
            return await store.list_summaries()

        return _run_db(database_url, graph_name, _op)

    @tool
    def create_detail(text: str, source_label: str = "agent") -> dict[str, Any]:
        """Create a detail node with text and source label.

        Args:
            text: Detail text content.
            source_label: Source identifier for the detail.
        """
        async def _op(store: GraphStore):
            return await store.create_detail(text, source_label)

        return _run_db(database_url, graph_name, _op)

    @tool
    def create_topic(text: str) -> dict[str, Any]:
        """Create or fetch a topic by text.

        Args:
            text: Topic text label.
        """
        async def _op(store: GraphStore):
            return await store.create_summary(text)

        return _run_db(database_url, graph_name, _op)

    @tool
    def update_topic(topic_id: str, new_text: str) -> dict[str, Any]:
        """Update the text of a topic.

        Args:
            topic_id: Topic identifier.
            new_text: New topic text.
        """
        async def _op(store: GraphStore):
            await store.update_topic_text(topic_id, new_text)
            return {"ok": True}

        return _run_db(database_url, graph_name, _op)

    @tool
    def link_topic_domain(topic_id: str, domain_label: str) -> dict[str, Any]:
        """Link a topic to a domain.

        Args:
            topic_id: Topic identifier.
            domain_label: Domain label to link.
        """
        async def _op(store: GraphStore):
            await store.link_summary_to_cluster(topic_id, _normalize_label(domain_label))
            return {"ok": True}

        return _run_db(database_url, graph_name, _op)

    @tool
    def link_detail_topic(detail_id: str, topic_id: str) -> dict[str, Any]:
        """Link a detail to a topic.

        Args:
            detail_id: Detail identifier.
            topic_id: Topic identifier.
        """
        async def _op(store: GraphStore):
            await store.link_detail_to_summary(detail_id, topic_id)
            return {"ok": True}

        return _run_db(database_url, graph_name, _op)

    agent = ToolCallingAgent(
        tools=[
            list_domains,
            list_topics,
            create_detail,
            create_topic,
            update_topic,
            link_topic_domain,
            link_detail_topic,
        ],
        model=model,
        add_base_tools=False,
    )

    domain_list = ", ".join(DEFAULT_DOMAINS)
    system = (
        "You are a memory organizer. Use tools to place the new detail into a hierarchy: "
        "Domain -> Topic -> Detail. Domains are broad categories; Topics are mid-level groupings.\n"
        "A detail may belong to multiple topics, and a topic may belong to multiple domains.\n"
        f"Use only these personal-interest domains: {domain_list}.\n"
        "Examples of subdomains/topics:\n"
        "- Realistic: outdoors, mechanics, hands-on crafts\n"
        "- Investigative: science, research, data analysis\n"
        "- Artistic: visual arts, writing, music, fashion\n"
        "- Social: teaching, counseling, community\n"
        "- Enterprising: entrepreneurship, leadership, sales\n"
        "- Conventional: organization, accounting, operations\n"
        "Process:\n"
        "1. Create the detail node.\n"
        "2. Reuse existing topics when applicable; otherwise create a new topic.\n"
        "3. You may edit an existing topic text to be more general.\n"
        "4. Link topic(s) to domain(s).\n"
        "5. Link the detail to topic(s).\n"
        "Be concise and only use the tools."
    )
    prompt = f"Detail: {detail_text}"

    if os.getenv("MEMORY_DEBUG", "").lower() in {"1", "true", "yes"}:
        _log_llm("agent_system", system, None)

    response = agent.run(f"{system}\n\n{prompt}")
    if isinstance(response, str) and os.getenv("MEMORY_DEBUG", "").lower() in {"1", "true", "yes"}:
        print(f"[memory][agent_response]\n{response}\n")

    return {"ok": True}
