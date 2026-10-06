import asyncio
import json
import logging

import plotly.io as pio

from core.config import MAX_TOOL_ITERATIONS, MODEL, RUN_SLOW_S, RUN_TIMEOUT_S, SEARCH_CATALOG_LIMIT
from tools import LABELS, SCHEMAS
from tools.schemas import TOOL_CLARIFY_SCOPE

from .aanspreekvorm import je_vorm
from .beweringen import onbeschikbaar_zonder_zoekpad, ongedekte_oorzaak
from .binding import verkeerd_gebonden
from .budget import AFRONDEN, DEELANTWOORD, zonder_antwoord
from .dimensielabels import verkeerde_dimensielabels
from .genoemde_bronnen import genoemde_bronnen
from .grafiekvraag import ontbrekende_grafiek
from .grounding import unverified
from .history import trim
from .kenmerken import verkeerde_kenmerken
from .keuze import genegeerde_keuze
from .kpi_periode import verkeerde_kpi_periodes
from .kpi_scope import kpi_naast_filter
from .labels import onbekende_datasets, ongebruikte_bronnen, verkeerde_opleidingsvormen
from .loop import LoopResult, ToolCall, tool_loop
from .metatekst import metatekst
from .models import build_system
from .probleem import INGEHOUDEN, Probleem, hard, harde, meldingen, veilig
from .selectie import ontbrekende_instellingen, ontbrekende_schooljaren, onvolledige_selecties
from .session_data import record_data_key, record_rekenbewijs
from .stream import Emit
from .tekens import zonder_citaatkop
from .telling import met_telling
from .timebox import timebox
from .vaste_antwoorden import sentinelvraag, weigering

logger = logging.getLogger(__name__)

_TOOL_LIMITS: dict[str, int] = {"search_catalog": SEARCH_CATALOG_LIMIT}
_MAX_TOOL_RESULT_CHARS = 12000

# LiteLLM bug: transform_request for ollama_chat converts tool_calls in history
# messages but never writes them to the output Ollama message, causing orphaned
# tool-result messages on the second LLM call. Patch it here.
if MODEL.startswith(("ollama_chat/", "ollama/")):
    from litellm.llms.ollama.chat.transformation import OllamaChatConfig

    _orig_transform = OllamaChatConfig.transform_request

    def _patched_transform(self, model, messages, optional_params, litellm_params, headers):
        result = _orig_transform(self, model, messages, optional_params, litellm_params, headers)
        for orig, out in zip(messages, result.get("messages", []), strict=False):
            if not isinstance(orig, dict):
                continue
            raw_tools = orig.get("tool_calls")
            if raw_tools and "tool_calls" not in out:
                converted = []
                for tc in raw_tools:
                    args = tc.get("function", {}).get("arguments", "{}")
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {}
                    converted.append({"function": {"name": tc["function"]["name"], "arguments": args}})
                out["tool_calls"] = converted
        return result

    OllamaChatConfig.transform_request = _patched_transform


async def _handle_figure(name: str, figure, session: dict, emit: Emit) -> None:
    """Store *figure* in the session and emit a figure event."""
    if figure is None:
        return
    for key in ("figures", "turn_figures"):
        figs = session.get(key, [])
        figs.append(figure)
        session[key] = figs
    await emit(
        {
            "type": "figure",
            "label": LABELS.get(name, name),
            "figure_json": pio.to_json(figure),
        }
    )


async def _handle_clarify_scope(
    call: ToolCall,
    text_content: str,
    turn_history: list[dict],
    messages: list[dict],
    session: dict,
    emit: Emit,
) -> str:
    """End the turn with a clarification card; returns the text for ``run()``."""
    args = call.args or {}
    vraag = je_vorm(args.get("vraag") or "")
    opties = [_optie_in_je_vorm(o) for o in args.get("opties") or []]

    # The assistant turn that asked has no text of its own; an empty content makes LiteLLM
    # put "[System: Empty message content sanitised…]" in the history, which the model then
    # repeats to the user (#322). The question it asked is the honest text for that turn.
    for m in turn_history:
        if m.get("role") == "assistant" and not (m.get("content") or "").strip():
            m["content"] = vraag or "Verduidelijkingsvraag gesteld."

    # Persist the clarification exchange back to messages so the next
    # turn has the tool_calls context (prevents re-asking same question).
    messages.extend(turn_history)
    session["_clarified"] = True

    # Cancel the open message_start before sending the clarification card.
    # If the LLM produced text before the tool call, close it properly first.
    if text_content:
        await emit({"type": "message_end", "content": text_content, "actions": []})
    else:
        await emit({"type": "message_cancel"})

    await emit(
        {
            "type": "clarification",
            "vraag": vraag,
            "opties": opties,
        }
    )
    return text_content


