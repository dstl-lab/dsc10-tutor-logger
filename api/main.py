import json
from html import escape

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

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


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(limit: int = 300):
    limit = min(limit, 10000)
    conn = await connect()
    try:
        rows = await conn.fetch(
            "SELECT id, event_type, user_email, payload, created_at "
            "FROM events ORDER BY id DESC LIMIT $1",
            limit,
        )
    finally:
        await conn.close()

    table_rows = ""
    for r in rows:
        payload = json.dumps(json.loads(r["payload"]) if r["payload"] else {})
        table_rows += (
            f"<tr>"
            f"<td>{r['id']}</td>"
            f"<td>{escape(r['event_type'])}</td>"
            f"<td>{escape(r['user_email'] or '')}</td>"
            f"<td class='payload'>{escape(payload)}</td>"
            f"<td>{r['created_at'].isoformat()}</td>"
            f"</tr>"
        )

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Events Dashboard</title>
<style>
  body {{ font-family: monospace; margin: 1rem; background: #fafafa; }}
  h1 {{ font-size: 1.1rem; margin-bottom: .5rem; }}
  table {{ border-collapse: collapse; width: 100%; font-size: .8rem; }}
  th, td {{ border: 1px solid #ccc; padding: 2px 6px; text-align: left; white-space: nowrap; }}
  th {{ background: #eee; position: sticky; top: 0; }}
  td.payload {{ max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  tr:hover {{ background: #e8f0fe; }}
</style>
</head>
<body>
<h1>Events ({len(rows)} rows)</h1>
<div style="overflow:auto; max-height:95vh;">
<table>
<thead><tr><th>id</th><th>event_type</th><th>user_email</th><th>payload</th><th>created_at</th></tr></thead>
<tbody>{table_rows}</tbody>
</table>
</div>
</body>
</html>"""


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
