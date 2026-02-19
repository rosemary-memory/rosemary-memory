from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
from pathlib import Path

from rosemary_memory.config import load_settings
from rosemary_memory.models.openai import build_openai_model
from rosemary_memory.storage.age import AgeClient
from rosemary_memory.memory.store import GraphStore
from rosemary_memory.memory.retrieval.retrieve import format_results
from rosemary_memory.memory.update.update import update_from_detail
from rosemary_memory.memory.export import build_graphviz_dot, default_snapshot_path
from rosemary_memory.agents.default import build_agent


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="rosemary-memory CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run agent with memory")
    run_parser.add_argument("--prompt", required=True, help="Prompt to run")
    run_parser.add_argument("--top-k", type=int, default=5, help="Memory results to fetch")
    run_parser.add_argument("--no-update", action="store_true", help="Skip memory update")

    store_parser = subparsers.add_parser("store", help="Store a memory detail")
    store_parser.add_argument("--text", required=True, help="Detail text to store")
    store_parser.add_argument("--source", default="cli", help="Source label")

    retrieve_parser = subparsers.add_parser("retrieve", help="Retrieve memory")
    retrieve_parser.add_argument("--query", required=True, help="Query text")
    retrieve_parser.add_argument("--top-k", type=int, default=5, help="Memory results to fetch")

    export_parser = subparsers.add_parser("export-graph", help="Export graph to Graphviz")
    export_parser.add_argument("--open", action="store_true", help="Open the exported file")
    export_parser.add_argument("--no-open", action="store_true", help="Do not open the file")
    export_parser.add_argument("--out-dir", default="snapshots", help="Output directory")
    export_parser.add_argument(
        "--format",
        default="png",
        choices=("png", "svg"),
        help="Export format",
    )

    return parser.parse_args()


def _run(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("CLI cannot run inside an active event loop")


async def _retrieve_once(database_url: str, graph_name: str, query: str, top_k: int) -> str:
    age = AgeClient(database_url)
    store = GraphStore(age, graph_name)
    await store.ensure_graph()
    results = await store.retrieve(query, top_k)
    await age.close()
    return format_results(results) if results else ""


def _store_once(
    database_url: str,
    graph_name: str,
    model,
    detail_text: str,
    source: str,
) -> None:
    update_from_detail(database_url, graph_name, model, detail_text, source=source)


def _run_sync(prompt: str, top_k: int, no_update: bool) -> int:
    settings = load_settings()
    model = build_openai_model(settings)
    agent = build_agent(model, settings.database_url, settings.age_graph_name)

    memory_context = ""
    if top_k > 0:
        memory_context = _run(_retrieve_once(settings.database_url, settings.age_graph_name, prompt, top_k))

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
        _store_once(settings.database_url, settings.age_graph_name, model, detail_text, source="cli")
    return 0


def _store_sync(text: str, source: str) -> int:
    settings = load_settings()
    model = build_openai_model(settings)
    _store_once(settings.database_url, settings.age_graph_name, model, text, source=source)
    return 0


def _retrieve_sync(query: str, top_k: int) -> int:
    settings = load_settings()
    output = _run(_retrieve_once(settings.database_url, settings.age_graph_name, query, top_k))
    if not output:
        output = "No relevant memory found."
    print(output)
    return 0


def _open_file(path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    elif os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def _render_graphviz(dot_content: str, out_path: Path, fmt: str) -> Path | None:
    result = subprocess.run(
        ["dot", f"-T{fmt}", "-o", str(out_path)],
        check=False,
        capture_output=True,
        text=True,
        input=dot_content,
    )
    if result.returncode != 0:
        print("Graphviz render failed. Is `dot` installed?", file=sys.stderr)
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        return None
    return out_path


def _export_graph_sync(out_dir: str, should_open: bool, fmt: str) -> int:
    settings = load_settings()
    dot_content = _run(build_graphviz_dot(settings.database_url, settings.age_graph_name))
    out_path = default_snapshot_path(Path(out_dir), fmt)
    rendered = _render_graphviz(dot_content, out_path, fmt)
    if rendered:
        print(f"Exported graph to {rendered}")
    else:
        print("Export failed.")
    if should_open:
        if rendered:
            _open_file(rendered)
    return 0


def main() -> int:
    args = _parse_args()
    if args.command == "run":
        return _run_sync(args.prompt, args.top_k, args.no_update)
    if args.command == "store":
        return _store_sync(args.text, args.source)
    if args.command == "retrieve":
        return _retrieve_sync(args.query, args.top_k)
    if args.command == "export-graph":
        should_open = args.open or not args.no_open
        return _export_graph_sync(args.out_dir, should_open, args.format)
    raise RuntimeError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
