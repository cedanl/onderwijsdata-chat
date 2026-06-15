import json
import re
from datetime import date

import chainlit as cl
import litellm

from agent.models import litellm_kwargs as _litellm_kwargs
from config import MODEL
from export import generate_dashboard, generate_report


@cl.action_callback("download_rapport_samenvatting")
async def on_download_rapport_samenvatting(action: cl.Action):
    turns = cl.user_session.get("turns", [])
    if not turns:
        await cl.Message(content="Geen gesprek om samen te vatten.").send()
        return

    model = cl.user_session.get("current_model") or MODEL
    status = await cl.Message(content="Samenvatting wordt gegenereerd...").send()

    session_lines: list[str] = []
    for i, turn in enumerate(turns):
        q = turn.get("question", "")
        a = (turn.get("answer", "") or "")[:600]
        figs: list = turn.get("figures", [])
        chart_titles = []
        for fig in figs:
            t = getattr(getattr(getattr(fig, "layout", None), "title", None), "text", None)
            chart_titles.append(t or f"grafiek {len(chart_titles)+1}")
        session_lines.append(f"[{i}] Vraag: {q}")
        session_lines.append(f"    Antwoord: {a}")
        if chart_titles:
            session_lines.append(f"    Grafieken: {', '.join(chart_titles)}")

    prompt = (
        "Je bent een analist die een onderwijsdata-gesprekssessie destilleert tot een beknopt rapport.\n\n"
        "Geef je antwoord als JSON met deze structuur (geen markdown, alleen JSON):\n"
        '{"title": "...", "narrative": "...", "key_findings": ["...", "..."], "selected_turns": [0, 1]}\n\n'
        "Regels:\n"
        "- title: een concrete, beschrijvende rapporttitel\n"
        "- narrative: 2-4 alinea's die de rode draad samenvatten (markdown toegestaan)\n"
        "- key_findings: 3-5 concrete bevindingen als korte bullets\n"
        "- selected_turns: indices van de meest relevante vragen (laat duplicaten of zijsporen weg)\n\n"
        f"Sessie:\n{chr(10).join(session_lines)}"
    )

    spec: dict = {}
    try:
        resp = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            **_litellm_kwargs(model),
        )
        raw = (resp.choices[0].message.content or "").strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        spec = json.loads(raw)
    except Exception:
        pass

    selected = spec.get("selected_turns") or list(range(len(turns)))
    selected = [i for i in selected if 0 <= i < len(turns)] or list(range(len(turns)))
    html = generate_dashboard(turns, spec, selected)
    if status:
        await status.remove()

    await cl.Message(
        content="Samenvatting klaar!",
        elements=[cl.File(name=f"samenvatting-{date.today()}.html", content=html.encode("utf-8"), mime="text/html")],
    ).send()


@cl.action_callback("download_rapport")
async def on_download_rapport(action: cl.Action):
    turns = cl.user_session.get("turns", [])
    html = generate_report(turns)
    await cl.Message(
        content="Rapport klaar!",
        elements=[cl.File(name=f"rapport-{date.today()}.html", content=html.encode("utf-8"), mime="text/html")],
    ).send()
