import os

import asyncpg


async def connect() -> asyncpg.Connection:
    return await asyncpg.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "5432")),
        database=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        statement_cache_size=0,
    )
