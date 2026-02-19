## rosemary-memory

Agent-driven memory system backed by Apache AGE (Postgres graph extension) and `smolagents`.

### Setup
1. `uv venv`
2. `uv sync`
3. `docker compose up -d`
4. Optional: copy `.env.example` to `.env` and fill in values
5. Or use `./scripts/start.sh` to bootstrap env + db

### Environment
- `OPENAI_API_KEY` (required)
- `OPENAI_MODEL` (default: `gpt-4o-mini`)
- `OPENAI_BASE_URL` (optional)
- `DATABASE_URL` (required)
- `AGE_GRAPH_NAME` (default: `gmemory`)

Example `DATABASE_URL` for the docker compose setup:
- `postgresql+asyncpg://rosemary:rosemary@localhost:5455/rosemary`

### Run
```
rosemary-memory run --prompt "Remember that my favorite theme is warm minimalism"
rosemary-memory store --text "My favorite theme is warm minimalism"
rosemary-memory retrieve --query "favorite theme"
rosemary-memory export-graph
rosemary-memory export-graph --format png
rosemary-memory export-graph --format svg
```

### What it does
- Clusters details into coarse topics (LLM-based)
- Stores `Cluster → Summary → Detail` nodes in AGE
- Retrieves memory and feeds it into the agent loop

### Notes
- Update `pyproject.toml` if you want stricter dependency pins.
