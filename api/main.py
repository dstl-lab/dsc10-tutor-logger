from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from db import close_pool, get_pool, init_pool
from models import EventIn


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    yield
    await close_pool()


app = FastAPI(title="DSC 10 Tutor Logging API", lifespan=lifespan)


@app.post("/events", status_code=201)
async def create_event(event: EventIn):
    pool = get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO events (event_type, user_email, payload)
        VALUES ($1, $2, $3::jsonb)
        RETURNING id, created_at
        """,
        event.event_type,
        event.user_email,
        __import__("json").dumps(event.payload),
    )
    return {"id": row["id"], "created_at": row["created_at"].isoformat()}


@app.get("/health")
async def health():
    try:
        pool = get_pool()
        await pool.fetchval("SELECT 1")
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
