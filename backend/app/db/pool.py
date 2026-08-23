"""asyncpg connection pool lifecycle + startup schema application."""

from pathlib import Path

import asyncpg

from app.logging import EVT_DB_ERROR, get_logger

log = get_logger(__name__)

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


async def create_pool(database_url: str) -> asyncpg.Pool:
    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=8, command_timeout=30)
    return pool


async def apply_schema(pool: asyncpg.Pool) -> None:
    schema = SCHEMA_PATH.read_text()
    async with pool.acquire() as conn:
        await conn.execute(schema)


async def check_db(pool: asyncpg.Pool) -> tuple[bool, float]:
    """Readiness probe: round-trip latency in ms, or (False, 0)."""
    import time

    try:
        start = time.perf_counter()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True, (time.perf_counter() - start) * 1000
    except Exception as exc:  # noqa: BLE001 — readiness must never raise
        log.warning(EVT_DB_ERROR, detail=str(exc))
        return False, 0.0
