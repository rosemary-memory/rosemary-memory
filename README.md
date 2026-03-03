# rosemary-memory

![](docs/img/example.png)

Agent memory that combines **graphs + vectors** (Postgres/Apache AGE + sentence-transformers embeddings) with `smolagents`.

Repeating yourself to an agent every time you use it isn’t intelligence, it’s amnesia. Rosemary sprinkles in the right amount of information so your agent can use the rest of its context to do something more useful.

## What You Get
- For builders: shrink prompt bloat, reuse memory across agents, and keep retrieval fast.
- For product teams: consistent personalization, explainable memory trails, and a shared profile layer across experiences.
- Structured knowledge you can browse, query, and visualize.

## Use Cases
- Personalization memory for chat assistants.
- Multi-agent workflows with shared memory.
- Long-lived user profiles and preferences.
- Agent reasoning over connected facts and insights.

## Integration Model
Rosemary acts as a shared memory layer:
- **Write**: store details, insights, and profile facts.
- **Retrieve**: inject only high-signal memories into an agent prompt.
- **Visualize**: inspect memory as a graph for debugging and product insight.

## How It Works
- Store details as memories.
- Retrieve the most relevant memories for a query.
- Generate insights that summarize and link details.
- Visualize everything as a graph.

## Architecture
Rosemary uses Apache AGE (graph on Postgres) to store Domains → Topics → Details → Insights, and sentence-transformers embeddings for vector retrieval. This lets agents recall relevant memories quickly while keeping an explicit, navigable graph for reasoning and explainability.

## Why Graph + Vectors
- Vectors find what’s relevant; graphs show how it connects.
- Explicit structure: Domains → Topics → Details.
- Multi-topic linking: a detail can live under multiple topics/domains.

![](docs/img/whoami.png)

## Quickstart
1. `uv venv`
2. `uv sync`
3. `export OPENAI_API_KEY=...`
4. `export DATABASE_URL=postgresql+asyncpg://rosemary:rosemary@localhost:5455/rosemary`
5. Optional: `export RETRIEVAL_MIN_SCORE=0.35`

## Demo (copy/paste)
```
uv run rosemary-memory store --text "I love shopping for fashion in Paris."
uv run rosemary-memory store --text "Looking for boutique hotels near the Louvre."
uv run rosemary-memory store --text "Interested in trying Michelin-starred restaurants in Paris."
uv run rosemary-memory store --text "Need a budget plan for my upcoming trip to London."
uv run rosemary-memory store --text "I want to visit art museums in Paris this summer."

uv run rosemary-memory retrieve --query "Paris"
uv run rosemary-memory retrieve --query "food"

uv run rosemary-memory export-graph
```

## Embeddings Service (Optional)
Keep the embedding model warm in a long‑running process:
```
uv run rosemary-memory serve-embeddings --host 127.0.0.1 --port 8765
export EMBEDDING_SERVICE_URL=http://127.0.0.1:8765
```

## Commands
Command-line interface for storing, retrieving, and exporting memory.
- Store: `rosemary-memory store --text "I love shopping for fashion in Paris."`
- Retrieve: `rosemary-memory retrieve --query "Paris"`
- Export graph: `rosemary-memory export-graph`
- Generate insights: `rosemary-memory generate-insights --limit 25`

## Developer Notes
- You control what gets stored and when (manual or agent-driven).
- Memory is durable and queryable (graph + vector retrieval).
- Works with OpenAI-compatible models via `smolagents`.

## Examples
- Frontier profile import: `uv run python examples/frontier_profile_import.py --path examples/example_data_extract.yaml`
- Generate insights after import: `uv run rosemary-memory generate-insights --limit 25`
- Visualize after import: `uv run rosemary-memory export-graph`

## Tests
- E2E smoke test (isolated test DB): `./tests/test_e2e.sh`. Uses `tests/docker-compose.test.yml` with its own compose project name. Defaults to `DATABASE_URL=postgresql+asyncpg://rosemary:rosemary@localhost:5456/rosemary_test`. Set `DATABASE_URL_TEST` to override.

## FAQ
**Is this a vector database?**  
It includes vector search via embeddings, but the core is a graph memory (Apache AGE on Postgres) with explicit relationships.

**Why not just use a vector store?**  
Vectors are great for recall; graphs make memory explainable and navigable. Rosemary uses both.

**Can I use this with any model?**  
Yes. It uses OpenAI-compatible models and exposes a CLI you can call from any agent or service.

**Tagline:** Graph + vector memory store for AI agents (Postgres/Apache AGE).

## License
- MIT (see `LICENSE`)

## Notes
- Domains use RIASEC (personal interests).
- Retrieval uses sentence‑transformers embeddings with a score threshold (`RETRIEVAL_MIN_SCORE`).
