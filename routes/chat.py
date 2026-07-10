import asyncio
import json
import logging
import os

from fastapi import APIRouter, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from agent import run as agent_run
from agent.dashboard import generate as generate_dashboard_spec
from agent.dashboard import DashboardSpec
from agent.replay import replay_data_calls, replay_dashboard_figures
from core.auth import AUTH_ENABLED, verify_token
from core.config import MODEL
from core.errors import friendly_error
from .instellingen import TAG_STARTERS, tag_voorbeeldvragen

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


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


async def _generate_dashboard(session: dict, emit, model: str | None) -> None:
    await emit({"type": "dashboard_generating"})
    try:
        spec = await generate_dashboard_spec(session, emit, model=model)
        await emit({"type": "dashboard_ready", "spec": spec.to_dict()})
    except ValueError as e:
        await emit({"type": "error", "message": str(e)})
    except Exception as e:
        await emit({"type": "error", "message": friendly_error(e)})


class RefreshError(Exception):
    pass


async def _do_refresh(recipe: list[dict], figure_recipes: list[dict], current_spec: dict) -> tuple[DashboardSpec, str | None]:
    """Shared refresh logic. Returns (updated_spec, info_message_or_None).

    Raises RefreshError if refresh fails entirely.
    """
    if not figure_recipes and not recipe:
        raise RefreshError("Dit dashboard kan niet ververst worden.")

    spec = DashboardSpec.from_dict(current_spec)
    info: str | None = None

    if figure_recipes:
        fresh_figures = await asyncio.to_thread(replay_dashboard_figures, recipe, figure_recipes)
        if fresh_figures:
            spec.figures_json = fresh_figures
        else:
            info = "Grafieken konden niet bijgewerkt worden, bestaande data behouden."
    elif recipe:
        results = await asyncio.to_thread(replay_data_calls, recipe)
        if all(not r["success"] for r in results):
            errors = "; ".join(r.get("error", "?") for r in results)
            raise RefreshError(f"Geen van de datasets kon herladen worden: {errors}")
        info = "Data herladen. Grafieken bijwerken is niet mogelijk bij oudere dashboards."

    return spec, info


async def _refresh_dashboard(recipe: list[dict], figure_recipes: list[dict], current_spec: dict, session: dict, emit, model: str | None) -> None:
    await emit({"type": "dashboard_generating"})
    try:
        spec, info = await _do_refresh(recipe, figure_recipes, current_spec)
        if info:
            level = "warning" if "niet" in info else "info"
            await emit({"type": "toast", "message": info, "level": level})
        await emit({"type": "dashboard_ready", "spec": spec.to_dict()})
    except RefreshError as e:
        await emit({"type": "error", "message": str(e)})
    except Exception as e:
        await emit({"type": "error", "message": friendly_error(e)})


@router.post("/api/dashboard/refresh")
async def refresh_dashboard_endpoint(request: Request):
    if AUTH_ENABLED:
        auth = request.headers.get("authorization", "")
        token = auth.removeprefix("Bearer ").strip()
        if not verify_token(token):
            return JSONResponse({"error": "Niet geautoriseerd"}, status_code=401)

    body = await request.json()
    recipe = body.get("recipe") or []
    figure_recipes = body.get("figure_recipes") or []
    current_spec = body.get("spec") or {}

    try:
        spec, _ = await _do_refresh(recipe, figure_recipes, current_spec)
        return {"spec": spec.to_dict()}
    except RefreshError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error("Dashboard refresh failed", exc_info=True)
        return JSONResponse({"error": friendly_error(e)}, status_code=500)


@router.websocket("/api/chat")
async def chat_websocket(ws: WebSocket, token: str | None = Query(default=None)) -> None:
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

                if content in TAG_STARTERS:
                    tags = TAG_STARTERS[content]
                    label = content.removeprefix("Verken ")
                    await emit({"type": "starter_questions", "label": label, "questions": tag_voorbeeldvragen(tags)})
                    continue

                current_task = asyncio.create_task(_process_message(content, session, emit, model))

            elif action == "clarification_choice":
                if current_task and not current_task.done():
                    continue
                choice = msg.get("choice", "")
                model = session.get("current_model")
                current_task = asyncio.create_task(_process_message(choice, session, emit, model))

            elif action == "generate_dashboard":
                if current_task and not current_task.done():
                    continue
                model = session["chat_settings"].get("model") or None
                current_task = asyncio.create_task(
                    _generate_dashboard(session, emit, model)
                )

            elif action == "refresh_dashboard":
                if current_task and not current_task.done():
                    continue
                recipe = msg.get("recipe") or []
                figure_recipes = msg.get("figure_recipes") or []
                current_spec = msg.get("spec") or {}
                model = session["chat_settings"].get("model") or None
                current_task = asyncio.create_task(
                    _refresh_dashboard(recipe, figure_recipes, current_spec, session, emit, model)
                )

    except WebSocketDisconnect:
        if current_task and not current_task.done():
            current_task.cancel()
            stop_event = session.get("stop_event")
            if stop_event:
                stop_event.set()
