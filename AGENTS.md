# Repository Guidelines

## Project Structure & Module Organization
- `src/rosemary_memory/`: Core package code.
  - `agents/`: Agent wiring and tool registration.
  - `memory/`: Memory store, retrieval, and update logic.
  - `models/`: Model factories (OpenAI-compatible).
  - `storage/`: Database adapters (Apache AGE/Postgres).
  - `tools/`: Tool functions exposed to agents.
- `examples/`: Small runnable scripts.
- `tests/`: Unit tests.
- `scripts/`: SQL init and setup helpers.
- `docker-compose.yml`: Local Postgres + AGE service.

## Build, Test, and Development Commands
- `uv venv`: Create a local virtual environment.
- `uv sync`: Install dependencies from `pyproject.toml`.
- `docker compose up -d`: Start Postgres with Apache AGE.
- `./scripts/start.sh`: Bootstrap env + db (uses `.env` if present).
- `rosemary-memory run --prompt "..."`: Run the CLI agent.
- `rosemary-memory store --text "..."`: Store a detail in memory.
- `rosemary-memory retrieve --query "..."`: Retrieve memory.
- `rosemary-memory export-graph`: Export Graphviz to `snapshots/` (default `png`, supports `svg`).
- `python -m unittest`: Run tests.

## Coding Style & Naming Conventions
- Python 3.11+.
- 4-space indentation, PEP 8 naming.
- `snake_case` for functions/variables, `PascalCase` for classes.
- Keep modules small and focused; prefer clear, explicit names.

## Testing Guidelines
- Framework: `unittest`.
- Test files named `test_*.py` under `tests/`.
- Prefer small, fast tests; integration tests should be opt-in and skip when env vars are missing.

## Commit & Pull Request Guidelines
- Git history currently only has the initial commit, so no established convention yet.
- Recommended: concise, present-tense commit messages (e.g., `Add AGE storage adapter`).
- PRs should include:
  - A short description of changes and rationale.
  - Any required setup steps or env vars.
  - Test results or a note if tests were not run.

## Configuration & Security
- Required env vars: `OPENAI_API_KEY`, `DATABASE_URL`.
- Optional: `OPENAI_MODEL`, `OPENAI_BASE_URL`, `AGE_GRAPH_NAME`.
- Do not commit secrets or `.env` files.
- `.env.example` shows expected variables.
