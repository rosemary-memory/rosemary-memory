from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any

from smolagents import ToolCallingAgent, tool

from rosemary_memory.config import load_settings
from rosemary_memory.models.openai import build_openai_model
from rosemary_memory.memory.update.update import update_from_detail


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import a frontier chat YAML profile into rosemary-memory.")
    parser.add_argument(
        "--path",
        default=str(Path(__file__).resolve().parents[0] / "example_data_extract.yaml"),
        help="Path to YAML profile file",
    )
    parser.add_argument(
        "--max-paragraphs",
        type=int,
        default=10,
        help="Max paragraphs to draft",
    )
    return parser.parse_args()


def _load_yaml_text(path: str) -> str:
    content = Path(path).read_text(encoding="utf-8")
    return content.strip()


def _run(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("This script cannot run inside an active event loop.")


async def _store_paragraphs(
    paragraphs: list[str],
    database_url: str,
    graph_name: str,
    source: str,
) -> dict[str, Any]:
    async def _one(text: str) -> dict[str, Any]:
        model = build_openai_model(load_settings())
        return await asyncio.to_thread(update_from_detail, database_url, graph_name, model, text, source=source)

    results = await asyncio.gather(*[_one(p) for p in paragraphs])
    return {"stored": len(results), "details": results}


def main() -> int:
    args = _parse_args()
    settings = load_settings()
    model = build_openai_model(settings)
    yaml_text = _load_yaml_text(args.path)

    @tool
    def save_paragraphs(paragraphs: list[str]) -> dict[str, Any]:
        """Persist selected paragraphs to memory.

        Args:
            paragraphs: Paragraphs to store in memory.
        """
        return _run(_store_paragraphs(paragraphs, settings.database_url, settings.age_graph_name, source="frontier-profile"))

    agent = ToolCallingAgent(
        tools=[save_paragraphs],
        model=model,
    )

    prompt = "\n".join(
        [
            "You are a frontier chat agent reading a YAML user profile.",
            "Goal: write short natural-language paragraphs (2-4 sentences each) describing what you understand about the user.",
            f"Draft up to {args.max_paragraphs} paragraphs.",
            "Then choose the most stable/high-confidence paragraphs to save.",
            "Call save_paragraphs with ONLY the paragraphs you want to persist.",
            "",
            "YAML profile:",
            yaml_text,
        ]
    )

    response = agent.run(prompt)
    print(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
