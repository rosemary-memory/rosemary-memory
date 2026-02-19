from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


class AgeClient:
    def __init__(self, database_url: str) -> None:
        self._engine: AsyncEngine = create_async_engine(database_url, future=True)

    async def close(self) -> None:
        await self._engine.dispose()

    async def _prepare_conn(self, conn) -> None:
        await conn.execute(text("LOAD 'age';"))
        await conn.execute(text('SET search_path = ag_catalog, "$user", public;'))

    async def execute_sql(self, sql: str, params: dict[str, Any] | None = None) -> list[Any]:
        async with self._engine.begin() as conn:
            await self._prepare_conn(conn)
            result = await conn.execute(text(sql), params or {})
            try:
                rows = result.fetchall()
            except Exception:
                rows = []
            return rows

    async def execute_cypher(
        self,
        graph_name: str,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> list[Any]:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", graph_name):
            raise ValueError(f"Invalid graph name: {graph_name!r}")

        quoted_query = _dollar_quote(query)
        params_json = json.dumps(params or {})
        sql = (
            f"SELECT * FROM cypher('{graph_name}', {quoted_query}, CAST($1 AS agtype)) "
            "AS (result agtype);"
        )
        async with self._engine.begin() as conn:
            await self._prepare_conn(conn)
            result = await conn.exec_driver_sql(sql, (params_json,))
            try:
                rows = result.fetchall()
            except Exception:
                rows = []
            return rows


def parse_agtype(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _dollar_quote(text: str) -> str:
    delimiter = "$q$"
    counter = 0
    while delimiter in text:
        counter += 1
        delimiter = f"$q{counter}$"
    return f"{delimiter}{text}{delimiter}"
