"""Golden-set retrieval eval (hit@5 by episode).

Runs against the REAL ingested knowledge base (production database), so it is
excluded from `make test` and run via `make eval`. This is the quantitative
answer to "how do you know retrieval works?" — extend the YAML as usage
reveals new question shapes.
"""

import asyncio
import os
from pathlib import Path

import asyncpg
import pytest
import yaml

from app.config import get_settings
from app.rag.embedder import embed_query
from app.rag.search import hybrid_search

GOLDEN = yaml.safe_load((Path(__file__).parent / "golden_set.yaml").read_text())
HIT_AT = 5
PASS_THRESHOLD = 0.80

DATABASE_URL = os.environ.get("DATABASE_URL", get_settings().database_url)


def _hit(retrieved_slugs: list[str], expected: list[str]) -> bool:
    # prefix match tolerates multi-episode guests (elena-verna-20 etc.)
    return any(r.startswith(e) for r in retrieved_slugs for e in expected)


async def _run() -> tuple[int, list[tuple[str, bool, list[str]]]]:
    settings = get_settings()
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=2)
    try:
        chunk_count = await pool.fetchval("SELECT count(*) FROM chunks")
        if chunk_count == 0:
            pytest.skip("Knowledge base is empty — run `make ingest` first.")
        rows = []
        hits = 0
        for case in GOLDEN:
            question, expected = case["question"], case["expected"]
            embedding = await asyncio.to_thread(embed_query, question, settings.embedding_model)
            results = await hybrid_search(pool, embedding, question, top_k=12)
            episode_slugs: list[str] = []
            for r in results:  # unique episodes, retrieval order
                if r.episode_slug not in episode_slugs:
                    episode_slugs.append(r.episode_slug)
            top = episode_slugs[:HIT_AT]
            ok = _hit(top, expected)
            hits += ok
            rows.append((question, ok, top))
        return hits, rows
    finally:
        await pool.close()


def test_retrieval_hit_at_5():
    hits, rows = asyncio.run(_run())
    total = len(rows)
    print(f"\n{'':2}{'hit':4} question → top-{HIT_AT} episodes")
    for question, ok, top in rows:
        print(f"  {'PASS' if ok else 'FAIL':4} {question[:70]}")
        print(f"       → {', '.join(top)}")
    rate = hits / total
    print(f"\n  hit@{HIT_AT}: {hits}/{total} = {rate:.0%} (threshold {PASS_THRESHOLD:.0%})")
    assert rate >= PASS_THRESHOLD, f"retrieval hit@{HIT_AT} {rate:.0%} below {PASS_THRESHOLD:.0%}"
