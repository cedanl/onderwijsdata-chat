import os
import tempfile
from datetime import date

from dotenv import load_dotenv

load_dotenv()

import chainlit as cl

import persistence
from agent import run
from data_layer import SQLiteDataLayer, init_db
from report import generate_report

init_db()


@cl.data_layer
def get_data_layer() -> SQLiteDataLayer:
    return SQLiteDataLayer()


@cl.header_auth_callback
def auth_callback(headers) -> cl.User:
    return cl.User(identifier="local", metadata={"role": "user"})


@cl.on_chat_resume
async def on_resume(thread: cl.types.ThreadDict) -> None:
    metadata = thread.get("metadata") or {}
    messages = metadata.get("messages", [])
    cl.user_session.set("messages", messages)
    cl.user_session.set("figures", [])
    cl.user_session.set("turns", [])
    cl.user_session.set("session_id", thread["id"])
    cl.user_session.set("turn_figures", [])

WELKOM = """Welkom! Ik kan je helpen met vragen over open Nederlandse onderwijsdata.

Ik heb toegang tot:
- **CBS** — statistieken over het Nederlandse onderwijs (68 datasets)
- **RIO** — register van onderwijsinstellingen en opleidingen (14 resources)
- **DUO** — 57 open datasets: prognoses, diplomering, instroom, adressen (onderwijsdata.duo.nl)

Stel een vraag, bijvoorbeeld:
- *Hoeveel MBO studenten waren er in 2023?*
- *Welke HBO-instellingen zijn er in Amsterdam?*
- *Wat is het verschil in uitstroom tussen mannen en vrouwen in het WO?*
- *Hoe ontwikkelt het MBO-studentenaantal zich richting 2040 per leerweg?*
"""


@cl.set_starters
async def set_starters():
    return [
        cl.Starter(label="MBO studenten 2023", message="Hoeveel MBO studenten waren er in 2023?"),
        cl.Starter(label="HBO-instellingen Amsterdam", message="Welke HBO-instellingen zijn er in Amsterdam?"),
        cl.Starter(label="WO uitstroom man/vrouw", message="Wat is het verschil in uitstroom tussen mannen en vrouwen in het WO?"),
        cl.Starter(label="VMBO instroom trend", message="Toon de trend in VMBO instroom over de afgelopen 10 jaar."),
    ]


@cl.on_chat_start
async def on_start():
    cl.user_session.set("session_id", cl.context.session.id)
    cl.user_session.set("messages", [])
    cl.user_session.set("figures", [])
    cl.user_session.set("turns", [])

    known_keys = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "AZURE_API_KEY", "AZURE_AI_API_KEY", "GEMINI_API_KEY"]
    if not any(os.getenv(k) for k in known_keys):
        await cl.Message(content="⚠️ Geen API key gevonden. Stel een omgevingsvariabele in (bijv. `ANTHROPIC_API_KEY`) en herstart de app.").send()
        return

    await cl.Message(content=WELKOM + "\n\nTip: typ `/history` om eerdere gesprekken te hervatten.").send()


@cl.action_callback("resume_session")
async def on_resume_session(action: cl.Action):
    session_id = action.payload["session_id"]
    messages = persistence.load(session_id)
    if not messages:
        await cl.Message(content="Gesprek niet meer beschikbaar.").send()
        return

    cl.user_session.set("messages", messages)
    cl.user_session.set("session_id", session_id)

    user_turns = [(m["content"], messages[i + 1]["content"] if i + 1 < len(messages) else "")
                  for i, m in enumerate(messages) if m["role"] == "user"]

    summary_lines = "\n".join(
        f"- **V:** {q[:80]}{'…' if len(q) > 80 else ''}\n  **A:** {a[:120]}{'…' if len(a) > 120 else ''}"
        for q, a in user_turns[-5:]
    )
    await cl.Message(
        content=f"Gesprek herladen ({len(user_turns)} vragen). Laatste uitwisselingen:\n\n{summary_lines}\n\nGa gerust verder."
    ).send()


async def _show_history() -> None:
    sessions = persistence.recent()
    if not sessions:
        await cl.Message(content="Nog geen opgeslagen gesprekken.").send()
        return
    actions = [
        cl.Action(
            name="resume_session",
            label=f"↩ {s['title'][:55]}{'…' if len(s['title']) > 55 else ''}",
            payload={"session_id": s["id"]},
        )
        for s in sessions
    ]
    await cl.Message(content="**Vorige gesprekken:**", actions=actions).send()


@cl.on_message
async def on_message(message: cl.Message):
    if message.content.strip().lower() in ("/history", "/gesprekken"):
        await _show_history()
        return

    messages: list = cl.user_session.get("messages")
    messages.append({"role": "user", "content": message.content})

    cl.user_session.set("turn_figures", [])

    try:
        response_text = await run(messages)
    except Exception as e:
        await cl.Message(content=f"Fout: {e}").send()
        return

    messages.append({"role": "assistant", "content": response_text})
    cl.user_session.set("messages", messages)

    turn_figures = cl.user_session.get("turn_figures", [])
    turns: list = cl.user_session.get("turns", [])
    turns.append({"question": message.content, "answer": response_text, "figures": turn_figures})
    cl.user_session.set("turns", turns)

    # Persist LLM messages in thread metadata so on_chat_resume can restore them
    thread_id = cl.context.session.thread_id
    from chainlit.data import get_data_layer
    dl = get_data_layer()
    if dl:
        await dl.update_thread(thread_id, metadata={"messages": messages})


@cl.action_callback("download_rapport")
async def on_download_rapport(action: cl.Action):
    turns = cl.user_session.get("turns", [])
    html = generate_report(turns)

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as f:
        f.write(html)
        path = f.name

    await cl.Message(
        content="Rapport klaar!",
        elements=[cl.File(name=f"rapport-{date.today()}.html", path=path, mime="text/html")],
    ).send()
