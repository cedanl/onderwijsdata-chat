import asyncio
import json
import os
import re
from datetime import date
from pathlib import Path

import litellm
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from riodata import duo

load_dotenv()

from agent import run as agent_run
from agent.models import litellm_kwargs as _litellm_kwargs
from auth import AUTH_ENABLED, USERS, check_credentials, make_token, verify_token
from config import MODEL, get_available_models
from errors import friendly_error
from export import generate_dashboard, generate_report
from tools.catalog import _cbs as _cbs_catalog, _rio_duo as _rio_duo_catalog

app = FastAPI(title="Onderwijsdata Chat")

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

# ─── Auth endpoints ────────────────────────────────────────────────────────────

@app.get("/api/auth/status")
async def auth_status() -> dict:
    return {"required": AUTH_ENABLED}


@app.post("/api/auth/login")
async def login(body: dict) -> dict:
    username = body.get("username", "").strip()
    password = body.get("password", "")
    if AUTH_ENABLED and not check_credentials(username, password, USERS):
        raise HTTPException(status_code=401, detail="Ongeldige inloggegevens")
    token = make_token(username or "gast")
    return {"token": token, "user": username or "gast"}


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


# ─── Dashboard data endpoint ──────────────────────────────────────────────────

def _load_dashboard_data(instelling: str) -> dict:
    def _filter(df: pd.DataFrame) -> pd.DataFrame:
        col = "INSTELLINGSNAAM_ACTUEEL"
        if col not in df.columns:
            return df.iloc[0:0]
        return df[df[col].str.lower() == instelling.lower()]

    result: dict = {"instelling": instelling, "gevonden": False}

    try:
        df_inges = duo.load("p01hoinges", 0)
        hu = _filter(df_inges)
        if hu.empty:
            instellingen = sorted(df_inges["INSTELLINGSNAAM_ACTUEEL"].dropna().unique().tolist())
            result["beschikbare_instellingen"] = instellingen[:20]
            return result
        result["gevonden"] = True

        # ingeschrevenen per jaar
        result["ingeschrevenen"] = (
            hu.groupby("STUDIEJAAR")["AANTAL_INGESCHREVENEN"].sum()
            .sort_index().to_dict()
        )

        # geslacht laatste jaar
        laatste_jaar = hu["STUDIEJAAR"].max()
        geslacht = (
            hu[hu["STUDIEJAAR"] == laatste_jaar]
            .groupby("GESLACHT")["AANTAL_INGESCHREVENEN"].sum().to_dict()
        )
        result["geslacht"] = geslacht
        result["laatste_jaar"] = int(laatste_jaar)

        # sector verdeling laatste jaar
        result["sectoren"] = (
            hu[hu["STUDIEJAAR"] == laatste_jaar]
            .groupby("ONDERDEEL")["AANTAL_INGESCHREVENEN"].sum()
            .sort_values(ascending=False).to_dict()
        )
    except Exception as e:
        result["fout_ingeschrevenen"] = str(e)

    try:
        df_1e = duo.load("p02ho1ejrs", 0)
        hu1 = _filter(df_1e)
        if not hu1.empty:
            result["eerstejaars"] = (
                hu1.groupby("STUDIEJAAR")["AANTAL_EERSTEJAARS_INGESCHREVENEN"].sum()
                .sort_index().to_dict()
            )
    except Exception as e:
        result["fout_eerstejaars"] = str(e)

    try:
        df_dipl = duo.load("p04hogdipl", 0)
        hud = _filter(df_dipl)
        if not hud.empty:
            result["gediplomeerden"] = (
                hud.groupby("DIPLOMAJAAR")["AANTAL_GEDIPLOMEERDEN"].sum()
                .sort_index().to_dict()
            )
    except Exception as e:
        result["fout_gediplomeerden"] = str(e)

    return result


@app.get("/api/dashboard/instroom")
async def dashboard_instroom(instelling: str = Query(...)) -> dict:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _load_dashboard_data, instelling)


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
