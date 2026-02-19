from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rosemary_memory.storage.age import AgeClient, parse_agtype


def _sanitize_label(text: str, limit: int = 80) -> str:
    clean = " ".join(text.replace("\n", " ").split())
    if len(clean) > limit:
        return clean[: limit - 3] + "..."
    return clean


def _node_key(node: dict[str, Any]) -> str:
    label = str(node.get("label", "node"))
    props = node.get("properties", {}) if isinstance(node.get("properties"), dict) else {}
    stable_id = props.get("id") or node.get("id") or props.get("label") or "unknown"
    return f"{label}:{stable_id}"


def _node_label(node: dict[str, Any]) -> str:
    label = str(node.get("label", "Node"))
    props = node.get("properties", {}) if isinstance(node.get("properties"), dict) else {}
    if label == "Cluster":
        title = props.get("label", "cluster")
    elif label == "Summary":
        title = props.get("text", "summary")
    elif label == "Detail":
        title = props.get("text", "detail")
    else:
        title = props.get("id", "node")
    return f"{label}: {_sanitize_label(str(title))}"


def _dot_node(node_id: str, label: str) -> str:
    safe_label = label.replace('"', "'")
    return f'  "{node_id}" [label="{safe_label}"];'


def _dot_edge(src: str, dst: str, label: str | None = None) -> str:
    if label:
        safe_label = label.replace('"', "'")
        return f'  "{src}" -> "{dst}" [label="{safe_label}"];'
    return f'  "{src}" -> "{dst}";'


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


async def build_graphviz_dot(database_url: str, graph_name: str) -> str:
    age = AgeClient(database_url)
    query = """
    MATCH (c:Cluster)
    OPTIONAL MATCH (c)-[:HAS_SUMMARY]->(s:Summary)
    OPTIONAL MATCH (s)-[:HAS_DETAIL]->(d:Detail)
    RETURN {
      cluster: {label: label(c), properties: properties(c)},
      summary: case when s is null then null else {label: label(s), properties: properties(s)} end,
      detail: case when d is null then null else {label: label(d), properties: properties(d)} end
    } AS result
    """
    rows = await age.execute_cypher(graph_name, query)
    await age.close()

    nodes: dict[str, str] = {}
    edges: set[tuple[str, str, str | None]] = set()

    for row in rows:
        payload = parse_agtype(row[0])
        if not isinstance(payload, dict):
            continue
        cluster = payload.get("cluster")
        summary = payload.get("summary")
        detail = payload.get("detail")

        if isinstance(cluster, dict):
            c_key = _node_key(cluster)
            nodes[c_key] = _node_label(cluster)
        else:
            continue

        if isinstance(summary, dict):
            s_key = _node_key(summary)
            nodes[s_key] = _node_label(summary)
            edges.add((c_key, s_key, "HAS_SUMMARY"))
        else:
            s_key = None

        if isinstance(detail, dict):
            d_key = _node_key(detail)
            nodes[d_key] = _node_label(detail)
            if s_key:
                edges.add((s_key, d_key, "HAS_DETAIL"))

    lines = [
        "digraph Memory {",
        "  rankdir=LR;",
        "  dpi=200;",
        "  nodesep=0.4;",
        "  ranksep=0.6;",
        '  node [shape=box, style="rounded,filled", color="#444444", fillcolor="#f6f6f6", fontname="Helvetica", fontsize=12];',
        '  edge [color="#666666", fontname="Helvetica", fontsize=10];',
    ]

    for node_id, label in nodes.items():
        lines.append(_dot_node(node_id, label))

    for src, dst, label in sorted(edges):
        lines.append(_dot_edge(src, dst, label))

    lines.append("}")
    return "\n".join(lines)


def default_snapshot_path(out_dir: Path, fmt: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"graph-{_timestamp_slug()}.{fmt}"
