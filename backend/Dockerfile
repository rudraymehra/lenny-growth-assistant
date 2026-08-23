# Backend image: FastAPI app + Claude Agent SDK + in-process embeddings.
FROM python:3.12-slim

# git is not required at runtime; curl only for debugging convenience.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /srv

# Install dependencies first for layer caching.
COPY pyproject.toml ./
RUN uv pip install --system -r pyproject.toml --group dev

# Pre-bake the embedding model so first ingest doesn't download ~130MB mid-demo.
ENV FASTEMBED_CACHE_PATH=/opt/fastembed-cache
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')"

COPY app ./app
COPY tests ./tests
COPY workspace ./workspace

# The Agent SDK spawns a bundled CLI subprocess; give it a writable HOME.
ENV HOME=/tmp
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
