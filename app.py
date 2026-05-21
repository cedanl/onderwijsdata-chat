import asyncio
import os
import tempfile
from datetime import date

from dotenv import load_dotenv

load_dotenv()

import litellm
import chainlit as cl

import auth
import data_layer
from agent import generate_title, run
from chainlit.data import get_data_layer
from config import MODEL
from report import generate_pdf, generate_report
from resume import build_messages_from_thread, build_turns_from_thread

auth.setup()
data_layer.setup()

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

_FRIENDLY_ERRORS: list[tuple[type, str]] = [
    (litellm.AuthenticationError, "API key ontbreekt of is ongeldig. Controleer je `.env` bestand."),
    (litellm.NotFoundError, "Model niet gevonden. Controleer de `MODEL` instelling in `.env`."),
    (litellm.RateLimitError, "Te veel verzoeken naar de API. Wacht even en probeer opnieuw."),
    (litellm.APIConnectionError, "Kan de API niet bereiken. Controleer je internetverbinding."),
    (litellm.BadRequestError, "Het verzoek werd afgewezen door de API. Mogelijk een ongeldig model of parameter."),
]


def _friendly_error(exc: Exception) -> str:
    for exc_type, msg in _FRIENDLY_ERRORS:
        if isinstance(exc, exc_type):
            return f"❌ {msg}"
    return f"❌ Er is een fout opgetreden: {exc}"


async def _set_thread_title(question: str, answer: str) -> None:
    try:
        title = await generate_title(question, answer)
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


@cl.set_starters
async def set_starters():
    return [
        cl.Starter(label="MBO studenten 2023", message="Hoeveel MBO studenten waren er in 2023?"),
        cl.Starter(label="HBO-instellingen Amsterdam", message="Welke HBO-instellingen zijn er in Amsterdam?"),
        cl.Starter(label="WO uitstroom man/vrouw", message="Wat is het verschil in uitstroom tussen mannen en vrouwen in het WO?"),
        cl.Starter(label="VMBO instroom trend", message="Toon de trend in VMBO instroom over de afgelopen 10 jaar."),
    ]


@cl.on_chat_resume
async def on_chat_resume(thread: dict):
    messages = build_messages_from_thread(thread)
    turns = build_turns_from_thread(thread)
    figures = [fig for turn in turns for fig in turn.get("figures", [])]
    cl.user_session.set("messages", messages)
    cl.user_session.set("turns", turns)
    cl.user_session.set("figures", figures)
    cl.user_session.set("turn_figures", [])


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

    await cl.Message(content=WELKOM).send()


@cl.on_stop
async def on_stop():
    stop_event: asyncio.Event | None = cl.user_session.get("stop_event")
    if stop_event:
        stop_event.set()


@cl.on_message
async def on_message(message: cl.Message):
    messages: list = cl.user_session.get("messages")
    messages.append({"role": "user", "content": message.content})

    stop_event = asyncio.Event()
    cl.user_session.set("stop_event", stop_event)
    cl.user_session.set("turn_figures", [])

    try:
        response_text = await run(messages, stop_event)
    except Exception as e:
        await cl.Message(content=_friendly_error(e)).send()
        return

    messages.append({"role": "assistant", "content": response_text})
    cl.user_session.set("messages", messages)

    turn_figures = cl.user_session.get("turn_figures", [])
    turns: list = cl.user_session.get("turns", [])
    turns.append({"question": message.content, "answer": response_text, "figures": turn_figures})
    cl.user_session.set("turns", turns)

    if len(messages) == 2:
        asyncio.create_task(_set_thread_title(message.content, response_text))


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


@cl.action_callback("download_rapport_pdf")
async def on_download_rapport_pdf(action: cl.Action):
    turns = cl.user_session.get("turns", [])
    pdf_bytes = await asyncio.to_thread(generate_pdf, turns)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(pdf_bytes)
        path = f.name

    await cl.Message(
        content="PDF rapport klaar!",
        elements=[cl.File(name=f"rapport-{date.today()}.pdf", path=path, mime="application/pdf")],
    ).send()
