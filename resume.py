import base64
from collections.abc import Mapping

import plotly.io as pio

_MESSAGE_TYPES = {"user_message": "user", "assistant_message": "assistant"}


def build_messages_from_thread(thread: Mapping) -> list[dict]:
    """Reconstruct the LLM message list from a persisted Chainlit thread."""
    messages = []
    for step in thread.get("steps", []):
        role = _MESSAGE_TYPES.get(step.get("type", ""))
        output = step.get("output") or ""
        if role and output:
            messages.append({"role": role, "content": output})
    return messages


def build_turns_from_thread(thread: Mapping) -> list[dict]:
    """Reconstruct turns (question/answer/figures) from a persisted Chainlit thread."""
    steps = thread.get("steps", [])
    elements = thread.get("elements") or []

    figures_by_step: dict[str, list] = {}
    for elem in elements:
        if elem.get("type") != "plotly":
            continue
        for_id = elem.get("forId") or elem.get("for_id")
        if not for_id:
            continue
        url = elem.get("url", "")
        if not url.startswith("data:application/json;base64,"):
            continue
        try:
            b64 = url.split(",", 1)[1]
            fig = pio.from_json(base64.b64decode(b64).decode())
            figures_by_step.setdefault(for_id, []).append(fig)
        except Exception:
            pass

    turns = []
    current_question: str | None = None
    current_answer: str | None = None
    current_figures: list = []

    for step in steps:
        step_type = step.get("type", "")
        step_id = step.get("id", "")

        if step_type == "user_message":
            if current_question is not None and current_answer is not None:
                turns.append({"question": current_question, "answer": current_answer, "figures": current_figures})
            current_question = step.get("output") or step.get("input") or ""
            current_answer = None
            current_figures = []

        elif step_type == "assistant_message":
            output = step.get("output") or ""
            if output:
                current_answer = output
            current_figures.extend(figures_by_step.get(step_id, []))

    if current_question is not None and current_answer is not None:
        turns.append({"question": current_question, "answer": current_answer, "figures": current_figures})

    return turns
