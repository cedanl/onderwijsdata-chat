import chainlit as cl

from ui.lifecycle import process_message


@cl.action_callback("clarification_choice")
async def on_clarification_choice(action: cl.Action):
    choice = action.payload["choice"]
    model = cl.user_session.get("current_model")
    source_options = cl.user_session.get("source_options", [])
    if source_options:
        cl.user_session.set("chosen_source", choice)
        cl.user_session.set("source_alternatives", [o for o in source_options if o.get("label") != choice])
    await cl.Message(content=choice, author="User").send()
    await process_message(choice, model=model)


@cl.action_callback("alternative_source")
async def on_alternative_source(action: cl.Action):
    label = action.payload["label"]
    model = cl.user_session.get("current_model")
    source_options = cl.user_session.get("source_options", [])
    if source_options:
        cl.user_session.set("chosen_source", label)
        cl.user_session.set("source_alternatives", [o for o in source_options if o.get("label") != label])
    msg = f"Herhaal de vorige analyse met {label} als databron."
    await cl.Message(content=msg, author="User").send()
    await process_message(msg, model=model)


@cl.action_callback("explore_question")
async def on_explore_question(action: cl.Action):
    question = action.payload["question"]
    model = cl.user_session.get("current_model")
    await cl.Message(content=question, author="User").send()
    await process_message(question, model=model)
