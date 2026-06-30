from config import MAX_HISTORY


def trim(history: list[dict]) -> tuple[list[dict], bool]:
    if len(history) <= MAX_HISTORY:
        return history, False
    first_user = next((m for m in history if m["role"] == "user"), None)
    tail = history[-(MAX_HISTORY - 1):]
    # Drop leading tool/assistant-with-tool_calls messages that lost their
    # paired counterpart at the cut point — they confuse the LLM.
    while tail and tail[0]["role"] == "tool":
        tail = tail[1:]
    while tail and tail[0]["role"] == "assistant" and tail[0].get("tool_calls"):
        tail = tail[1:]
        while tail and tail[0]["role"] == "tool":
            tail = tail[1:]
    if first_user and first_user not in tail:
        return [first_user] + tail, True
    return tail, True
