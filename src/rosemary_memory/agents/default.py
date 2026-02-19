from __future__ import annotations

from smolagents import CodeAgent

from rosemary_memory.tools.memory_tools import build_memory_tools


def build_agent(model, store) -> CodeAgent:
    tools = build_memory_tools(store, model)
    return CodeAgent(
        tools=tools,
        model=model,
        add_base_tools=False,
    )
