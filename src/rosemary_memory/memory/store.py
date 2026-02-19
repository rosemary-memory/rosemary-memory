from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from rosemary_memory.storage.age import AgeClient, parse_agtype


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex


class GraphStore:
    def __init__(self, age: AgeClient, graph_name: str) -> None:
        self._age = age
        self._graph = graph_name

    @property
    def graph_name(self) -> str:
        return self._graph

    async def ensure_graph(self) -> None:
        rows = await self._age.execute_sql(
            "SELECT count(*) FROM ag_catalog.ag_graph WHERE name = :name;",
            {"name": self._graph},
        )
        if rows and rows[0][0] > 0:
            return
        await self._age.execute_sql(
            "SELECT create_graph(:name);",
            {"name": self._graph},
        )

    async def list_cluster_labels(self) -> list[str]:
        query = "MATCH (c:Cluster) RETURN c.label AS result ORDER BY result"
        rows = await self._age.execute_cypher(self._graph, query)
        labels: list[str] = []
        for row in rows:
            label = parse_agtype(row[0])
            if isinstance(label, str):
                labels.append(label)
        return labels

    async def insert_cluster_summary_detail(
        self,
        cluster_label: str,
        summary_text: str,
        detail_text: str,
        source: str,
    ) -> dict[str, Any]:
        created_at = _utc_now()
        params = {
            "cluster_label": cluster_label,
            "cluster_id": _new_id(),
            "summary_id": _new_id(),
            "summary_text": summary_text,
            "detail_id": _new_id(),
            "detail_text": detail_text,
            "source": source,
            "created_at": created_at,
        }
        query = """
        MERGE (c:Cluster {label: $cluster_label})
        SET c.id = coalesce(c.id, $cluster_id),
            c.created_at = coalesce(c.created_at, $created_at)
        WITH c
        CREATE (s:Summary {id: $summary_id, text: $summary_text, created_at: $created_at})
        CREATE (d:Detail {id: $detail_id, text: $detail_text, source: $source, created_at: $created_at})
        CREATE (c)-[:HAS_SUMMARY]->(s)
        CREATE (s)-[:HAS_DETAIL]->(d)
        RETURN {cluster: properties(c), summary: properties(s), detail: properties(d)} AS result
        """
        rows = await self._age.execute_cypher(self._graph, query, params)
        if not rows:
            return {}
        result = parse_agtype(rows[0][0])
        if isinstance(result, dict):
            return result
        return {}

    async def retrieve(self, query_text: str, top_k: int) -> list[dict[str, Any]]:
        params = {"q": query_text, "k": top_k}
        query = """
        MATCH (c:Cluster)-[:HAS_SUMMARY]->(s:Summary)
        WHERE toLower(c.label) CONTAINS toLower($q)
           OR toLower(s.text) CONTAINS toLower($q)
        OPTIONAL MATCH (s)-[:HAS_DETAIL]->(d:Detail)
        WITH c, s, collect(properties(d)) AS details
        RETURN {cluster: properties(c),
                summary: properties(s),
                details: details} AS result
        LIMIT $k
        """
        rows = await self._age.execute_cypher(self._graph, query, params)
        results: list[dict[str, Any]] = []
        for row in rows:
            result = parse_agtype(row[0])
            if isinstance(result, dict):
                results.append(result)
        return results
