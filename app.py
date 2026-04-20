from dotenv import load_dotenv

load_dotenv()

import chainlit as cl

from agent import run

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
    await cl.Message(content=WELKOM).send()


@cl.on_message
async def on_message(message: cl.Message):
    messages: list = cl.user_session.get("messages")
    messages.append({"role": "user", "content": message.content})

    response_text = await run(messages)

    messages.append({"role": "assistant", "content": response_text})
    cl.user_session.set("messages", messages)

    await cl.Message(content=response_text).send()
