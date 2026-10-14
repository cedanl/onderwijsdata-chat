from core.config import MAX_HISTORY


def trim(history: list[dict]) -> tuple[list[dict], bool]:
    if len(history) <= MAX_HISTORY:
        return history, False
    first_user = next((m for m in history if m["role"] == "user"), None)
    tail = history[-(MAX_HISTORY - 1) :]
    # Drop leading tool/assistant-with-tool_calls messages that lost their
    # paired counterpart at the cut point — they confuse the LLM.
    while tail and tail[0]["role"] == "tool":
        tail = tail[1:]
    while tail and tail[0]["role"] == "assistant" and tail[0].get("tool_calls"):
        tail = tail[1:]
        while tail and tail[0]["role"] == "tool":
            tail = tail[1:]
    if first_user and first_user not in tail:
        return [first_user, *tail], True
    return tail, True


# Een lege assistenttekst wordt bij LiteLLM "[System: Empty message content sanitised…]", die het
# model daarna herhaalt (#322).
TUSSENSTAP = "Tussenstap: data opgehaald."


def afgeronde_stappen(beurt: list[dict]) -> list[dict]:
    """De toolstappen van een onderbroken beurt die af zijn: elke aanroep met al zijn resultaten (#431).

    Een nieuwe poging bouwt daarop voort in plaats van alles opnieuw op te halen. Een
    aanroep zonder (alle) resultaten gaat niet mee, net als een correctieronde of
    afrondvraag: die hoorden bij de onderbroken beurt.
    """
    stappen: list[dict] = []
    i = 0
    while i < len(beurt):
        m = beurt[i]
        j = i + 1
        if m["role"] == "assistant" and m.get("tool_calls"):
            while j < len(beurt) and beurt[j]["role"] == "tool":
                j += 1
            resultaten = beurt[i + 1 : j]
            if {r["tool_call_id"] for r in resultaten} == {tc["id"] for tc in m["tool_calls"]}:
                stappen += [{**m, "content": m.get("content") or TUSSENSTAP}, *resultaten]
        i = j
    return stappen
