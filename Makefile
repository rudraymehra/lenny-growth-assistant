# The Lenny Growth Assistant — operator entry points.
# `make demo` is the one-command startup documented in the README.

.PHONY: demo up down build ingest ingest-refresh test eval logs ps clean fetch-data

demo: ## One-command startup: data + ollama + compose + ingest + browser
	./scripts/demo.sh

up: ## Start the stack without the demo niceties
	docker compose up -d --build

down:
	docker compose down

build:
	docker compose build

fetch-data: ## Shallow-clone the transcript dataset into ./data
	./scripts/fetch_transcripts.sh

ingest: ## Ingest transcripts (idempotent: unchanged episodes are skipped)
	docker compose exec backend python -m app.ingest.cli

ingest-refresh: ## Force re-chunk + re-embed of all episodes
	docker compose exec backend python -m app.ingest.cli --refresh

test: ## Backend unit + integration tests (uses the lenny_test database)
	docker compose exec backend pytest tests/unit tests/integration -q

eval: ## Golden-set retrieval eval against the real knowledge base
	docker compose exec backend pytest tests/evals -q -s

logs:
	docker compose logs -f backend

ps:
	docker compose ps

clean: ## Stop everything and delete volumes (destroys the database)
	docker compose down -v
