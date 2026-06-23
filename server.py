import asyncio
import json
import os
import re
from datetime import date
from pathlib import Path

import litellm
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

load_dotenv()

from agent import run as agent_run
from agent.models import litellm_kwargs as _litellm_kwargs
from auth import AUTH_ENABLED, USERS, check_credentials
from config import MODEL, get_available_models
from export import generate_dashboard, generate_report
from tools.catalog import _cbs as _cbs_catalog, _rio_duo as _rio_duo_catalog
from ui.errors import friendly_error

app = FastAPI(title="Onderwijsdata Chat")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Auth ─────────────────────────────────────────────────────────────────────

@app.post("/api/auth/login")
async def login(body: dict) -> dict:
    username = body.get("username", "")
    password = body.get("password", "")
    if AUTH_ENABLED and not check_credentials(username, password, USERS):
        raise HTTPException(status_code=401, detail="Ongeldige inloggegevens")
    return {"ok": True, "user": username or "gast"}


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


# ─── Settings config ───────────────────────────────────────────────────────────

@app.get("/api/settings/config")
async def get_settings_config() -> dict:
    available = get_available_models()
    return {
        "roles": ["Geen voorkeur", "Beleidsmedewerker", "Onderzoeker / Analist", "Schoolbestuur / Directeur", "Journalist"],
        "domains": ["Geen voorkeur", "PO", "VO", "MBO", "HBO / WO"],
        "models": [
            {"id": mid, "name": name, "description": desc, "icon": icon}
            for mid, name, desc, icon in (available or [])
        ],
        "default_model": MODEL,
    }


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
        "source_alternatives": [],
        "source_options": [],
        "chosen_source": "",
        "pending_clarification": None,
    }


async def _process_message(content: str, session: dict, emit, model: str | None) -> None:
    messages: list = session["messages"]
    messages.append({"role": "user", "content": content})

    stop_event = asyncio.Event()
    session["stop_event"] = stop_event
    session["turn_figures"] = []

    try:
        response_text = await agent_run(messages, session, emit, stop_event, model=model)
    except Exception as e:
        await emit({"type": "error", "message": friendly_error(e)})
        messages.pop()
        return

    messages.append({"role": "assistant", "content": response_text})
    session["messages"] = messages

    turn_figures = session.get("turn_figures", [])
    turn_tool_calls = session.get("_last_turn_tool_calls", [])
    session["_last_turn_tool_calls"] = []
    turns: list = session.get("turns", [])
    turns.append({
        "question": content,
        "answer": response_text,
        "tool_calls": turn_tool_calls,
    })
    session["turns"] = turns


@app.websocket("/api/chat")
async def chat_websocket(ws: WebSocket) -> None:
    await ws.accept()
    session = _new_session()

    # Send initial config
    known_keys = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "AZURE_API_KEY", "AZURE_AI_API_KEY", "GEMINI_API_KEY", "WILLMA_API_KEY"]
    is_ollama = MODEL.startswith("ollama_chat/") or MODEL.startswith("ollama/")
    if not is_ollama and not any(os.getenv(k) for k in known_keys):
        await ws.send_text(json.dumps({
            "type": "system_message",
            "message": "Geen API key gevonden. Stel een omgevingsvariabele in (bijv. ANTHROPIC_API_KEY) en herstart de app.",
        }))

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

                model = session["chat_settings"].get("model") or None
                session["current_model"] = model

                if content in _TAG_STARTERS:
                    tags = _TAG_STARTERS[content]
                    label = content.removeprefix("Verken ")
                    questions = _tag_voorbeeldvragen(tags)
                    await ws.send_text(json.dumps({
                        "type": "starter_questions",
                        "label": label,
                        "questions": questions,
                    }))
                    continue

                async def emit(event: dict) -> None:
                    await ws.send_text(json.dumps(event))

                await _process_message(content, session, emit, model)

            elif action == "clarification_choice":
                choice = msg.get("choice", "")
                model = session.get("current_model")
                source_options = session.get("source_options", [])
                if source_options:
                    session["chosen_source"] = choice
                    session["source_alternatives"] = [o for o in source_options if o.get("label") != choice]

                async def emit(event: dict) -> None:
                    await ws.send_text(json.dumps(event))

                await _process_message(choice, session, emit, model)

            elif action == "alternative_source":
                label = msg.get("label", "")
                model = session.get("current_model")
                source_options = session.get("source_options", [])
                if source_options:
                    session["chosen_source"] = label
                    session["source_alternatives"] = [o for o in source_options if o.get("label") != label]
                content = f"Herhaal de vorige analyse met {label} als databron."

                async def emit(event: dict) -> None:
                    await ws.send_text(json.dumps(event))

                await _process_message(content, session, emit, model)

    except WebSocketDisconnect:
        pass


# ─── Serve React frontend ──────────────────────────────────────────────────────

_FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"

if _FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        index = _FRONTEND_DIST / "index.html"
        return Response(content=index.read_text(), media_type="text/html")
