"""Nepmodel voor lokaal testen zonder providersleutel (#1065).

Met `MODEL=mock/<scenario>` antwoordt dit model in plaats van een echte provider: vast, herhaalbaar en zonder netwerk
naar een LLM. De toollaag (catalogus, CBS, DUO, RIO), de controles en de UI draaien gewoon; alleen het model is nep.
`acompletion_with_backoff` (agent/ratelimit.py) geeft dan deze stroom terug in plaats van `litellm.acompletion`. De
stukken hebben de vorm van een LiteLLM-stream, zodat `accumulate_stream` ze leest zoals een echte.

Alleen voor `APP_ENV` local en development: `Config.validate()` weigert het model elders (config.py).

Scenario's:
- `default`: zoekt in de catalogus met de vraag als zoekterm, laadt een vaste maat (mbo-studenten landelijk, CBS) en
  antwoordt met wat de tools teruggaven. Het laden gaat naar CBS: zonder internet faalt die stap en antwoordt het
  nepmodel met de catalogustreffer alleen.
- `tekst`: antwoordt met een vaste tekst, zonder tools en zonder netwerk.
- `verzonnen`: antwoordt eerst met een getal dat in geen data staat (`VERZONNEN`, over twee tekststukken verdeeld:
  "27." en "135"), zonder tools en zonder netwerk. De getalcontrole trekt dat antwoord in; in de correctieronde
  antwoordt het nepmodel zonder getal. Zo toetst tests/e2e/mock-llm.spec.js dat een ingetrokken getal nooit in beeld
  stond (#1254).

Een rapportaanvraag (de toolset van agent/report.py, zonder search_catalog) krijgt in elk scenario een kort vast rapport.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from typing import Any

from litellm.types.utils import (
    ChatCompletionDeltaToolCall,
    Delta,
    Function,
    ModelResponseStream,
    StreamingChoices,
    Usage,
)

from core.config import NEP_PREFIX, is_nepmodel

__all__ = ["is_nepmodel", "keuze", "scenario", "stroom"]

_ZOEK = "search_catalog"
_MAAT = "get_maat"
_QUERY = "query_data"
# De vaste maat van het scenario default: één kleine CBS-tabel, zonder instelling of sector.
_VASTE_MAAT = {"maat": "mbo_studenten_landelijk"}
# Zo lang is een tekststuk in de stroom: het antwoord komt in delen binnen, zoals bij een echt model.
_STUK = 24

KOP = "Nepmodel (lokaal testen, geen echt taalmodel)."
# Het getal van scenario verzonnen. De zin valt zo in stukken van _STUK dat het getal over twee stukken loopt.
VERZONNEN = "27.135"
_VERZONNEN_ZIN = f"Een verzonnen getal van dit nepmodel: er zijn {VERZONNEN} studenten."
_ZONDER_GETAL = "Dit nepmodel heeft geen data opgehaald en noemt daarom geen aantal."
# De correctieronde begint met deze woorden (agent/controles.py, correctie).
_CORRECTIE = "Controle van je antwoord"
# Pauze tussen de tekststukken van scenario verzonnen, zoals bij een echt model: zonder pauze komen alle stukken en de
# intrekking in één frame binnen en tekent de browser de eerste versie nooit. Een vaste pauze, want de timing van het
# streamen is hier wat de test meet (tests/e2e/mock-llm.spec.js, #1254).
_PAUZE_S = 0.04


def scenario(model: str) -> str:
    """Het scenario uit de modelnaam: `mock/tekst` is `tekst`. Welke er zijn, staat in core/config.py (NEP_SCENARIOS)."""
    return model[len(NEP_PREFIX) :].strip().lower()


def _naam(tool: dict) -> str:
    return str((tool.get("function") or {}).get("name") or "")


def _tekst(content: Any) -> str:
    if isinstance(content, list):
        return " ".join(str(b.get("text", "")) for b in content if isinstance(b, dict))
    return str(content or "")


def _beurtbegin(messages: list[dict]) -> int:
    """De index van de vraag waarmee deze beurt begon, of -1.

    Een herkansing (correctie na een antwoord) of afrondvraag is ook een gebruikersbericht, maar hoort bij dezelfde
    beurt: het komt direct na een toolresultaat, of na een antwoord dat zelf op een toolresultaat volgde.
    """
    vragen = [i for i, m in enumerate(messages) if m.get("role") == "user"]
    while vragen:
        u = vragen.pop()
        vorige = messages[u - 1] if u >= 1 else {}
        binnen_beurt = vorige.get("role") == "tool" or (
            vorige.get("role") == "assistant"
            and not vorige.get("tool_calls")
            and u >= 2
            and messages[u - 2].get("role") == "tool"
        )
        if not binnen_beurt or not vragen:
            return u
    return -1


def _toolresultaten(messages: list[dict]) -> list[tuple[str, str]]:
    """(toolnaam, resultaat) in volgorde; de naam komt uit de aanroep van de assistent met hetzelfde id."""
    namen: dict[str, str] = {}
    uit: list[tuple[str, str]] = []
    for m in messages:
        for tc in m.get("tool_calls") or []:
            namen[str(tc.get("id"))] = str((tc.get("function") or {}).get("name") or "")
        if m.get("role") == "tool":
            uit.append((namen.get(str(m.get("tool_call_id")), ""), _tekst(m.get("content"))))
    return uit


def _json(tekst: str) -> dict:
    try:
        uit = json.loads(tekst)
    except (TypeError, ValueError):
        return {}
    return uit if isinstance(uit, dict) else {}


def _uit_catalogus(resultaat: str) -> str:
    """Een zin over de eerste kandidaat van search_catalog, of over de status als er geen is."""
    envelop = _json(resultaat)
    kandidaten = envelop.get("kandidaten") or []
    if kandidaten and isinstance(kandidaten[0], dict):
        k = kandidaten[0]
        titel = k.get("titel") or k.get("bron") or k.get("title") or ""
        return f"In de catalogus vond ik als eerste {k.get('dataset_id', '?')}{f' ({titel})' if titel else ''}."
    return f"De catalogus gaf geen kandidaten (status: {envelop.get('status', 'onbekend')})."


def _uit_maat(resultaat: str) -> str:
    """Een zin met de laatste rij van get_maat: periode en waarde zoals de tool ze gaf."""
    uit = _json(resultaat)
    rijen = uit.get("rijen") or []
    if not rijen or not isinstance(rijen[-1], dict):
        return "De vaste maat kon niet worden geladen."
    rij = rijen[-1]
    periode = rij.get(f"{uit.get('periodekolom')}_label") or rij.get(str(uit.get("periodekolom")), "?")
    waarde = rij.get(str(uit.get("waardekolom")), "?")
    # Woorden tussen periode en waarde: "2021/'22 512100" leest de getalcontrole als één getal.
    return f"Volgens de vaste maat {uit.get('maat', '?')} telde schooljaar {periode} in totaal {waarde} mbo-studenten."


def _antwoord(resultaten: list[tuple[str, str]], scenario_: str) -> str:
    zinnen = [KOP]
    for naam, resultaat in resultaten:
        if naam == _ZOEK:
            zinnen.append(_uit_catalogus(resultaat))
        elif naam == _MAAT:
            zinnen.append(_uit_maat(resultaat))
    if len(zinnen) == 1:
        zinnen.append(f"Dit is een vast antwoord van scenario {scenario_}, zonder data.")
    return " ".join(zinnen)


def _rapport(messages: list[dict]) -> str:
    """Een kort vast rapport in het JSON-blok dat agent/report.py leest.

    Een rapport moet een getal uit de data noemen (agent/report_checks.py): het nepmodel neemt het aantal rijen van de
    eerste dataset uit de systeemprompt ("- Rijen: n"), dat ook in de context van de controle staat.
    """
    prompt = " ".join(_tekst(m.get("content")) for m in messages if m.get("role") == "system")
    rijen = re.search(r"- Rijen: (\d+)", prompt)
    conclusie = "Het nepmodel schreef dit rapport op de geladen data, zonder eigen analyse."
    if rijen:
        conclusie = f"De geladen tabel heeft {rijen.group(1)} rijen. {conclusie}"
    spec = {
        "title": "Nep-rapport",
        "onderzoeksvraag": "",
        "beantwoordt": ["Dit rapport komt van het nepmodel en dient alleen om de rapportroute te testen."],
        "beantwoordt_niet": ["Inhoudelijke conclusies: er is geen echt taalmodel gebruikt."],
        "conclusie": conclusie,
        "visualisaties": [],
    }
    return "```json\n" + json.dumps(spec, ensure_ascii=False) + "\n```"


def keuze(model: str, messages: list[dict], tools: list[dict] | None, tool_choice: Any = None) -> dict:
    """Wat het nepmodel deze ronde doet: `{"tekst": ...}` of `{"tool": naam, "argumenten": {...}}`."""
    namen = {_naam(t) for t in tools or []}
    scen = scenario(model)
    if _ZOEK not in namen and _QUERY in namen:
        return {"tekst": _rapport(messages)}
    begin = _beurtbegin(messages)
    vraag = _tekst(messages[begin].get("content")) if begin >= 0 else ""
    if scen == "verzonnen":
        return {"tekst": f"{KOP} {_ZONDER_GETAL if vraag.startswith(_CORRECTIE) else _VERZONNEN_ZIN}"}
    deze_beurt = _toolresultaten(messages[begin + 1 :])
    gedaan = {naam for naam, _ in deze_beurt}
    if scen == "default" and tool_choice != "none":
        if not deze_beurt and _ZOEK in namen:
            return {"tool": _ZOEK, "argumenten": {"query": vraag.strip()[:200] or "studenten"}}
        if _ZOEK in gedaan and _MAAT not in gedaan and _MAAT in namen:
            return {"tool": _MAAT, "argumenten": dict(_VASTE_MAAT)}
    return {"tekst": _antwoord(deze_beurt, scen)}


def _stuk(model: str, delta: Delta, finish_reason: str | None = None) -> ModelResponseStream:
    return ModelResponseStream(
        model=model, choices=[StreamingChoices(index=0, delta=delta, finish_reason=finish_reason)]
    )


async def stroom(model: str, messages: list[dict], tools: list[dict] | None, tool_choice: Any = None) -> AsyncIterator:
    """De ronde als LiteLLM-stream: tekst in stukken of één toolaanroep, dan het slot en het gebruik."""
    stap = keuze(model, messages, tools, tool_choice)
    if "tool" in stap:
        aanroep = ChatCompletionDeltaToolCall(
            id=f"nep-{stap['tool']}-{len(messages)}",
            index=0,
            type="function",
            function=Function(name=stap["tool"], arguments=json.dumps(stap["argumenten"], ensure_ascii=False)),
        )
        yield _stuk(model, Delta(content=None, tool_calls=[aanroep]))
        yield _stuk(model, Delta(content=None), finish_reason="tool_calls")
        uitvoer = 10
    else:
        tekst = stap["tekst"]
        for i in range(0, len(tekst), _STUK):
            if i and scenario(model) == "verzonnen":
                await asyncio.sleep(_PAUZE_S)
            yield _stuk(model, Delta(content=tekst[i : i + _STUK]))
        yield _stuk(model, Delta(content=None), finish_reason="stop")
        uitvoer = max(1, len(tekst) // 4)
    yield ModelResponseStream(model=model, choices=[], usage=Usage(prompt_tokens=0, completion_tokens=uitvoer))
