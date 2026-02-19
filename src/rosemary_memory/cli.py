from __future__ import annotations

import argparse
import asyncio

from rosemary_memory.config import load_settings
from rosemary_memory.models.openai import build_openai_model
from rosemary_memory.storage.age import AgeClient
from rosemary_memory.memory.store import GraphStore
from rosemary_memory.memory.retrieval.retrieve import format_results
from rosemary_memory.memory.update.update import update_from_detail
from rosemary_memory.agents.default import build_agent


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run rosemary-memory agent")
    parser.add_argument("--prompt", required=True, help="Prompt to run")
    parser.add_argument("--top-k", type=int, default=5, help="Memory results to fetch")
    parser.add_argument("--no-update", action="store_true", help="Skip memory update")
    return parser.parse_args()


def _run(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("CLI cannot run inside an active event loop")


def _run_sync(prompt: str, top_k: int, no_update: bool) -> int:
    settings = load_settings()
    age = AgeClient(settings.database_url)
    store = GraphStore(age, settings.age_graph_name)
    _run(store.ensure_graph())

    model = build_openai_model(settings)
    agent = build_agent(model, store)

    memory_context = ""
    if top_k > 0:
        results = _run(store.retrieve(prompt, top_k))
        memory_context = format_results(results)

    final_prompt = prompt
    if memory_context:
        final_prompt = (
            f"{prompt}\n\nRelevant memory:\n{memory_context}\n\n"
            "If useful, you may call memory_retrieve or memory_update."
        )

    response = agent.run(final_prompt)
    print(response)

    if not no_update:
        detail_text = f"User: {prompt}\nAgent: {response}"
        _run(update_from_detail(store, model, detail_text, source="cli"))

    _run(age.close())
    return 0


def main() -> int:
    args = _parse_args()
    return _run_sync(args.prompt, args.top_k, args.no_update)


if __name__ == "__main__":
    raise SystemExit(main())
