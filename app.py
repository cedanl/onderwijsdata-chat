import os
import tempfile
from datetime import date

from dotenv import load_dotenv

load_dotenv()

import chainlit as cl

from agent import run
from config import MODEL
from report import generate_report

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
    cl.user_session.set("messages", [])
    cl.user_session.set("figures", [])
    cl.user_session.set("turns", [])

    is_ollama = MODEL.startswith("ollama_chat/") or MODEL.startswith("ollama/")
    known_keys = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "AZURE_API_KEY", "AZURE_AI_API_KEY", "GEMINI_API_KEY", "WILLMA_API_KEY"]
    if not is_ollama and not any(os.getenv(k) for k in known_keys):
        await cl.Message(content="⚠️ Geen API key gevonden. Stel een omgevingsvariabele in (bijv. `ANTHROPIC_API_KEY`) en herstart de app.").send()
        return

    await cl.Message(content=WELKOM).send()


@cl.on_message
async def on_message(message: cl.Message):
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
