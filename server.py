import asyncio
import json
import os
import re
from datetime import date
from pathlib import Path

import litellm
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

load_dotenv()

from agent import run as agent_run
from agent.models import litellm_kwargs as _litellm_kwargs
from auth import AUTH_ENABLED, USERS, check_credentials, get_current_user, make_token, verify_token
from config import MODEL, get_available_models
from persistence import db as persistence_db
from rate_limit import RateLimiter
from errors import friendly_error
from export import generate_dashboard, generate_report
from instellingen import get_all as get_all_instellingen, load_dashboard as load_dashboard_data
from tools.catalog import _cbs as _cbs_catalog, _rio_duo as _rio_duo_catalog

app = FastAPI(title="Onderwijsdata Chat")

persistence_db.init_db()

_login_limiter = RateLimiter(max_attempts=5, window_seconds=60)

_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "connect-src 'self' wss: ws:; "
        "font-src 'self'; "
        "frame-ancestors 'none';"
    )
    response.headers["Server"] = ""
    return response

# ─── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/version")
async def version() -> dict:
    import tomllib
    with open(Path(__file__).parent / "pyproject.toml", "rb") as f:
        return {"version": tomllib.load(f)["project"]["version"]}


# ─── Auth endpoints ────────────────────────────────────────────────────────────

@app.get("/api/auth/status")
async def auth_status() -> dict:
    return {"required": AUTH_ENABLED}


@app.post("/api/auth/login")
async def login(body: dict, request: Request) -> dict:
    client_ip = request.client.host if request.client else "unknown"
    if not _login_limiter.is_allowed(client_ip):
        retry = _login_limiter.retry_after(client_ip)
        raise HTTPException(
            status_code=429,
            detail=f"Te veel inlogpogingen. Probeer het over {retry} seconden opnieuw.",
            headers={"Retry-After": str(retry)},
        )
    username = body.get("username", "").strip()
    password = body.get("password", "")
    if AUTH_ENABLED and not check_credentials(username, password, USERS):
        raise HTTPException(status_code=401, detail="Ongeldige inloggegevens")
    token = make_token(username or "gast")
    return {"token": token, "user": username or "gast"}


# ─── Persistence ──────────────────────────────────────────────────────────────

@app.get("/api/conversations")
async def list_conversations(username: str = Depends(get_current_user)) -> list[dict]:
    return persistence_db.list_conversations(username)


@app.put("/api/conversations/{conv_id}")
async def upsert_conversation(conv_id: str, body: dict, username: str = Depends(get_current_user)) -> dict:
    persistence_db.upsert_conversation(
        username, conv_id, body["title"], body["timestamp"], body["messages"],
    )
    return {"ok": True}


@app.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: str, username: str = Depends(get_current_user)) -> dict:
    persistence_db.delete_conversation(username, conv_id)
    return {"ok": True}


@app.get("/api/workbooks")
async def list_workbooks(username: str = Depends(get_current_user)) -> list[dict]:
    return persistence_db.list_workbooks(username)


@app.put("/api/workbooks/{wb_id}")
async def upsert_workbook(wb_id: str, body: dict, username: str = Depends(get_current_user)) -> dict:
    persistence_db.upsert_workbook(
        username, wb_id, body.get("title", ""),
        body.get("description", ""),
        messages=body.get("messages"),
        figures=body.get("figures"),
        instelling=body.get("instelling"),
        html_content=body.get("htmlContent"),
        created_at=body.get("createdAt", ""),
    )
    return {"ok": True}


@app.delete("/api/workbooks/{wb_id}")
async def delete_workbook(wb_id: str, username: str = Depends(get_current_user)) -> dict:
    persistence_db.delete_workbook(username, wb_id)
    return {"ok": True}


# ─── Starters ─────────────────────────────────────────────────────────────────

_TAG_STARTERS: dict[str, tuple[str, ...]] = {
    "Verken Arbeidsmarkt": ("arbeidsmarkt",),
    "Verken Kansengelijkheid": ("kansengelijkheid", "herkomst", "diversiteit"),
    "Verken Regio": ("regio", "gemeente"),
    "Verken Voortijdig Schoolverlaten": ("vsv",),
}


