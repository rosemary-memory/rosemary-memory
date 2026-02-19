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
        try:
            await self._age.execute_sql(
                "SELECT create_graph(:name);",
                {"name": self._graph},
            )
        except Exception as exc:
            message = str(exc)
            if "already exists" in message or "duplicate key" in message:
                return
            raise

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

    async def create_detail(self, detail_text: str, source: str) -> dict[str, Any]:
        created_at = _utc_now()
        params = {
            "detail_id": _new_id(),
            "detail_text": detail_text,
            "source": source,
            "created_at": created_at,
        }
        query = """
        CREATE (d:Detail {id: $detail_id, text: $detail_text, source: $source, created_at: $created_at})
        RETURN {detail: properties(d)} AS result
        """
        rows = await self._age.execute_cypher(self._graph, query, params)
        if not rows:
            return {}
        result = parse_agtype(rows[0][0])
        if isinstance(result, dict):
            return result.get("detail", {}) if isinstance(result.get("detail"), dict) else result
        return {}

    async def list_summaries(self, limit: int = 50) -> list[dict[str, Any]]:
        params = {"k": limit}
        query = """
        MATCH (t:Topic)
        RETURN {id: t.id, text: t.text} AS result
        LIMIT $k
        """
        rows = await self._age.execute_cypher(self._graph, query, params)
        results: list[dict[str, Any]] = []
        for row in rows:
            result = parse_agtype(row[0])
            if isinstance(result, dict):
                results.append(result)
        return results

    async def list_clusters(self, limit: int = 50) -> list[dict[str, Any]]:
        params = {"k": limit}
        query = """
        MATCH (c:Domain)
        RETURN {label: c.label} AS result
        LIMIT $k
        """
        rows = await self._age.execute_cypher(self._graph, query, params)
        results: list[dict[str, Any]] = []
        for row in rows:
            result = parse_agtype(row[0])
            if isinstance(result, dict):
                results.append(result)
        return results

    async def create_domain(self, label: str) -> dict[str, Any]:
        created_at = _utc_now()
        params = {
            "cluster_label": label,
            "cluster_id": _new_id(),
            "created_at": created_at,
        }
        query = """
        MERGE (c:Domain {label: $cluster_label})
        SET c.id = coalesce(c.id, $cluster_id),
            c.created_at = coalesce(c.created_at, $created_at)
        RETURN {domain: properties(c)} AS result
        """
        rows = await self._age.execute_cypher(self._graph, query, params)
        if not rows:
            return {}
        result = parse_agtype(rows[0][0])
        if isinstance(result, dict):
            return result.get("domain", {}) if isinstance(result.get("domain"), dict) else result
        return {}

    async def create_summary(self, summary_text: str) -> dict[str, Any]:
        created_at = _utc_now()
        params = {
            "summary_id": _new_id(),
            "summary_text": summary_text,
            "created_at": created_at,
        }
        query = """
        MERGE (t:Topic {text: $summary_text})
        SET t.id = coalesce(t.id, $summary_id),
            t.created_at = coalesce(t.created_at, $created_at)
        RETURN {summary: properties(t)} AS result
        """
        rows = await self._age.execute_cypher(self._graph, query, params)
        if not rows:
            return {}
        result = parse_agtype(rows[0][0])
        if isinstance(result, dict):
            return result.get("summary", {}) if isinstance(result.get("summary"), dict) else result
        return {}

    async def link_detail_to_summary(self, detail_id: str, summary_id: str) -> None:
        params = {"detail_id": detail_id, "summary_id": summary_id}
        query = """
        MATCH (d:Detail {id: $detail_id})
        MATCH (t:Topic {id: $summary_id})
        MERGE (t)-[:HAS_DETAIL]->(d)
        RETURN {ok: true} AS result
        """
        await self._age.execute_cypher(self._graph, query, params)

    async def link_summary_to_cluster(self, summary_id: str, cluster_label: str) -> None:
        created_at = _utc_now()
        params = {
            "summary_id": summary_id,
            "cluster_label": cluster_label,
            "cluster_id": _new_id(),
            "created_at": created_at,
        }
        query = """
        MERGE (c:Domain {label: $cluster_label})
        SET c.id = coalesce(c.id, $cluster_id),
            c.created_at = coalesce(c.created_at, $created_at)
        WITH c
        MATCH (t:Topic {id: $summary_id})
        MERGE (c)-[:HAS_TOPIC]->(t)
        RETURN {ok: true} AS result
        """
        await self._age.execute_cypher(self._graph, query, params)

    async def update_topic_text(self, topic_id: str, new_text: str) -> None:
        params = {"topic_id": topic_id, "topic_text": new_text}
        query = """
        MATCH (t:Topic {id: $topic_id})
        SET t.text = $topic_text
        RETURN {ok: true} AS result
        """
        await self._age.execute_cypher(self._graph, query, params)
    async def retrieve(self, query_text: str, top_k: int) -> list[dict[str, Any]]:
        terms = _expand_query_terms(query_text)
        params: dict[str, Any] = {"k": top_k}
        clauses = []
        for idx, term in enumerate(terms):
            key = f"q{idx}"
            params[key] = term
            clauses.append(
                f"toLower(c.label) CONTAINS toLower(${key}) "
                f"OR toLower(t.text) CONTAINS toLower(${key}) "
                f"OR toLower(d.text) CONTAINS toLower(${key})"
            )
        where_clause = " OR ".join(f"({c})" for c in clauses) if clauses else "true"

        query = f"""
        MATCH (c:Domain)-[:HAS_TOPIC]->(t:Topic)
        OPTIONAL MATCH (t)-[:HAS_DETAIL]->(d:Detail)
        WHERE {where_clause}
        WITH c, t, collect(properties(d)) AS details
        RETURN {{cluster: properties(c),
                summary: properties(t),
                details: details}} AS result
        LIMIT $k
        """
        rows = await self._age.execute_cypher(self._graph, query, params)
        results: list[dict[str, Any]] = []
        for row in rows:
            result = parse_agtype(row[0])
            if isinstance(result, dict):
                results.append(result)
        return results


def _expand_query_terms(query_text: str) -> list[str]:
    base = query_text.strip()
    if not base:
        return []
    terms = [base]
    lowered = base.lower()
    if "food" in lowered or "eat" in lowered or "restaurant" in lowered:
        terms.extend(["food", "eat", "restaurant", "cafe", "dinner", "lunch", "breakfast"])
    if "shop" in lowered or "shopping" in lowered or "fashion" in lowered:
        terms.extend(["shop", "shopping", "fashion", "boutique", "clothes", "style"])
    if "travel" in lowered or "trip" in lowered or "visit" in lowered:
        terms.extend(["travel", "trip", "visit", "vacation", "tour", "hotel"])
    # De-duplicate while preserving order
    seen = set()
    deduped = []
    for term in terms:
        t = term.strip()
        if not t:
            continue
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(t)
    return deduped
