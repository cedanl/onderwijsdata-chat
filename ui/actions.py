import chainlit as cl

from ui.lifecycle import process_message


@cl.action_callback("followup")
async def on_followup(action: cl.Action):
    await cl.context.emitter.send_window_message({
        "type": "set_input",
        "value": action.payload["question"],
    })


@cl.action_callback("clarification_choice")
async def on_clarification_choice(action: cl.Action):
    choice = action.payload["choice"]
    modus = cl.user_session.get("modus", "verdiep")
    model = cl.user_session.get("current_model")
    source_options = cl.user_session.get("source_options", [])
    if source_options:
        cl.user_session.set("chosen_source", choice)
        cl.user_session.set("source_alternatives", [o for o in source_options if o.get("label") != choice])
    await cl.Message(content=choice, author="User").send()
    await process_message(choice, modus=modus, model=model)


@cl.action_callback("alternative_source")
async def on_alternative_source(action: cl.Action):
    label = action.payload["label"]
    modus = cl.user_session.get("modus", "verdiep")
    model = cl.user_session.get("current_model")
    source_options = cl.user_session.get("source_options", [])
    if source_options:
        cl.user_session.set("chosen_source", label)
        cl.user_session.set("source_alternatives", [o for o in source_options if o.get("label") != label])
    msg = f"Herhaal de vorige analyse met {label} als databron."
    await cl.Message(content=msg, author="User").send()
    await process_message(msg, modus=modus, model=model)


@cl.action_callback("explore_question")
async def on_explore_question(action: cl.Action):
    question = action.payload["question"]
    modus = action.payload.get("modus", "snel")
    model = action.payload.get("model") or None
    await cl.Message(content=question, author="User").send()
    await process_message(question, modus=modus, model=model)
