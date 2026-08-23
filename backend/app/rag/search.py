"""Hybrid retrieval: pgvector cosine similarity + Postgres full-text search,
fused with Reciprocal Rank Fusion. The only module that issues retrieval SQL."""

import time

import asyncpg

from app.logging import EVT_RETRIEVAL, get_logger
from app.models.domain import RetrievedChunk

log = get_logger(__name__)

RRF_K = 60  # standard damping constant; rank 1 → 1/61, rank 10 → 1/70
CANDIDATES_PER_LEG = 30


def rrf_fuse(rankings: list[list[int]], k: int = RRF_K) -> list[int]:
    """Fuse ranked id lists: score(id) = Σ 1/(k + rank). Deterministic
    tie-break by id keeps tests stable."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=lambda cid: (-scores[cid], cid))


async def hybrid_search(
    pool: asyncpg.Pool,
    query_embedding: list[float],
    query_text: str,
    top_k: int,
) -> list[RetrievedChunk]:
    start = time.perf_counter()
    vec_literal = "[" + ",".join(f"{v:.6f}" for v in query_embedding) + "]"

    vector_rows = await pool.fetch(
        """SELECT id FROM chunks ORDER BY embedding <=> $1::vector LIMIT $2""",
        vec_literal, CANDIDATES_PER_LEG,
    )
    text_rows = await pool.fetch(
        """SELECT id FROM chunks, plainto_tsquery('english', $1) q
           WHERE tsv @@ q
           ORDER BY ts_rank(tsv, q) DESC LIMIT $2""",
        query_text, CANDIDATES_PER_LEG,
    )

    fused = rrf_fuse([[r["id"] for r in vector_rows], [r["id"] for r in text_rows]])[:top_k]
    if not fused:
        log.info(EVT_RETRIEVAL, query=query_text[:120], hit_count=0,
                 latency_ms=int((time.perf_counter() - start) * 1000))
        return []

    rows = await pool.fetch(
        """SELECT c.id AS chunk_id, c.speaker, c.start_ts, c.end_ts, c.content,
                  e.slug, e.title, e.guest, e.youtube_url
           FROM chunks c JOIN episodes e ON e.id = c.episode_id
           WHERE c.id = ANY($1::bigint[])""",
        fused,
    )
    by_id = {r["chunk_id"]: r for r in rows}
    results = [
        RetrievedChunk(
            chunk_id=cid,
            episode_slug=by_id[cid]["slug"],
            episode_title=by_id[cid]["title"],
            guest=by_id[cid]["guest"],
            youtube_url=by_id[cid]["youtube_url"],
            speaker=by_id[cid]["speaker"],
            start_ts=by_id[cid]["start_ts"],
            end_ts=by_id[cid]["end_ts"],
            content=by_id[cid]["content"],
            score=1.0 / (rank + 1),
        )
        for rank, cid in enumerate(fused)
        if cid in by_id
    ]
    log.info(EVT_RETRIEVAL, query=query_text[:120], hit_count=len(results),
             latency_ms=int((time.perf_counter() - start) * 1000))
    return results
