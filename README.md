# rosemary-memory

![](docs/img/whoami.png)

Agent memory that combines **graphs + vectors** (Postgres/Apache AGE + sentence-transformers embeddings) with `smolagents`.

## Why a graph (vs vectors)?
- Explicit structure: Domains → Topics → Details.
- Multi‑topic linking: a detail can live under multiple topics/domains.

![](docs/img/example.png)

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
- Store: `rosemary-memory store --text "I love shopping for fashion in Paris."`
- Retrieve: `rosemary-memory retrieve --query "Paris"`
- Export graph: `rosemary-memory export-graph`
- Generate insights: `rosemary-memory generate-insights --limit 25`

## License
- MIT (see `LICENSE`)

## Notes
- Domains use RIASEC (personal interests).
- Retrieval uses sentence‑transformers embeddings with a score threshold (`RETRIEVAL_MIN_SCORE`).
