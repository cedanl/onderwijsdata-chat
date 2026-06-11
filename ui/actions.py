import chainlit as cl

from ui.chat import process_message


@cl.action_callback("followup")
async def on_followup(action: cl.Action):
    await cl.context.emitter.send_window_message({
        "type": "set_input",
        "value": action.payload["question"],
    })


@cl.action_callback("clarification_choice")
async def on_clarification_choice(action: cl.Action):
    choice = action.payload["choice"]
    await cl.Message(content=choice, author="User").send()
    await process_message(choice, modus="verdiep")


@cl.action_callback("explore_question")
async def on_explore_question(action: cl.Action):
    question = action.payload["question"]
    modus = action.payload.get("modus", "snel")
    model = action.payload.get("model") or None
    await cl.Message(content=question, author="User").send()
    await process_message(question, modus=modus, model=model)
