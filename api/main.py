import hashlib
import hmac
import json
import os
from html import escape
from urllib.parse import quote

from fastapi import Cookie, FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse

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


DASHBOARD_CSS = """
  body { font-family: monospace; margin: 1rem; background: #fafafa; }
  h1 { font-size: 1.1rem; margin-bottom: .5rem; }
  a { color: #1a73e8; }
  .nav { margin-bottom: 1rem; font-size: .85rem; }
  /* notebook list */
  .notebook-list { list-style: none; padding: 0; }
  .notebook-list li { padding: 4px 0; border-bottom: 1px solid #eee; }
  .notebook-list .cnt { color: #888; margin-left: .5rem; }
  /* student sections */
  details { margin-bottom: .75rem; border: 1px solid #ddd; border-radius: 4px; background: #fff; }
  summary { cursor: pointer; padding: 6px 10px; background: #f5f5f5; font-weight: bold; font-size: .85rem; }
  summary:hover { background: #e8f0fe; }
  .messages { padding: 8px 12px; }
  .msg { margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid #f0f0f0; }
  .msg:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
  .msg-time { font-size: .75rem; color: #888; }
  .msg-type { font-size: .75rem; color: #555; background: #eee; padding: 1px 5px; border-radius: 3px; }
  .msg-chatgpt { font-size: .75rem; color: #fff; background: #e53935; padding: 1px 5px; border-radius: 3px; margin-left: 4px; }
  .msg-q { margin: 4px 0; padding: 6px 8px; background: #e3f2fd; border-radius: 4px; white-space: pre-wrap; }
  .msg-a { margin: 4px 0; padding: 6px 8px; background: #f1f8e9; border-radius: 4px; white-space: pre-wrap; }
  /* flat table fallback */
  table { border-collapse: collapse; width: 100%; font-size: .8rem; }
  th, td { border: 1px solid #ccc; padding: 2px 6px; text-align: left; white-space: nowrap; }
  th { background: #eee; position: sticky; top: 0; }
  td.payload { max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  tr:hover { background: #e8f0fe; }
"""


def _html_page(title: str, body: str) -> str:
    return (
        f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>{title}</title><style>{DASHBOARD_CSS}</style></head>"
        f"<body>{body}"
        "<script>document.querySelectorAll('time[datetime]').forEach(el=>{"
        "const d=new Date(el.getAttribute('datetime'));"
        "el.textContent=d.toLocaleString(undefined,{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});"
        "})</script></body></html>"
    )


def _make_token(password: str) -> str:
    return hmac.HMAC(b"dsc10-dashboard", password.encode(), hashlib.sha256).hexdigest()


def _check_auth(token: str | None) -> bool:
    if not token:
        return False
    expected = _make_token(os.environ["DB_PASSWORD"])
    return hmac.compare_digest(token, expected)


def _login_page(error: str = "") -> str:
    err_html = f"<p style='color:#c62828;font-size:.85rem'>{escape(error)}</p>" if error else ""
    body = (
        "<h1>Dashboard Login</h1>"
        f"{err_html}"
        "<form method='post' action='/dashboard/login'>"
        "<input type='password' name='password' placeholder='Password' "
        "style='font-family:monospace;padding:6px 8px;font-size:.9rem;width:260px' autofocus>"
        " <button type='submit' style='padding:6px 12px;font-size:.9rem'>Log in</button>"
        "</form>"
    )
    return _html_page("Dashboard — Login", body)


@app.post("/dashboard/login", response_class=HTMLResponse)
async def dashboard_login(password: str = Form()):
    if not hmac.compare_digest(password, os.environ["DB_PASSWORD"]):
        return HTMLResponse(_login_page("Wrong password."), status_code=401)
    resp = RedirectResponse("/dashboard", status_code=303)
    resp.set_cookie("dash_token", _make_token(password), httponly=True, samesite="lax")
    return resp


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(notebook: str | None = None, dash_token: str | None = Cookie(None)):
    if not _check_auth(dash_token):
        return HTMLResponse(_login_page())
    conn = await connect()
    try:
        if notebook is None:
            return await _dashboard_notebook_list(conn)
        return await _dashboard_notebook_detail(conn, notebook)
    finally:
        await conn.close()


async def _dashboard_notebook_list(conn) -> str:
    rows = await conn.fetch(
        "SELECT payload->>'notebook' AS notebook, COUNT(*) AS cnt "
        "FROM events "
        "WHERE payload->>'notebook' IS NOT NULL "
        "GROUP BY payload->>'notebook' "
        "ORDER BY cnt DESC"
    )
    items = ""
    for r in rows:
        raw_nb = r["notebook"]
        nb = escape(raw_nb)
        items += (
            f"<li><a href='/dashboard?notebook={quote(raw_nb)}'>{nb}</a>"
            f"<span class='cnt'>({r['cnt']} events)</span></li>"
        )
    body = (
        f"<h1>Notebooks ({len(rows)})</h1>"
        f"<ul class='notebook-list'>{items}</ul>"
    )
    return _html_page("Dashboard — Notebooks", body)


async def _dashboard_notebook_detail(conn, notebook: str) -> str:
    rows = await conn.fetch(
        "SELECT id, event_type, user_email, payload, created_at "
        "FROM events "
        "WHERE payload->>'notebook' = $1 "
        "ORDER BY user_email, created_at",
        notebook,
    )

    # Group by user_email
    groups: dict[str, list] = {}
    for r in rows:
        email = r["user_email"] or "(unknown)"
        groups.setdefault(email, []).append(r)

    sections = ""
    for email, events in groups.items():
        msgs = ""
        for ev in events:
            payload = json.loads(ev["payload"]) if ev["payload"] else {}
            question = escape(payload.get("question", ""))
            response = escape(payload.get("response", ""))
            ts_iso = ev["created_at"].strftime("%Y-%m-%dT%H:%M:%SZ")
            ts_display = ev["created_at"].strftime("%Y-%m-%d %H:%M")
            ev_type = escape(ev["event_type"])
            msgs += f"<div class='msg'>"
            chatgpt = payload.get("mode") == "chatgpt"
            mode_badge = " <span class='msg-chatgpt'>ChatGPT</span>" if chatgpt else ""
            msgs += f"<time datetime='{ts_iso}' class='msg-time'>{ts_display}</time> <span class='msg-type'>{ev_type}</span>{mode_badge}"
            if question:
                msgs += f"<div class='msg-q'>{question}</div>"
            if response:
                msgs += f"<div class='msg-a'>{response}</div>"
            msgs += "</div>"
        sections += (
            f"<details><summary>{escape(email)} ({len(events)} events)</summary>"
            f"<div class='messages'>{msgs}</div></details>"
        )

    nav = f"<div class='nav'><a href='/dashboard'>&larr; All notebooks</a></div>"
    body = (
        f"{nav}<h1>{escape(notebook)}</h1>"
        f"<p style='font-size:.85rem;color:#555'>{len(rows)} events, {len(groups)} students</p>"
        f"{sections}"
    )
    return _html_page(f"Dashboard — {escape(notebook)}", body)


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
