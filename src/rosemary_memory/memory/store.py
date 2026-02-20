from __future__ import annotations

import uuid
from datetime import datetime, timezone
import asyncio
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
        self._label_ready: set[str] = set()

    async def _execute_cypher_with_retry(self, query: str, params: dict[str, Any] | None = None) -> list[Any]:
        params = params or {}
        for attempt in range(3):
            try:
                return await self._age.execute_cypher(self._graph, query, params)
            except Exception as exc:
                message = str(exc)
                if "DuplicateTableError" in message or "Entity failed to be updated" in message:
                    await asyncio.sleep(0.1 * (attempt + 1))
                    continue
                raise
        return await self._age.execute_cypher(self._graph, query, params)

    async def _ensure_edge_label(self, label: str) -> None:
        if label in self._label_ready:
            return
        # Trigger edge label creation safely.
        params = {"label": label}
        query = """
        MATCH (a) WHERE false
        MATCH (b) WHERE false
        MERGE (a)-[r:$label]->(b)
        RETURN r
        """
        try:
            await self._age.execute_cypher(self._graph, query, params)
        except Exception:
            # Best-effort only.
            pass
        self._label_ready.add(label)

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

    async def create_detail(
        self,
        detail_text: str,
        source: str,
        embedding: list[float] | None = None,
    ) -> dict[str, Any]:
        created_at = _utc_now()
        params = {
            "detail_id": _new_id(),
            "detail_text": detail_text,
            "source": source,
            "created_at": created_at,
            "embedding": embedding,
            "insight_pending": True,
        }
        query = """
        CREATE (d:Detail {id: $detail_id, text: $detail_text, source: $source, created_at: $created_at, embedding: $embedding, insight_pending: $insight_pending})
        RETURN {detail: properties(d)} AS result
        """
        rows = await self._execute_cypher_with_retry(query, params)
        if not rows:
            return {}
        result = parse_agtype(rows[0][0])
        if isinstance(result, dict):
            detail = result.get("detail", {}) if isinstance(result.get("detail"), dict) else result
            if isinstance(detail, dict):
                detail.pop("embedding", None)
            return detail
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
        return _flatten_results(results)

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
        rows = await self._execute_cypher_with_retry(query, params)
        if not rows:
            return {}
        result = parse_agtype(rows[0][0])
        if isinstance(result, dict):
            return result.get("domain", {}) if isinstance(result.get("domain"), dict) else result
        return {}

    async def create_summary(
        self,
        summary_text: str,
        embedding: list[float] | None = None,
    ) -> dict[str, Any]:
        created_at = _utc_now()
        params = {
            "summary_id": _new_id(),
            "summary_text": summary_text,
            "created_at": created_at,
            "embedding": embedding,
        }
        query = """
        MERGE (t:Topic {text: $summary_text})
        SET t.id = coalesce(t.id, $summary_id),
            t.created_at = coalesce(t.created_at, $created_at),
            t.embedding = coalesce(t.embedding, $embedding)
        RETURN {summary: properties(t)} AS result
        """
        rows = await self._execute_cypher_with_retry(query, params)
        if not rows:
            return {}
        result = parse_agtype(rows[0][0])
        if isinstance(result, dict):
            summary = result.get("summary", {}) if isinstance(result.get("summary"), dict) else result
            if isinstance(summary, dict):
                summary.pop("embedding", None)
            return summary
        return {}

    async def create_insight(
        self,
        insight_text: str,
        embedding: list[float] | None = None,
    ) -> dict[str, Any]:
        created_at = _utc_now()
        params = {
            "insight_id": _new_id(),
            "insight_text": insight_text,
            "created_at": created_at,
            "embedding": embedding,
        }
        query = """
        CREATE (i:Insight {id: $insight_id, text: $insight_text, created_at: $created_at, embedding: $embedding})
        RETURN {insight: properties(i)} AS result
        """
        rows = await self._execute_cypher_with_retry(query, params)
        if not rows:
            return {}
        result = parse_agtype(rows[0][0])
        if isinstance(result, dict):
            insight = result.get("insight", {}) if isinstance(result.get("insight"), dict) else result
            if isinstance(insight, dict):
                insight.pop("embedding", None)
            return insight
        return {}

    async def link_detail_to_summary(self, detail_id: str, summary_id: str) -> None:
        await self._ensure_edge_label("HAS_DETAIL")
        params = {"detail_id": detail_id, "summary_id": summary_id}
        query = """
        MATCH (d:Detail {id: $detail_id})
        MATCH (t:Topic {id: $summary_id})
        MERGE (t)-[:HAS_DETAIL]->(d)
        RETURN {ok: true} AS result
        """
        await self._execute_cypher_with_retry(query, params)

    async def link_detail_to_insight(self, detail_id: str, insight_id: str) -> None:
        await self._ensure_edge_label("SUPPORTS_DETAIL")
        params = {"detail_id": detail_id, "insight_id": insight_id}
        query = """
        MATCH (d:Detail {id: $detail_id})
        MATCH (i:Insight {id: $insight_id})
        MERGE (i)-[:SUPPORTS_DETAIL]->(d)
        RETURN {ok: true} AS result
        """
        await self._execute_cypher_with_retry(query, params)

    async def link_insight_to_topic(self, insight_id: str, topic_id: str) -> None:
        await self._ensure_edge_label("HAS_INSIGHT")
        params = {"insight_id": insight_id, "topic_id": topic_id}
        query = """
        MATCH (i:Insight {id: $insight_id})
        MATCH (t:Topic {id: $topic_id})
        MERGE (t)-[:HAS_INSIGHT]->(i)
        RETURN {ok: true} AS result
        """
        await self._execute_cypher_with_retry(query, params)

    async def resolve_detail_id(self, detail_ref: str) -> str | None:
        params = {"detail_ref": detail_ref}
        query = """
        MATCH (d:Detail)
        WHERE d.id = $detail_ref OR d.text = $detail_ref
        RETURN {id: d.id} AS result
        LIMIT 1
        """
        rows = await self._age.execute_cypher(self._graph, query, params)
        if not rows:
            return None
        result = parse_agtype(rows[0][0])
        if isinstance(result, dict):
            return result.get("id")
        return None

    async def link_summary_to_cluster(self, summary_id: str, cluster_label: str) -> None:
        await self._ensure_edge_label("HAS_TOPIC")
        created_at = _utc_now()
        params = {
            "summary_id": summary_id,
            "cluster_label": cluster_label,
            "cluster_id": _new_id(),
            "created_at": created_at,
        }
        query = """
        MATCH (t:Topic {id: $summary_id})
        MERGE (c:Domain {label: $cluster_label})
        SET c.id = coalesce(c.id, $cluster_id),
            c.created_at = coalesce(c.created_at, $created_at)
        MERGE (c)-[:HAS_TOPIC]->(t)
        RETURN {ok: true} AS result
        """
        await self._execute_cypher_with_retry(query, params)

    async def list_pending_details(self, limit: int = 25) -> list[dict[str, Any]]:
        params = {"k": limit}
        query = """
        MATCH (d:Detail)
        WHERE coalesce(d.insight_pending, true) = true
        RETURN {id: d.id, text: d.text} AS result
        LIMIT $k
        """
        rows = await self._age.execute_cypher(self._graph, query, params)
        results: list[dict[str, Any]] = []
        for row in rows:
            result = parse_agtype(row[0])
            if isinstance(result, dict):
                results.append(result)
        return results

    async def mark_detail_insight_processed(self, detail_id: str) -> None:
        params = {"detail_id": detail_id, "processed_at": _utc_now()}
        query = """
        MATCH (d:Detail {id: $detail_id})
        SET d.insight_pending = false,
            d.insight_processed_at = $processed_at
        RETURN {ok: true} AS result
        """
        await self._age.execute_cypher(self._graph, query, params)

    async def get_detail_context(self, detail_id: str) -> dict[str, Any]:
        params = {"detail_id": detail_id}
        query = """
        MATCH (d:Detail {id: $detail_id})
        WITH d
        OPTIONAL MATCH (t:Topic)-[:HAS_DETAIL]->(d)
        WITH d, collect(distinct properties(t)) AS topics
        OPTIONAL MATCH (c:Domain)-[:HAS_TOPIC]->(:Topic)-[:HAS_DETAIL]->(d)
        WITH d, topics, collect(distinct properties(c)) AS domains
        RETURN {detail: properties(d), topics: topics, domains: domains} AS result
        """
        rows = await self._age.execute_cypher(self._graph, query, params)
        if not rows:
            return {}
        result = parse_agtype(rows[0][0])
        if not isinstance(result, dict):
            return {}
        detail = result.get("detail")
        if isinstance(detail, dict):
            detail.pop("embedding", None)
        topics = result.get("topics")
        if isinstance(topics, list):
            for topic in topics:
                if isinstance(topic, dict):
                    topic.pop("embedding", None)
        domains = result.get("domains")
        if isinstance(domains, list):
            for domain in domains:
                if isinstance(domain, dict):
                    domain.pop("embedding", None)
        return result

    async def list_insights_for_topics(self, topic_ids: list[str]) -> list[dict[str, Any]]:
        if not topic_ids:
            return []
        params = {"topic_ids": topic_ids}
        query = """
        MATCH (t:Topic)-[:HAS_INSIGHT]->(i:Insight)
        WHERE t.id IN $topic_ids
        RETURN {id: i.id, text: i.text} AS result
        """
        rows = await self._age.execute_cypher(self._graph, query, params)
        results: list[dict[str, Any]] = []
        for row in rows:
            result = parse_agtype(row[0])
            if isinstance(result, dict):
                results.append(result)
        return results

    async def list_insights_for_topic(self, topic_id: str) -> list[dict[str, Any]]:
        params = {"topic_id": topic_id}
        query = """
        MATCH (t:Topic {id: $topic_id})-[:HAS_INSIGHT]->(i:Insight)
        RETURN {id: i.id, text: i.text} AS result
        """
        rows = await self._age.execute_cypher(self._graph, query, params)
        results: list[dict[str, Any]] = []
        for row in rows:
            result = parse_agtype(row[0])
            if isinstance(result, dict):
                results.append(result)
        return results

    async def update_insight_text(self, insight_id: str, new_text: str) -> None:
        params = {"insight_id": insight_id, "insight_text": new_text}
        query = """
        MATCH (i:Insight {id: $insight_id})
        SET i.text = $insight_text
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
        params: dict[str, Any] = {}
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
        RETURN {{cluster: properties(c),
                summary: properties(t),
                detail: properties(d)}} AS result
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


def _flatten_results(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        cluster = row.get("cluster") or {}
        summary = row.get("summary") or {}
        detail = row.get("detail") or {}
        cluster_id = cluster.get("id") or cluster.get("label") or "cluster"
        summary_id = summary.get("id") or summary.get("text") or "topic"
        key = (str(cluster_id), str(summary_id))
        if key not in grouped:
            grouped[key] = {"cluster": cluster, "summary": summary, "details": []}
        if detail:
            grouped[key]["details"].append(detail)
    return list(grouped.values())
