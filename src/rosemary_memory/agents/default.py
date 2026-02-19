from __future__ import annotations

from smolagents import CodeAgent

from rosemary_memory.tools.memory_tools import build_memory_tools


def build_agent(model, database_url: str, graph_name: str) -> CodeAgent:
    tools = build_memory_tools(database_url, graph_name, model)
    return CodeAgent(
        tools=tools,
        model=model,
        add_base_tools=False,
    )
