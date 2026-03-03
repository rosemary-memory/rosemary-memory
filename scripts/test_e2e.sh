#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

if [[ -f ".env" ]]; then
  # shellcheck disable=SC2046
  export $(grep -v '^#' .env | xargs) || true
fi

if [[ -z "${AGE_GRAPH_NAME:-}" ]]; then
  export AGE_GRAPH_NAME=gmemory_test
fi

if [[ -n "${DATABASE_URL_TEST:-}" ]]; then
  export DATABASE_URL="${DATABASE_URL_TEST}"
else
  export DATABASE_URL="postgresql+asyncpg://rosemary:rosemary@localhost:5456/rosemary_test"
fi

echo "[e2e] Starting test database..."
docker compose -f docker-compose.yml -f docker-compose.test.yml up -d postgres_test

echo "[e2e] Checking env vars..."
if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "[e2e] ERROR: DATABASE_URL is not set"
  exit 1
fi

echo "[e2e] Resetting graph..."
psql "$DATABASE_URL" -c "SELECT drop_graph('${AGE_GRAPH_NAME}', true);" >/dev/null 2>&1 || true

echo "[e2e] Storing seed details..."
uv run rosemary-memory store --text "Interested in trying Michelin-starred restaurants in Paris."
uv run rosemary-memory store --text "I love shopping for fashion in Paris."
uv run rosemary-memory store --text "Looking for boutique hotels near the Louvre."
uv run rosemary-memory store --text "Need a budget plan for my upcoming trip to London."
uv run rosemary-memory store --text "I want to visit art museums in Paris this summer."
uv run rosemary-memory store --text "Prefers early-morning workouts and quiet cafes."
uv run rosemary-memory store --text "Allergic to shellfish; avoids seafood restaurants."
uv run rosemary-memory store --text "Planning a weekend hike near Yosemite."
uv run rosemary-memory store --text "Interested in jazz clubs and live music venues."
uv run rosemary-memory store --text "Works remotely; needs reliable hotel Wi-Fi."

echo "[e2e] Generating insights..."
uv run rosemary-memory generate-insights --limit 25 >/dev/null 2>&1 || true

echo "[e2e] Retrieving..."
uv run rosemary-memory retrieve --query "What food does the user like?"
uv run rosemary-memory retrieve --query "Paris"

echo "[e2e] Exporting graph..."
uv run rosemary-memory export-graph >/dev/null

echo "[e2e] Done."
echo "[e2e] To tear down test DB:"
echo "       docker compose -f docker-compose.yml -f docker-compose.test.yml down -v"
