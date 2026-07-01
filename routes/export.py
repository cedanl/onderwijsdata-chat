import json
import re
from datetime import date

import litellm
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from agent.models import litellm_kwargs as _litellm_kwargs
from core.config import MODEL
from export import generate_dashboard, generate_report

router = APIRouter(prefix="/api/export", tags=["export"])


@router.post("/rapport")
async def export_rapport(body: dict) -> Response:
    turns = body.get("turns", [])
    html = generate_report(turns)
    return Response(
        content=html,
        media_type="text/html",
        headers={"Content-Disposition": f"attachment; filename=rapport-{date.today()}.html"},
    )


@router.post("/samenvatting")
async def export_samenvatting(body: dict) -> Response:
    turns = body.get("turns", [])
    if not turns:
        raise HTTPException(status_code=400, detail="Geen gesprek om samen te vatten.")

    model = body.get("model") or MODEL
    session_lines: list[str] = []
    for i, turn in enumerate(turns):
        q = turn.get("question", "")
        a = (turn.get("answer", "") or "")[:600]
        session_lines.append(f"[{i}] Vraag: {q}")
        session_lines.append(f"    Antwoord: {a}")

    prompt = (
        "Je bent een analist die een onderwijsdata-gesprekssessie destilleert tot een beknopt rapport.\n\n"
        "Geef je antwoord als JSON met deze structuur (geen markdown, alleen JSON):\n"
        '{"title": "...", "narrative": "...", "key_findings": ["...", "..."], "selected_turns": [0, 1]}\n\n'
        "Regels:\n"
        "- title: een concrete, beschrijvende rapporttitel\n"
        "- narrative: 2-4 alinea's die de rode draad samenvatten (markdown toegestaan)\n"
        "- key_findings: 3-5 concrete bevindingen als korte bullets\n"
        "- selected_turns: indices van de meest relevante vragen\n\n"
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
    return Response(
        content=html,
        media_type="text/html",
        headers={"Content-Disposition": f"attachment; filename=samenvatting-{date.today()}.html"},
    )