def _tag_voorbeeldvragen(tags: tuple[str, ...], n: int = 4) -> list[str]:
    seen: set[str] = set()
    questions: list[str] = []
    for entry in list(_cbs_catalog()) + list(_rio_duo_catalog()):
        if any(t in entry.get("tags", []) for t in tags):
            for q in entry.get("voorbeeldvragen", []):
                if q not in seen:
                    seen.add(q)
                    questions.append(q)
        if len(questions) >= n * 4:
            break
    step = max(1, len(questions) // n)
    return [questions[i * step] for i in range(n) if i * step < len(questions)]


@app.get("/api/starters")
async def get_starters() -> list[dict]:
    return [
        {"label": "Arbeidsmarkt", "message": "Verken Arbeidsmarkt", "description": "Wat doen afgestudeerden? Aansluiting onderwijs-arbeidsmarkt"},
        {"label": "Kansengelijkheid", "message": "Verken Kansengelijkheid", "description": "Herkomst, diversiteit en gelijke kansen in het onderwijs"},
        {"label": "Regio", "message": "Verken Regio", "description": "Regionale verschillen in onderwijsdeelname en -resultaten"},
        {"label": "Voortijdig Schoolverlaten", "message": "Verken Voortijdig Schoolverlaten", "description": "VSV: wie verlaat school zonder startkwalificatie?"},
    ]


# ─── Settings ─────────────────────────────────────────────────────────────────

@app.get("/api/settings/config")
async def get_settings_config() -> dict:
    available = get_available_models()
    return {
        "models": [
            {"id": mid, "name": name, "description": desc, "icon": icon}
            for mid, name, desc, icon in (available or [])
        ],
        "default_model": MODEL,
    }


# ─── Instellingen & Dashboard ────────────────────────────────────────────────

@app.get("/api/instellingen")
async def get_instellingen(type: str | None = Query(default=None)) -> list[dict]:
    loop = asyncio.get_running_loop()
    alle = await loop.run_in_executor(None, get_all_instellingen)
    if type:
        types = {t.strip().lower() for t in type.split(",")}
        return [i for i in alle if i["type"] in types]
    return alle


@app.get("/api/dashboard/instroom")
async def dashboard_instroom(instelling: str = Query(...)) -> dict:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, load_dashboard_data, instelling)


# ─── Export ────────────────────────────────────────────────────────────────────

@app.post("/api/export/rapport")
async def export_rapport(body: dict) -> Response:
    turns = body.get("turns", [])
    html = generate_report(turns)
    return Response(
        content=html,
        media_type="text/html",
        headers={"Content-Disposition": f"attachment; filename=rapport-{date.today()}.html"},
    )


@app.post("/api/export/samenvatting")
async def export_samenvatting(body: dict) -> Response:
    turns = body.get("turns", [])
    if not turns:
        raise HTTPException(status_code=400, detail="Geen gesprek om samen te vatten.")

    model = body.get("model") or MODEL
    session_lines: list[str] = []
    for i, turn in enumerate(turns):
        q = turn.get("question", "")
        a = (turn.get("answer", "") or "")[:600]
        session_lines.append(f"[{i}] Vraag: {q}")
        session_lines.append(f"    Antwoord: {a}")

    prompt = (
        "Je bent een analist die een onderwijsdata-gesprekssessie destilleert tot een beknopt rapport.\n\n"
        "Geef je antwoord als JSON met deze structuur (geen markdown, alleen JSON):\n"
        '{"title": "...", "narrative": "...", "key_findings": ["...", "..."], "selected_turns": [0, 1]}\n\n'
        "Regels:\n"
        "- title: een concrete, beschrijvende rapporttitel\n"
        "- narrative: 2-4 alinea's die de rode draad samenvatten (markdown toegestaan)\n"
        "- key_findings: 3-5 concrete bevindingen als korte bullets\n"
        "- selected_turns: indices van de meest relevante vragen\n\n"
        f"Sessie:\n{chr(10).join(session_lines)}"
    )

    spec: dict = {}
    try:
        resp = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            **_litellm_kwargs(model),
        )
        raw = (resp.choices[0].message.content or "").strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        spec = json.loads(raw)
    except Exception:
        pass

    selected = spec.get("selected_turns") or list(range(len(turns)))
    selected = [i for i in selected if 0 <= i < len(turns)] or list(range(len(turns)))
    html = generate_dashboard(turns, spec, selected)
    return Response(
        content=html,
        media_type="text/html",
        headers={"Content-Disposition": f"attachment; filename=samenvatting-{date.today()}.html"},
    )


