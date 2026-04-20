import os
import tempfile
from datetime import date

from dotenv import load_dotenv

load_dotenv()

import chainlit as cl

from agent import run
from report import generate_report

WELKOM = """Welkom! Ik kan je helpen met vragen over open Nederlandse onderwijsdata.

Ik heb toegang tot:
- **CBS** — statistieken over het Nederlandse onderwijs (68 datasets)
- **RIO** — register van onderwijsinstellingen en opleidingen (14 resources)

Stel een vraag, bijvoorbeeld:
- *Hoeveel MBO studenten waren er in 2023?*
- *Welke HBO-instellingen zijn er in Amsterdam?*
- *Wat is het verschil in uitstroom tussen mannen en vrouwen in het WO?*
"""


@cl.on_chat_start
async def on_start():
    cl.user_session.set("messages", [])
    cl.user_session.set("figures", [])
    await cl.Message(content=WELKOM).send()
    known_keys = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "AZURE_API_KEY", "AZURE_AI_API_KEY", "GEMINI_API_KEY"]
    if not any(os.getenv(k) for k in known_keys):
        await cl.Message(content="⚠️ Geen API key gevonden. Stel een omgevingsvariabele in (bijv. `ANTHROPIC_API_KEY`) en herstart de app.").send()


@cl.on_message
async def on_message(message: cl.Message):
    messages: list = cl.user_session.get("messages")
    messages.append({"role": "user", "content": message.content})

    try:
        response_text = await run(messages)
    except Exception as e:
        await cl.Message(content=f"Fout: {e}").send()
        return

    messages.append({"role": "assistant", "content": response_text})
    cl.user_session.set("messages", messages)

    figures = cl.user_session.get("figures", [])
    actions = [cl.Action(name="download_rapport", label="📥 Download rapport", payload={"action": "download"})] if figures else []

    if response_text:
        await cl.Message(content=response_text, actions=actions).send()
    elif actions:
        await cl.Message(content="", actions=actions).send()


@cl.action_callback("download_rapport")
async def on_download_rapport(action: cl.Action):
    messages = cl.user_session.get("messages", [])
    figures = cl.user_session.get("figures", [])
    html = generate_report(messages, figures)

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as f:
        f.write(html)
        path = f.name

    await cl.Message(
        content="Rapport klaar!",
        elements=[cl.File(name=f"rapport-{date.today()}.html", path=path)],
    ).send()
