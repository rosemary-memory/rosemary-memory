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
    if label == "Domain":
        title = props.get("label", "cluster")
    elif label == "Topic":
        title = props.get("text", "summary")
    elif label == "Detail":
        title = props.get("text", "detail")
    elif label == "Insight":
        title = props.get("text", "insight")
    else:
        title = props.get("id", "node")
    return _sanitize_label(str(title))


def _dot_node(node_id: str, label: str, style: str) -> str:
    safe_label = label.replace('"', "'")
    return f'  "{node_id}" [label="{safe_label}", {style}];'


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
    MATCH (c:Domain)
    OPTIONAL MATCH (c)-[:HAS_TOPIC]->(s:Topic)
    OPTIONAL MATCH (s)-[:HAS_DETAIL]->(d:Detail)
    RETURN {
      cluster: {label: label(c), properties: properties(c)},
      summary: case when s is null then null else {label: label(s), properties: properties(s)} end,
      detail: case when d is null then null else {label: label(d), properties: properties(d)} end
    } AS result
    """
    rows = await age.execute_cypher(graph_name, query)

    insight_query = """
    MATCH (t:Topic)
    OPTIONAL MATCH (t)-[:HAS_INSIGHT]->(i:Insight)
    OPTIONAL MATCH (i)-[:SUPPORTS_DETAIL]->(d:Detail)
    RETURN {
      summary: {label: label(t), properties: properties(t)},
      insight: case when i is null then null else {label: label(i), properties: properties(i)} end,
      detail: case when d is null then null else {label: label(d), properties: properties(d)} end
    } AS result
    """
    insight_rows = await age.execute_cypher(graph_name, insight_query)
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

    for row in insight_rows:
        payload = parse_agtype(row[0])
        if not isinstance(payload, dict):
            continue
        summary = payload.get("summary")
        insight = payload.get("insight")
        detail = payload.get("detail")

        s_key = None
        if isinstance(summary, dict):
            s_key = _node_key(summary)
            nodes[s_key] = _node_label(summary)

        i_key = None
        if isinstance(insight, dict):
            i_key = _node_key(insight)
            nodes[i_key] = _node_label(insight)
            if s_key:
                edges.add((s_key, i_key, "HAS_INSIGHT"))

        if isinstance(detail, dict):
            d_key = _node_key(detail)
            nodes[d_key] = _node_label(detail)
            if i_key:
                edges.add((i_key, d_key, "SUPPORTS_DETAIL"))

    cluster_nodes: list[str] = []
    summary_nodes: list[str] = []
    detail_nodes: list[str] = []
    insight_nodes: list[str] = []

    for node_id in nodes:
        if node_id.startswith("Domain:"):
            cluster_nodes.append(node_id)
        elif node_id.startswith("Topic:"):
            summary_nodes.append(node_id)
        elif node_id.startswith("Detail:"):
            detail_nodes.append(node_id)
        elif node_id.startswith("Insight:"):
            insight_nodes.append(node_id)

    lines = [
        "digraph Memory {",
        "  rankdir=TB;",
        "  dpi=220;",
        "  nodesep=0.35;",
        "  ranksep=0.6;",
        '  edge [color="#666666", fontname="Helvetica", fontsize=10, arrowsize=0.7];',
        "",
        "  subgraph cluster_clusters {",
        "    label=\"Domains\";",
        "    style=\"rounded\";",
        "    color=\"#cccccc\";",
        "    rank=same;",
    ]
    for node_id in sorted(cluster_nodes):
        lines.append(
            _dot_node(
                node_id,
                nodes[node_id],
                'shape=box, style="rounded,filled", color="#1f4e79", fillcolor="#e6f0fa", fontname="Helvetica", fontsize=12',
            )
        )
    lines.extend(["  }", "", "  subgraph cluster_summaries {", "    label=\"Topics\";", "    style=\"rounded\";", "    color=\"#cccccc\";", "    rank=same;"])
    for node_id in sorted(summary_nodes):
        lines.append(
            _dot_node(
                node_id,
                nodes[node_id],
                'shape=box, style="rounded,filled", color="#5b3a29", fillcolor="#f5ede9", fontname="Helvetica", fontsize=11',
            )
        )
    lines.extend(["  }", "", "  subgraph cluster_details {", "    label=\"Details\";", "    style=\"rounded\";", "    color=\"#cccccc\";", "    rank=same;"])
    for node_id in sorted(detail_nodes):
        lines.append(
            _dot_node(
                node_id,
                nodes[node_id],
                'shape=box, style="rounded,filled", color="#2f4f2f", fillcolor="#e9f3e9", fontname="Helvetica", fontsize=10',
            )
        )
    lines.extend(["  }", ""])

    if insight_nodes:
        lines.extend(["", "  subgraph cluster_insights {", "    label=\"Insights\";", "    style=\"rounded\";", "    color=\"#cccccc\";", "    rank=same;"])
        for node_id in sorted(insight_nodes):
            lines.append(
                _dot_node(
                    node_id,
                    nodes[node_id],
                    'shape=box, style="rounded,filled", color="#4b3b6b", fillcolor="#efe9f7", fontname="Helvetica", fontsize=10',
                )
            )
        lines.extend(["  }", ""])

    # Force layer ordering: Domains -> Topics -> Details -> Insights
    if cluster_nodes and summary_nodes:
        lines.append(f'  "{sorted(cluster_nodes)[0]}" -> "{sorted(summary_nodes)[0]}" [style=invis, weight=10];')
    if summary_nodes and detail_nodes:
        lines.append(f'  "{sorted(summary_nodes)[0]}" -> "{sorted(detail_nodes)[0]}" [style=invis, weight=10];')
    if detail_nodes and insight_nodes:
        lines.append(f'  "{sorted(detail_nodes)[0]}" -> "{sorted(insight_nodes)[0]}" [style=invis, weight=10];')

    for src, dst, _label in sorted(edges):
        lines.append(_dot_edge(src, dst, None))

    lines.append("}")
    return "\n".join(lines)


def default_snapshot_path(out_dir: Path, fmt: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"graph-{_timestamp_slug()}.{fmt}"
