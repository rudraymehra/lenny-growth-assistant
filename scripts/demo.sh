#!/usr/bin/env bash
# One-command demo startup. Safe to re-run: every step is idempotent.
#   1. Fetch the transcript dataset (skipped if present)
#   2. Verify Ollama is reachable and the local model is pulled (local provider)
#   3. Build + start the compose stack
#   4. Wait for readiness, ingest the knowledge base (hash-idempotent)
#   5. Open the app
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OLLAMA_MODEL="$(grep -E '^OLLAMA_MODEL=' .env 2>/dev/null | cut -d= -f2 || true)"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen3:4b}"
OLLAMA_HOST_URL="http://localhost:11434"

step() { printf '\n\033[1;36m▸ %s\033[0m\n' "$1"; }

step "1/5 Transcript dataset"
./scripts/fetch_transcripts.sh

step "2/5 Ollama (local provider)"
if curl -sf "$OLLAMA_HOST_URL/api/version" >/dev/null 2>&1; then
  if curl -sf "$OLLAMA_HOST_URL/api/tags" | grep -q "\"$OLLAMA_MODEL\"" 2>/dev/null; then
    echo "Ollama is up and $OLLAMA_MODEL is available."
  else
    echo "Ollama is up; pulling $OLLAMA_MODEL (one-time download) ..."
    ollama pull "$OLLAMA_MODEL"
  fi
else
  echo "WARNING: Ollama is not reachable at $OLLAMA_HOST_URL."
  echo "  Install + start it:   brew install ollama && brew services start ollama"
  echo "  Then pull the model:  ollama pull $OLLAMA_MODEL"
  echo "  Continuing anyway — the app will use the cloud provider if an"
  echo "  ANTHROPIC_API_KEY is configured, and will show a setup card if not."
fi

step "3/5 Build + start containers"
docker compose up -d --build

step "4/5 Readiness + knowledge-base ingest"
printf 'Waiting for backend readiness'
for i in $(seq 1 60); do
  if curl -sf http://localhost:8000/api/v1/health/ready >/dev/null 2>&1; then
    echo " — ready."
    break
  fi
  printf '.'
  sleep 2
  if [[ "$i" == 60 ]]; then
    echo; echo "Backend did not become ready. Inspect with: make logs"; exit 1
  fi
done
docker compose exec backend python -m app.ingest.cli

step "5/5 Open the app"
echo "Frontend:  http://localhost:3000"
echo "API docs:  http://localhost:8000/docs"
command -v open >/dev/null && open http://localhost:3000 || true