# ─── WebSocket chat ────────────────────────────────────────────────────────────

def _new_session() -> dict:
    return {
        "messages": [],
        "figures": [],
        "turns": [],
        "turn_figures": [],
        "chat_settings": {},
        "current_model": None,
        "stop_event": None,
        "_last_turn_tool_calls": [],
    }


async def _process_message(content: str, session: dict, emit, model: str | None) -> None:
    messages: list = session["messages"]
    messages.append({"role": "user", "content": content})

    stop_event = asyncio.Event()
    session["stop_event"] = stop_event
    session["turn_figures"] = []

    session["_clarified"] = False
    try:
        response_text = await agent_run(messages, session, emit, stop_event, model=model)
    except Exception as e:
        await emit({"type": "error", "message": friendly_error(e)})
        messages.pop()
        return

    clarified = session.pop("_clarified", False)
    aborted = stop_event.is_set()
    if not clarified and not aborted:
        messages.append({"role": "assistant", "content": response_text})
        turn_tool_calls = session.get("_last_turn_tool_calls", [])
        session["_last_turn_tool_calls"] = []
        turns: list = session.get("turns", [])
        turns.append({
            "question": content,
            "answer": response_text,
            "tool_calls": turn_tool_calls,
            "figures": session.get("turn_figures", []),
        })
        session["turns"] = turns
    session["messages"] = messages


@app.websocket("/api/chat")
async def chat_websocket(ws: WebSocket, token: str | None = Query(default=None)) -> None:
    # Auth guard — close with 4001 before sending any data
    if AUTH_ENABLED:
        username = verify_token(token or "")
        if not username:
            await ws.close(code=4001, reason="Niet geautoriseerd")
            return

    await ws.accept()
    session = _new_session()

    async def emit(event: dict) -> None:
        await ws.send_text(json.dumps(event))

    known_keys = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "AZURE_API_KEY", "AZURE_AI_API_KEY", "GEMINI_API_KEY", "WILLMA_API_KEY"]
    is_ollama = MODEL.startswith("ollama_chat/") or MODEL.startswith("ollama/")
    if not is_ollama and not any(os.getenv(k) for k in known_keys):
        await emit({"type": "system_message", "message": "Geen API key gevonden. Stel een omgevingsvariabele in (bijv. ANTHROPIC_API_KEY) en herstart de app."})

    current_task: asyncio.Task | None = None

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            action = msg.get("action")

            if action == "stop":
                stop_event = session.get("stop_event")
                if stop_event:
                    stop_event.set()

            elif action == "settings":
                session["chat_settings"] = msg.get("settings", {})

            elif action == "message":
                content = msg.get("content", "").strip()
                if not content:
                    continue
                if current_task and not current_task.done():
                    continue
                model = session["chat_settings"].get("model") or None
                session["current_model"] = model

                if content in _TAG_STARTERS:
                    tags = _TAG_STARTERS[content]
                    label = content.removeprefix("Verken ")
                    await emit({"type": "starter_questions", "label": label, "questions": _tag_voorbeeldvragen(tags)})
                    continue

                current_task = asyncio.create_task(_process_message(content, session, emit, model))

            elif action == "clarification_choice":
                if current_task and not current_task.done():
                    continue
                choice = msg.get("choice", "")
                model = session.get("current_model")
                current_task = asyncio.create_task(_process_message(choice, session, emit, model))

    except WebSocketDisconnect:
        if current_task and not current_task.done():
            current_task.cancel()
            stop_event = session.get("stop_event")
            if stop_event:
                stop_event.set()


# ─── Serve React frontend ──────────────────────────────────────────────────────

_FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"

if _FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str) -> Response:
        return Response(content=(_FRONTEND_DIST / "index.html").read_text(), media_type="text/html")