def _optie_in_je_vorm(optie):
    if isinstance(optie, str):
        return je_vorm(optie)
    if isinstance(optie, dict):
        return {k: je_vorm(v) if k in ("label", "beschrijving") and isinstance(v, str) else v for k, v in optie.items()}
    return optie


def _correction(problems: list[str]) -> str:
    return (
        "Controle van je antwoord tegen de data van dit gesprek:\n"
        + "\n".join(f"- {p}" for p in problems)
        + "\nReken niet zelf en rond niet af: haal elk getal op met query_data (group_by/aggregate) "
        "of compute_kpi, selecteer het gevraagde schooljaar en de gevraagde instelling, of laat het weg.\n"
        "Schrijf daarna een volledig nieuw antwoord voor de gebruiker, alsof het het eerste is: zonder kop of inleiding "
        "over de herziening, zonder te verwijzen naar een eerdere versie of naar deze controle, en zonder toolnamen."
    )


_MAX_CLARIFY_RONDES = 1


def tools_for(session: dict) -> list[dict]:
    """De toolset van deze beurt. Na een beantwoorde scopevraag is clarify_scope er niet meer:
    nooit twee clarifies achter elkaar voor dezelfde vraag (#75), in code en niet alleen in de prompt."""
    if session.get("clarify_rondes", 0) < _MAX_CLARIFY_RONDES:
        return SCHEMAS
    return [t for t in SCHEMAS if t["function"]["name"] != TOOL_CLARIFY_SCOPE]


