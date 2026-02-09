"""Dump the entire events table to a Parquet file.

Usage:
    python dump_to_parquet.py              # writes events.parquet
    python dump_to_parquet.py out.parquet   # writes out.parquet

Requires DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD env vars.
"""

import asyncio
import os
import sys
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
import pyarrow as pa
import pyarrow.parquet as pq


async def dump():
    conn = await asyncpg.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "5432")),
        database=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    )

    rows = await conn.fetch("SELECT id, event_type, user_email, payload::text, created_at FROM events ORDER BY id")
    await conn.close()

    table = pa.table({
        "id": pa.array([r["id"] for r in rows], type=pa.int32()),
        "event_type": pa.array([r["event_type"] for r in rows], type=pa.string()),
        "user_email": pa.array([r["user_email"] for r in rows], type=pa.string()),
        "payload": pa.array([r["payload"] for r in rows], type=pa.string()),
        "created_at": pa.array([r["created_at"] for r in rows], type=pa.timestamp("us", tz="UTC")),
    })

    out = sys.argv[1] if len(sys.argv) > 1 else "events.parquet"
    pq.write_table(table, out)
    print(f"Wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    asyncio.run(dump())
