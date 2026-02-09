import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from db import connect
from models import EventIn

app = FastAPI(title="DSC 10 Tutor Logging API")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost(:\d+)?|.*\.localhost(:\d+)?|datahub\.ucsd\.edu)$",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/events", status_code=201)
async def create_event(event: EventIn):
    conn = await connect()
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO events (event_type, user_email, payload)
            VALUES ($1, $2, $3::jsonb)
            RETURNING id, created_at
            """,
            event.event_type,
            event.user_email,
            json.dumps(event.payload),
        )
        return {"id": row["id"], "created_at": row["created_at"].isoformat()}
    finally:
        await conn.close()


@app.get("/health")
async def health():
    try:
        conn = await connect()
        try:
            await conn.fetchval("SELECT 1")
        finally:
            await conn.close()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
