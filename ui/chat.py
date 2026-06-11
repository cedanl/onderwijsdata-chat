import asyncio
import io
import json
import os

import chainlit as cl
from chainlit.data import get_data_layer
from chainlit.types import ThreadDict

from agent import run
from agent.title import generate_title
from config import MODEL
from resume import build_messages_from_thread, build_turns_from_thread
from tools import store
from ui.errors import friendly_error
from ui.setup import setup_modes, setup_settings
from ui.starters import _TAG_STARTERS, tag_voorbeeldvragen
from ui.uploads import persist_uploads, read_file_content


async def _set_thread_title(question: str, answer: str, model: str | None = None) -> None:
    try:
        title = await generate_title(question, answer, model=model)
        cl.user_session.set("thread_title", title)
        layer = get_data_layer()
        if layer:
            await layer.update_thread(
                thread_id=cl.context.session.thread_id,
                name=title,
            )
        await cl.context.emitter.emit(
            "first_interaction",
            {"interaction": title, "thread_id": cl.context.session.thread_id},
        )
    except Exception:
        pass


async def process_message(content: str, modus: str = "snel", model: str | None = None) -> None:
    cl.user_session.set("current_model", model)
    messages: list = cl.user_session.get("messages")
    messages.append({"role": "user", "content": content})

    stop_event = asyncio.Event()
    cl.user_session.set("stop_event", stop_event)
    cl.user_session.set("turn_figures", [])

    try:
        response_text = await run(messages, stop_event, model=model, modus=modus)
    except Exception as e:
        await cl.Message(content=friendly_error(e)).send()
        return

    messages.append({"role": "assistant", "content": response_text})
    cl.user_session.set("messages", messages)

    turn_figures = cl.user_session.get("turn_figures", [])
    turn_tool_calls = cl.user_session.get("_last_turn_tool_calls", [])
    cl.user_session.set("_last_turn_tool_calls", [])
    turns: list = cl.user_session.get("turns", [])
    turns.append({"question": content, "answer": response_text, "figures": turn_figures, "tool_calls": turn_tool_calls})
    cl.user_session.set("turns", turns)

    if len(messages) == 2:
        asyncio.create_task(_set_thread_title(content, response_text, model=model))

    asyncio.create_task(persist_uploads())


@cl.on_chat_start
async def on_start():
    cl.user_session.set("messages", [])
    cl.user_session.set("figures", [])
    cl.user_session.set("turns", [])

    is_ollama = MODEL.startswith("ollama_chat/") or MODEL.startswith("ollama/")
    known_keys = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "AZURE_API_KEY", "AZURE_AI_API_KEY", "GEMINI_API_KEY", "WILLMA_API_KEY"]
    if not is_ollama and not any(os.getenv(k) for k in known_keys):
        await cl.Message(content="⚠️ Geen API key gevonden. Stel een omgevingsvariabele in (bijv. `ANTHROPIC_API_KEY`) en herstart de app.").send()
        return

    await setup_modes()
    await setup_settings()


@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict):
    import pandas as pd

    messages = build_messages_from_thread(thread)
    turns = build_turns_from_thread(thread)
    figures = [fig for turn in turns for fig in turn.get("figures", [])]
    cl.user_session.set("messages", messages)
    cl.user_session.set("turns", turns)
    cl.user_session.set("figures", figures)
    cl.user_session.set("turn_figures", [])

    raw_meta = thread.get("metadata") or {}
    if isinstance(raw_meta, str):
        try:
            raw_meta = json.loads(raw_meta)
        except Exception:
            raw_meta = {}
    for key, csv_str in (raw_meta.get("_uploads") or {}).items():
        try:
            df = pd.read_csv(io.StringIO(csv_str), dtype=str)
            store.put(key, df)
        except Exception:
            pass

    await setup_modes()
    await setup_settings()


@cl.on_stop
async def on_stop():
    stop_event: asyncio.Event | None = cl.user_session.get("stop_event")
    if stop_event:
        stop_event.set()


@cl.on_message
async def on_message(message: cl.Message):
    modus = message.modes.get("modus", "snel") if message.modes else "snel"
    model = message.modes.get("model") if message.modes else None

    if message.content in _TAG_STARTERS:
        tags = _TAG_STARTERS[message.content]
        label = message.content.removeprefix("Verken ")
        questions = tag_voorbeeldvragen(tags)
        actions = [
            cl.Action(name="explore_question", label=q, payload={"question": q, "modus": modus, "model": model or ""})
            for q in questions
        ]
        await cl.Message(
            content=f"Hier zijn voorbeeldvragen over **{label}**:",
            actions=actions,
        ).send()
        return

    content = message.content
    if message.elements:
        for el in message.elements:
            file_text = await read_file_content(el)
            if file_text:
                content += file_text

    await process_message(content, modus=modus, model=model)
