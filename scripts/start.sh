#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ -f .env ]; then
  # shellcheck disable=SC1091
  source .env
fi

if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "OPENAI_API_KEY is required. Set it in your shell or .env." >&2
  exit 1
fi

if [ -z "${DATABASE_URL:-}" ]; then
  export DATABASE_URL="postgresql+asyncpg://rosemary:rosemary@localhost:5455/rosemary"
  echo "DATABASE_URL not set; defaulting to $DATABASE_URL"
fi

uv venv
uv sync

docker compose up -d

echo "Environment ready."
