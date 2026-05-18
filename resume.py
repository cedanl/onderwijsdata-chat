_MESSAGE_TYPES = {"user_message": "user", "assistant_message": "assistant"}


def build_messages_from_thread(thread: dict) -> list[dict]:
    """Reconstruct the LLM message list from a persisted Chainlit thread."""
    messages = []
    for step in thread.get("steps", []):
        role = _MESSAGE_TYPES.get(step.get("type", ""))
        output = step.get("output") or ""
        if role and output:
            messages.append({"role": role, "content": output})
    return messages
