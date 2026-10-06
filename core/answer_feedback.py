"""De trace achter een antwoord, voor feedback per antwoord (#248).

Een 👎 is pas bruikbaar als duidelijk is welke vraag, welk antwoord en welke
stappen erbij hoorden. Die trace komt uit het opgeslagen gesprek, niet uit het
feedbackverzoek: zo hoort de melding altijd bij een antwoord dat er echt stond.
"""

import json


def _stap(tool: dict) -> dict:
    return {
        "name": tool.get("name"),
        "label": tool.get("label"),
        "status": tool.get("status"),
        "snippet": tool.get("snippet"),
    }


def _beurt(messages: list[dict], index: int) -> tuple[str | None, list[dict]]:
    """De vraag en de assistentberichten van de beurt die op `index` eindigt.

    De stappen staan vaak aan een tussenbericht, niet aan het eindantwoord; een
    correctie houdt ze in dezelfde kaart (#398). De trace is dus de hele beurt.
    """
    start = index
    while start > 0 and messages[start - 1].get("role") != "user":
        start -= 1
    vraag = messages[start - 1].get("content") if start > 0 else None
    return vraag, messages[start : index + 1]


def antwoord_trace(messages: list[dict], index: int) -> dict | None:
    """Vraag, antwoord, controle, stappen en ingetrokken tekst van het antwoord op `index`.

    None als daar geen antwoord staat.
    """
    if not 0 <= index < len(messages):
        return None
    msg = messages[index]
    if msg.get("role") != "assistant" or msg.get("isError") or not msg.get("content"):
        return None
    vraag, beurt = _beurt(messages, index)
    return {
        "vraag": vraag,
        "antwoord": msg["content"],
        "controle": msg.get("controle") or [],
        "stappen": [_stap(t) for m in beurt for t in m.get("tools") or []],
        "ingetrokken": [v["tekst"] for m in beurt for v in m.get("vervangen") or []],
    }


def als_markdown(rijen: list[dict]) -> str:
    """De meldingen als één leesbaar overzicht voor het team; per melding een reproduceerbaar rapport."""
    blokken = []
    for rij in rijen:
        trace = json.loads(rij["trace"])
        duim = "👍" if rij["oordeel"] == "up" else "👎"
        blok = [f"## {duim} {rij['created_at']} · {rij['username']} · gesprek {rij['conversation_id']}"]
        if rij["toelichting"]:
            blok.append(f"> {rij['toelichting']}")
        blok += [f"**Vraag:** {trace['vraag'] or '(onbekend)'}", f"**Antwoord:**\n\n{trace['antwoord']}"]
        blok += [f"Controle: {zin}" for zin in trace["controle"]]
        blok += [f"Ingetrokken na controle: {tekst}" for tekst in trace.get("ingetrokken", [])]
        for i, stap in enumerate(trace["stappen"], 1):
            status = f" ({stap['status']})" if stap["status"] else ""
            blok.append(f"{i}. {stap['label']}{status}")
            if stap["snippet"]:
                blok.append(f"```python\n{stap['snippet']}\n```")
        blokken.append("\n\n".join(blok))
    return "\n\n---\n\n".join(blokken) + "\n" if blokken else "Nog geen feedback.\n"