async def run(
    messages: list[dict],
    session: dict,
    emit: Emit,
    stop_event: asyncio.Event | None = None,
    model: str | None = None,
) -> str:
    settings: dict = session.get("chat_settings") or {}
    chosen_model = model or MODEL

    _raw = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
    last_user_msg = (
        " ".join(b.get("text", "") for b in _raw if isinstance(b, dict)) if isinstance(_raw, list) else str(_raw)
    )
    logger.info("RUN START  model=%s  vraag=%r", chosen_model, last_user_msg[:200])

    if vast := sentinelvraag(last_user_msg):
        await emit({"type": "message_start"})
        await emit({"type": "message_end", "content": vast, "actions": []})
        return vast

    history, was_trimmed = trim(list(messages))
    initial_history_len = len(history)
    if was_trimmed:
        await emit(
            {
                "type": "toast",
                "message": "Oudere berichten vallen buiten de context van het model.",
                "level": "warning",
            }
        )

    # What the assistant already said counts as sourced: a follow-up may repeat a
    # number from an earlier turn. What the user said does not (#211): that is a
    # claim to verify, not evidence. Taken before the loop, so the correction
    # message with the suspect numbers does not source them.
    earlier = [str(m.get("content") or "") for m in history if m.get("role") == "assistant"]
    said_by_user = [str(m.get("content") or "") for m in history if m.get("role") == "user"]

    def ongedekt(n: str) -> Probleem:
        if unverified(n, [], said_by_user):
            (verzonnen,) = hard([Probleem(f"{n} staat niet in de opgehaalde data.")])
            return verzonnen
        # Zacht: een correcte weerlegging citeert het getal van de gebruiker ook (#207, #214).
        return Probleem(
            f"{n} staat alleen in een eerder bericht van de gebruiker, niet in de opgehaalde data.",
            "Dat is een bewering om te toetsen: haal het getal uit de data of laat het weg.",
        )

    def ongedekte_getallen(text: str, tool_results: list[str]) -> list[str]:
        return [ongedekt(n) for n in unverified(text, tool_results, earlier)]

    def check(text: str, tool_results: list[str]) -> list[str]:
        # hard(): blijft het probleem na de herkansing, dan wordt het antwoord ingehouden (#207).
        return [
            *veilig(ongedekte_getallen, text, tool_results),
            *hard(veilig(ontbrekende_schooljaren, last_user_msg, tool_results)),
            *hard(veilig(ontbrekende_instellingen, last_user_msg, tool_results)),
            *hard(veilig(onvolledige_selecties, text, tool_results)),
            *veilig(verkeerde_opleidingsvormen, text, tool_results),
            *veilig(verkeerde_dimensielabels, text, tool_results),
            *veilig(onbekende_datasets, text),
            *veilig(ongebruikte_bronnen, text, tool_results),
            *hard(veilig(verkeerd_gebonden, text, tool_results)),
            *hard(veilig(verkeerde_kenmerken, text, tool_results)),
            *hard(veilig(verkeerde_kpi_periodes, text, tool_results)),
            *veilig(kpi_naast_filter, text, tool_results),
            *veilig(genegeerde_keuze, session.get("clarify_keuzes", []), text),
            *veilig(onbeschikbaar_zonder_zoekpad, last_user_msg, text, tool_results),
            *veilig(ongedekte_oorzaak, text, tool_results),
            *veilig(ontbrekende_grafiek, last_user_msg, text, tool_results, session.get("data_keys", [])),
            *veilig(metatekst, text),
        ]

    async def withdraw(problems: list[str]) -> None:
        await emit({"type": "message_cancel"})
        await emit(
            {
                "type": "toast",
                "message": "Het antwoord klopte niet met de opgehaalde data; het wordt herschreven.",
                "level": "info",
            }
        )

    async def keep(call: ToolCall, result: str, figure) -> None:
        record_data_key(session, result, {"name": call.name, "arguments": call.args})
        record_rekenbewijs(session, result, {"name": call.name, "arguments": call.args})
        await _handle_figure(call.name, figure, session, emit)

    stop = stop_event or asyncio.Event()
    async with timebox(emit, stop, RUN_SLOW_S, RUN_TIMEOUT_S) as box:
        try:
            async with asyncio.timeout(box.afbreken_s):
                result = await tool_loop(
                    history,
                    model=chosen_model,
                    tools=tools_for(session),
                    emit=emit,
                    stop_event=stop,
                    system=build_system(settings, beurt=genoemde_bronnen(last_user_msg)),
                    stream_text=True,
                    on_llm_start=lambda: emit({"type": "message_start"}),
                    on_tool_result=keep,
                    tool_limits=_TOOL_LIMITS,
                    halt_on=frozenset({TOOL_CLARIFY_SCOPE}),
                    max_iterations=MAX_TOOL_ITERATIONS,
                    max_result_chars=_MAX_TOOL_RESULT_CHARS,
                    check=check,
                    correction=_correction,
                    on_correction=withdraw,
                    wrap_up=AFRONDEN,
                )
        except TimeoutError:
            # Vastgelopen aanroep die het stopsignaal niet zag.
            result = LoopResult(aborted="tools")
    if box.verlopen:
        logger.warning("RUN TIMEOUT na %ss  model=%s", RUN_TIMEOUT_S, chosen_model)
        await emit(box.melding())

    if result.aborted == "tools":
        # Stopped while tools ran: close the open message as aborted. No
        # content key, so the client keeps the text it already has.
        await emit({"type": "message_end", "aborted": True})
        return ""
    if result.aborted == "stream":
        await emit({"type": "message_end", "content": result.text, "aborted": True})
        return result.text
    if result.halted_on:
        session["_last_turn_tool_calls"] = result.tool_calls
        return await _handle_clarify_scope(
            result.halted_on,
            result.text,
            history[initial_history_len:],
            messages,
            session,
            emit,
        )
    if result.exhausted:
        text_content = zonder_antwoord(result.steps)
        # partial: the frontend offers 'Opnieuw met <ander model>' (#405).
        await emit({"type": "message_end", "content": text_content, "actions": [], "partial": True})
        return text_content

    text_content = weigering(
        result.text, result.tool_calls, eerder_gesprek=bool(earlier or session.get("data_keys"))
    ) or met_telling(zonder_citaatkop(result.text), result.tool_results)
    if result.wrapped_up:
        text_content = f"{DEELANTWOORD}\n\n{text_content}"
    logger.info("FINALE ANTWOORD  %r", text_content[:500])
    session["_last_turn_tool_calls"] = result.tool_calls
    truncated = result.finish_reason == "length"
    if truncated:
        logger.warning("ANTWOORD AFGEKAPT op outputlimiet  model=%s", chosen_model)
    if not text_content.strip():
        logger.warning("LEEG ANTWOORD  model=%s", chosen_model)
    if result.problems:
        logger.warning("CONTROLE na herkansing nog niet in orde  model=%s  %s", chosen_model, result.problems)
    if harde(result.problems):
        logger.warning("ANTWOORD INGEHOUDEN  model=%s  %r", chosen_model, text_content[:500])
        text_content = INGEHOUDEN
    await emit(
        {
            "type": "message_end",
            "content": text_content,
            "actions": [],
            **({"truncated": True} if truncated else {}),
            **({"partial": True} if result.wrapped_up else {}),
            **({"controle": meldingen(result.problems)} if result.problems else {}),
        }
    )
    return text_content
