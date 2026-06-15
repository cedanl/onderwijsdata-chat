from config import MAX_HISTORY


def trim(history: list[dict]) -> tuple[list[dict], bool]:
    if len(history) <= MAX_HISTORY:
        return history, False
    first_user = next((m for m in history if m["role"] == "user"), None)
    tail = history[-(MAX_HISTORY - 1):]
    if first_user and first_user not in tail:
        return [first_user] + tail, True
    return tail, True
