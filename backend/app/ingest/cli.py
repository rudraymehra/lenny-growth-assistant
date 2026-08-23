"""Knowledge-base ingestion CLI.

    python -m app.ingest.cli [--refresh] [--limit N]

Idempotent: each episode's source file is sha256-hashed; unchanged episodes
are skipped, changed ones are re-chunked and re-embedded atomically (delete +
insert in one transaction). Every run writes an ingest_runs audit row, which
/config surfaces in the UI. --refresh forces re-processing of everything.
"""

import argparse
import asyncio
import hashlib
import sys
from datetime import date
from pathlib import Path

import asyncpg

from app.config import get_settings
from app.logging import EVT_INGEST, configure_logging, get_logger
from app.db.pool import apply_schema, create_pool
from app.rag.chunker import chunk_transcript
from app.rag.embedder import embed_texts

log = get_logger(__name__)


def _vec(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in values) + "]"


async def ingest(refresh: bool = False, limit: int | None = None) -> int:
    settings = get_settings()
    episodes_dir = Path(settings.transcripts_dir) / "episodes"
    if not episodes_dir.is_dir():
        print(f"ERROR: no transcripts at {episodes_dir}. Run scripts/fetch_transcripts.sh first.")
        return 1

    pool = await create_pool(settings.database_url)
    await apply_schema(pool)
    run_id = await pool.fetchval("INSERT INTO ingest_runs DEFAULT VALUES RETURNING id")

    seen = written = skipped = chunks_total = 0
    try:
        existing = {
            r["slug"]: r["content_hash"]
            for r in await pool.fetch("SELECT slug, content_hash FROM episodes")
        }
        paths = sorted(episodes_dir.glob("*/transcript.md"))
        if limit:
            paths = paths[:limit]

        for path in paths:
            seen += 1
            slug = path.parent.name
            raw = path.read_text(encoding="utf-8", errors="replace")
            content_hash = hashlib.sha256(raw.encode()).hexdigest()
            if not refresh and existing.get(slug) == content_hash:
                skipped += 1
                continue

            meta, chunks = chunk_transcript(raw, slug)
            if not chunks:
                log.warning(EVT_INGEST, slug=slug, detail="no chunks parsed — skipped")
                skipped += 1
                continue
            embeddings = await asyncio.to_thread(
                embed_texts, [c.content for c in chunks], settings.embedding_model
            )

            publish_date = None
            if meta.publish_date:
                try:
                    publish_date = date.fromisoformat(meta.publish_date[:10])
                except ValueError:
                    publish_date = None

            async with pool.acquire() as conn, conn.transaction():
                await conn.execute("DELETE FROM episodes WHERE slug = $1", slug)
                episode_id = await conn.fetchval(
                    """INSERT INTO episodes (slug, guest, title, youtube_url, video_id,
                                             publish_date, description, keywords,
                                             content_hash, chunk_count)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) RETURNING id""",
                    slug, meta.guest, meta.title, meta.youtube_url, meta.video_id,
                    publish_date, meta.description, meta.keywords, content_hash, len(chunks),
                )
                await conn.executemany(
                    """INSERT INTO chunks (episode_id, chunk_index, speaker, start_ts,
                                           end_ts, content, token_count, embedding)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8::vector)""",
                    [
                        (episode_id, c.chunk_index, c.speaker, c.start_ts, c.end_ts,
                         c.content, c.token_count, _vec(e))
                        for c, e in zip(chunks, embeddings)
                    ],
                )
            written += 1
            chunks_total += len(chunks)
            if written % 25 == 0:
                print(f"  ... {written} episodes ingested ({chunks_total} chunks)")

        await pool.execute(
            """UPDATE ingest_runs SET finished_at = now(), status = 'succeeded',
               episodes_seen=$2, episodes_written=$3, episodes_skipped=$4, chunks_written=$5
               WHERE id = $1""",
            run_id, seen, written, skipped, chunks_total,
        )
        log.info(EVT_INGEST, status="succeeded", episodes_seen=seen,
                 episodes_written=written, episodes_skipped=skipped, chunks_written=chunks_total)
        print(f"Ingest complete: {seen} seen, {written} written, {skipped} unchanged, "
              f"{chunks_total} chunks.")
        return 0
    except Exception as exc:
        await pool.execute(
            "UPDATE ingest_runs SET finished_at = now(), status = 'failed', error = $2 WHERE id = $1",
            run_id, str(exc)[:2000],
        )
        log.error(EVT_INGEST, status="failed", error=str(exc))
        raise
    finally:
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Lenny's Podcast transcripts")
    parser.add_argument("--refresh", action="store_true", help="re-process unchanged episodes")
    parser.add_argument("--limit", type=int, default=None, help="ingest only the first N episodes")
    args = parser.parse_args()
    configure_logging(get_settings().log_level)
    sys.exit(asyncio.run(ingest(refresh=args.refresh, limit=args.limit)))


if __name__ == "__main__":
    main()
