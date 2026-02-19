# rosemary-memory

Agent memory with Postgres (Apache AGE) + `smolagents`.

## Quickstart
1. `uv venv`
2. `uv sync`
3. `docker compose up -d`
4. `export OPENAI_API_KEY=...`
5. `export DATABASE_URL=postgresql+asyncpg://rosemary:rosemary@localhost:5455/rosemary`

## Commands
- Store: `rosemary-memory store --text "I love shopping for fashion in Paris."`
- Retrieve: `rosemary-memory retrieve --query "Paris"`
- Export graph: `rosemary-memory export-graph`

## Notes
- Domains use RIASEC (personal interests).
- `.env.example` shows all supported env vars.
