import asyncio
import contextlib
import json
import logging
import os
import uuid
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from agent import recepten
from agent import run as agent_run
from agent.dashboard import DashboardSpec
from agent.dashboard import generate as generate_dashboard_spec
from agent.figuurverschil import figuur_verschillen
from agent.history import afgebroken_beurt
from agent.replay import (
    MODE_REPRODUCEER,
    MODE_VERVERS,
    Figuuruitkomst,
    Reproductie,
    anker_verschillen,
    ankers_van_recipe,
    geldige_modus,
    recept_ids,
    replay_dashboard_figures,
    replay_data_calls,
    reproduceer_figures,
)
from agent.report import RapportGeannuleerd, RapportGeweigerd
from agent.report import generate as generate_report_spec
from config import Config
from core.auth import AUTH_ENABLED, FALLBACK_USER, WS_SUBPROTOCOL, token_uit_protocol, verify_token
from core.config import (
    CHAT_RATE_LIMIT,
    CHAT_RATE_WINDOW_S,
    DASHBOARDS_ENABLED,
    HISTORY_MAX_CHARS,
    MAX_CONCURRENT_RUNS,
    MAX_HISTORY,
    MAX_MESSAGE_CHARS,
    MAX_WS_PER_USER,
    MAX_WS_TOTAL,
    MODEL,
    RUN_QUEUE_TIMEOUT_S,
)
from core.errors import Gebruikersfout, error_event, friendly_error, log_interne_fout
from core.gelijktijdig import Druk, Runplaatsen, Verbindingen
from core.herkomst import origin_toegestaan
from core.logging_context import nieuwe_verbinding
from core.logging_util import gebruiker_kenmerk
from core.rate_limit import RateLimiter
from tools import store

from .instellingen import TAG_STARTERS, tag_voorbeeldvragen

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


# Per gebruiker, niet per IP: achter de ingress delen alle bezoekers één adres (zie routes/feedback.py).
# Zonder login heet iedereen "gast": dan per verbinding, zodat een zaal vol gasten elkaar niet blokkeert.
_berichtlimiter = RateLimiter(max_attempts=CHAT_RATE_LIMIT, window_seconds=CHAT_RATE_WINDOW_S)
_LIMIET_MELDING = "Te veel verzoeken in korte tijd. Probeer het over {wacht} seconden opnieuw."

# Wat er tegelijk mag (#688): open verbindingen per gebruiker en in totaal, en runs die het model aanroepen.
_verbindingen = Verbindingen(per_sleutel=MAX_WS_PER_USER, totaal=MAX_WS_TOTAL)
_runplaatsen = Runplaatsen(max_tegelijk=MAX_CONCURRENT_RUNS, wacht_s=RUN_QUEUE_TIMEOUT_S)
# "Try again later" (RFC 6455); de frontend probeert het met zijn gewone terugval opnieuw.
_TE_VEEL_VERBINDINGEN = 1013
# De origins die naast de eigen een chatverbinding mogen openen (core/herkomst.py, #682).
_CORS_ORIGINS = Config.get_parsed_cors_origins()
_TE_VEEL_MELDING = "Er staan te veel vensters open met deze app. Sluit er een paar en probeer het opnieuw."


async def _in_een_runplaats(start: Callable[[], Awaitable[None]], emit) -> None:
    """Wacht op een vrije runplaats en start dan pas de run; is het te druk, dan een melding en geen run (#688)."""
    try:
        async with _runplaatsen.plaats():
            await start()
    except Druk as e:
        logger.warning("RUNPLAATSEN vol  max=%d  wacht=%ss", MAX_CONCURRENT_RUNS, RUN_QUEUE_TIMEOUT_S)
        await emit({"type": "error", "message": str(e), "modelafhankelijk": False})


def _new_session(username: str | None = None, verbinding: str | None = None) -> dict:
    return {
        "messages": [],
        "figures": [],
        "turns": [],
        "turn_figures": [],
        "chat_settings": {},
        "current_model": None,
        "stop_event": None,
        "_last_turn_tool_calls": [],
        "data_keys": [],
        "data_provenance": {},
        # Moet gelijk zijn aan wat core.auth teruggeeft als auth uit staat, anders
        # schrijft de websocket weg onder een naam waar /api/conversations niet op zoekt.
        "username": username or FALLBACK_USER,
        # Eén ID per WebSocket-verbinding; blijft bij een reset, anders ontloopt een gast de berichtlimiet (#444).
        "verbinding": verbinding or uuid.uuid4().hex[:8],
    }


def _reset_session(session: dict) -> None:
    """Start a new conversation on this connection (#70).

    Everything the agent could remember goes — messages, turns, figures, clarify,
    tool state and loaded data. Only who is chatting and their settings carry over.
    """
    fresh = _new_session(username=session["username"], verbinding=session.get("verbinding"))
    fresh["chat_settings"] = session.get("chat_settings") or {}
    session.clear()
    session.update(fresh)


def _open_conversation(session: dict, messages: list, data_keys: list[str] | None = None) -> None:
    """Continue a stored conversation: a fresh session that knows its text and its own data keys.

    Nothing of the previously open conversation may leak into it — not its turns,
    and not its loaded data, which a report would otherwise pick up. `data_keys` are the
    keys this user saved a recipe for with this conversation (#472).
    """
    _reset_session(session)
    session["messages"] = _parse_history(messages)
    session["data_keys"] = list(data_keys or [])


async def _process_message(content: str, session: dict, emit, model: str | None) -> None:
    messages: list = session["messages"]
    messages.append({"role": "user", "content": content})
    # Waarop 'wij' in deze beurt slaat; wisselt het profiel later, dan hoort het model dat (#543).
    instelling = (session.get("chat_settings") or {}).get("instelling") or ""

    stop_event = asyncio.Event()
    session["stop_event"] = stop_event
    session["turn_figures"] = []

    session["_clarified"] = False
    try:
        response_text = await agent_run(messages, session, emit, stop_event, model=model)
    except Exception as e:
        await emit(error_event(e))
        # De vraag blijft staan, met een afbreekmarkering als antwoord: het gesprek blijft in beurten,
        # een herhaling bouwt op de afgeronde stappen (#431) en een andere vraag gaat niet op deze door (#548).
        messages.append(afgebroken_beurt())
        return

    clarified = session.pop("_clarified", False)
    aborted = stop_event.is_set()
    if aborted:
        # Stopknop of tijdsgrens: wat er al stond plus de markering, geen beurt voor rapport of dashboard.
        messages.append(afgebroken_beurt(response_text))
    elif not clarified:
        messages.append({"role": "assistant", "content": response_text})
        turn_tool_calls = session.get("_last_turn_tool_calls", [])
        session["_last_turn_tool_calls"] = []
        turns: list = session.get("turns", [])
        turns.append(
            {
                "question": content,
                "answer": response_text,
                "tool_calls": turn_tool_calls,
                "figures": session.get("turn_figures", []),
                "instelling": instelling,
            }
        )
        session["turns"] = turns
    session["messages"] = messages


async def _generate_dashboard(session: dict, emit, model: str | None) -> None:
    await emit({"type": "dashboard_generating"})
    try:
        spec = await generate_dashboard_spec(session, emit, model=model)
        await emit({"type": "dashboard_ready", "spec": spec.to_dict()})
    except Gebruikersfout as e:
        # Alleen tekst die voor de gebruiker is geschreven; elke andere fout
        # krijgt via error_event een vaste melding met fout-ID (#503).
        await emit({"type": "error", "message": str(e)})
    except Exception as e:
        await emit(error_event(e))


async def _generate_report(
    session: dict, emit, model: str | None, author: str | None = None, onderzoeksvraag: str | None = None
) -> None:
    await emit({"type": "report_generating"})
    stop_event = asyncio.Event()
    session["stop_event"] = stop_event
    try:
        spec = await generate_report_spec(
            session,
            emit,
            model=model,
            stop_event=stop_event,
            author=author or session.get("username"),
            onderzoeksvraag=onderzoeksvraag,
        )
        await emit({"type": "report_ready", "spec": spec.to_dict()})
    except RapportGeannuleerd:
        await emit({"type": "report_cancelled"})
    except asyncio.CancelledError:
        # Een reset of ander gesprek breekt de taak af; zonder eindbericht wachtte de
        # frontend met voortgang en Annuleer-knop tot de time-out (#417).
        with contextlib.suppress(Exception):
            await emit({"type": "report_cancelled"})
        raise
    except RapportGeweigerd as e:
        # Vaste tekst; `herstel` laat de frontend het rapport opnieuw aanbieden (#515).
        await emit({"type": "report_error", "message": str(e), "herstel": "rapport"})
    except Gebruikersfout as e:
        # Raised on purpose with guidance for the user (e.g. no datasets loaded).
        # Any other exception — a parser error included — falls through to the
        # generic melding below, so no raw exception text reaches the browser (#503).
        await emit({"type": "report_error", "message": str(e)})
    except Exception as e:
        # De fouttekst kan modeluitvoer citeren (een JSONDecodeError op het antwoord): op ERROR
        # alleen type en kenmerk, de traceback op DEBUG (#502).
        log_interne_fout(e, "rapport")
        await emit(
            {
                "type": "report_error",
                "message": "Rapport kon niet worden gemaakt. Probeer het opnieuw.",
            }
        )


class RefreshError(Exception):
    pass


async def _do_refresh(
    recipe: list[dict], figure_recipes: list[dict], current_spec: dict, mode: str = MODE_VERVERS
) -> tuple[DashboardSpec, str | None, list[str]]:
    """De twee herhaalmodi van #346. Returns (updated_spec, info_message_or_None, veranderingen).

    - ververs: opnieuw ophalen bij de bron; `veranderingen` benoemt wat er
      verschilt met het bewaarde dashboard (waarden, bron-ankers).
    - reproduceer: opnieuw renderen uit de data in de store, zonder netwerk.

    Raises RefreshError if refresh fails entirely.
    """
    if not figure_recipes and not recipe:
        raise RefreshError("Dit dashboard kan niet ververst worden.")

    spec = DashboardSpec.from_dict(current_spec)

    if mode == MODE_REPRODUCEER:
        return await _reproduceer(spec, figure_recipes)
    if figure_recipes:
        return await _ververs_figuren(spec, recipe, figure_recipes)

    results = await asyncio.to_thread(replay_data_calls, recipe)
    if melding := _herlaad_mislukt(results):
        raise RefreshError(melding)
    return spec, "Data herladen. Grafieken bijwerken is niet mogelijk bij oudere dashboards.", []


def _herlaad_mislukt(results: list[dict]) -> str | None:
    """De weigering als een dataoproep niet herlaadde; None als alles herlaadde (#524).

    Ververs meldt alleen "ververst" als de data echt opnieuw is opgehaald: één mislukte
    call breekt het geheel af, anders mengen verse en oude figuren onder dat label. De
    redenen per call staan in het log (replay_data_calls); de melding naar de browser
    blijft vrij van paden en uitzonderingstekst (#503).
    """
    mislukt = sum(1 for r in results if not r["success"])
    if not mislukt:
        return None
    return (
        f"De data kon niet opnieuw opgehaald worden: {mislukt} van de {len(results)} dataset(s) niet geladen. "
        "Het bewaarde dashboard is niet gewijzigd. Probeer het later opnieuw."
    )


# _refresh_dashboard kiest het toastniveau op het woord "niet" in de melding: elke
# ververs-melding over een mislukte of niet vervangen grafiek bevat het (warning).
_MAX_NAMEN = 3
_PAST_NIET = "Het bewaarde dashboard past niet bij zijn recept (het aantal grafieken verschilt)."
# Een ververs zonder datarecept haalt niets bij de bron op: de grafieken komen uit de data in het
# geheugen, en dat hoort de melding te zeggen in plaats van "Data ververst" (#528).
# "niets" draagt het woord "niet": de toast wordt een waarschuwing, geen succesmelding.
_GEEN_BRON = (
    "Bij de bron is niets opgehaald: dit dashboard heeft geen datarecept; "
    "de grafieken zijn opnieuw getekend uit de data in het geheugen"
)
_GEHEUGEN = (
    "Reproduceren kan niet: de data van dit dashboard staat niet meer in het geheugen van de "
    "server. Ververs haalt haar opnieuw op bij de bron."
)


async def _ververs_figuren(
    spec: DashboardSpec, recipe: list[dict], figure_recipes: list[dict]
) -> tuple[DashboardSpec, str, list[str]]:
    """Ververs per figuurrecept (#523): een mislukt recept houdt zijn bewaarde figuur en wordt apart gemeld.

    De bewaarde figuren horen via hun index bij de recepten. Past dat niet (een ouder
    dashboard), dan wordt niet per figuur vergeleken en alleen vervangen als elk recept slaagt.
    """
    verversing = await asyncio.to_thread(replay_dashboard_figures, recipe, figure_recipes)
    if melding := _herlaad_mislukt(verversing.calls):
        raise RefreshError(melding)
    uitkomsten = verversing.uitkomsten
    mislukt = [u for u in uitkomsten if u.figuur_json is None]
    if len(mislukt) == len(uitkomsten):
        return spec, "Grafieken konden niet bijgewerkt worden, bestaande data behouden.", []
    passend = len(spec.figures_json) == len(uitkomsten)
    if not passend and mislukt:
        weigering = f"Er is niets vervangen, want niet elke grafiek kon bijgewerkt worden: {_opsomming(mislukt)}."
        return spec, f"{_PAST_NIET} {weigering}", []

    oude_ankers = dict(spec.ankers)
    spec.ankers = await asyncio.to_thread(ankers_van_recipe, recipe, oude_ankers)
    veranderingen = anker_verschillen(oude_ankers, spec.ankers)
    if passend:
        veranderingen += _figuurverschil(spec.figures_json, uitkomsten)
        spec.figures_json = [u.figuur_json or oud for u, oud in zip(uitkomsten, spec.figures_json, strict=True)]
    else:
        spec.figures_json = [u.figuur_json for u in uitkomsten if u.figuur_json is not None]
    return spec, _ververs_melding(veranderingen, mislukt, passend, bron_geraakt=bool(recipe)), veranderingen


def _figuurverschil(bewaard: list[str], uitkomsten: list[Figuuruitkomst]) -> list[str]:
    """Bewaard tegen vers, per recept-id; een mislukt recept blijft aan beide kanten weg."""
    paren = [
        (u.recept_id, oud, vers)
        for u, oud in zip(uitkomsten, bewaard, strict=True)
        if (vers := u.figuur_json) is not None
    ]
    return figuur_verschillen(
        {rid: oud for rid, oud, _ in paren},
        {rid: vers for rid, _, vers in paren},
        [u.recept_id for u in uitkomsten],
    )


def _ververs_melding(
    veranderingen: list[str], mislukt: list[Figuuruitkomst], passend: bool, bron_geraakt: bool = True
) -> str:
    """ "Data ververst" alleen als er bij de bron iets is opgehaald; zonder datarecept zegt de kop dat (#528)."""
    kop = "Data ververst" if bron_geraakt else _GEEN_BRON
    if not passend:
        return (
            f"{kop}. Het bewaarde dashboard paste niet bij zijn recept (het aantal grafieken verschilde): "
            "de grafieken zijn vervangen zonder ze per stuk te vergelijken."
        )
    if veranderingen:
        melding = f"{kop}: {len(veranderingen)} wijziging(en) ten opzichte van het bewaarde dashboard."
    elif mislukt:
        melding = f"{kop}; geen wijzigingen in de grafieken die bijgewerkt zijn."
    else:
        melding = f"{kop}; geen wijzigingen ten opzichte van het bewaarde dashboard."
    return f"{melding} {_niet_bijgewerkt(mislukt)}" if mislukt else melding


def _niet_bijgewerkt(mislukt: list[Figuuruitkomst]) -> str:
    return f"{len(mislukt)} grafiek(en) niet bijgewerkt; de bewaarde versie blijft staan: {_opsomming(mislukt)}."


def _opsomming(mislukt: list[Figuuruitkomst]) -> str:
    """De mislukte grafieken met hun reden, hoogstens _MAX_NAMEN bij naam; de rest geteld."""
    namen = ", ".join(f"{u.naam} ({u.reden})" for u in mislukt[:_MAX_NAMEN])
    rest = len(mislukt) - _MAX_NAMEN
    return f"{namen} en nog {rest} andere" if rest > 0 else namen


def _reproduceer_weigering(repro: Reproductie) -> str:
    """Ontbrekende data verwijst naar ververs; elke andere reden niet, want daar helpt ververs niet (#523)."""
    if not repro.mislukt:
        return _GEHEUGEN
    mislukt = f"{len(repro.mislukt)} grafiek(en) niet te maken uit de opgeslagen data: {_opsomming(repro.mislukt)}."
    return f"{_GEHEUGEN} Daarnaast {mislukt}" if repro.ontbrekend else f"Reproduceren kan niet. {mislukt}"


async def _reproduceer(spec: DashboardSpec, figure_recipes: list[dict]) -> tuple[DashboardSpec, str, list[str]]:
    """Reproduceer de figuren uit de opgeslagen data, zonder netwerk (#346)."""
    if not figure_recipes:
        raise RefreshError("Dit dashboard heeft geen reproduceerbaar recept; alleen verversen is mogelijk.")
    repro = await asyncio.to_thread(reproduceer_figures, figure_recipes)
    if repro.ontbrekend or repro.mislukt:
        # Geen gedeeltelijke reproductie: het bewaarde dashboard blijft zoals het is.
        raise RefreshError(_reproduceer_weigering(repro))
    bewaard = spec.figures_json
    passend = len(bewaard) == len(repro.figures_json)
    afwijkingen = _reproductieverschil(bewaard, repro.figures_json, figure_recipes) if passend else []
    # De spec gaat terug zoals altijd, maar de client bewaart een reproductie niet.
    spec.figures_json = repro.figures_json
    return spec, _reproduceer_melding(bewaard == repro.figures_json, passend, afwijkingen), afwijkingen


def _reproductieverschil(bewaard: list[str], gereproduceerd: list[str], figure_recipes: list[dict]) -> list[str]:
    """Bewaard tegen gereproduceerd, per recept-id; een reproductie slaagt alleen als elk recept slaagt."""
    ids = recept_ids(figure_recipes)
    return figuur_verschillen(dict(zip(ids, bewaard, strict=True)), dict(zip(ids, gereproduceerd, strict=True)), ids)


def _reproduceer_melding(identiek: bool, passend: bool, afwijkingen: list[str]) -> str:
    """De uitkomst van reproduceren; het bewaarde dashboard blijft altijd staan (#524)."""
    if identiek:
        return "Gereproduceerd uit de opgeslagen data; identiek aan het bewaarde dashboard."
    if not passend:
        return (
            f"Gereproduceerd uit de opgeslagen data, maar niet per grafiek te vergelijken. {_PAST_NIET} "
            "Het bewaarde dashboard is niet aangepast."
        )
    if afwijkingen:
        return (
            "De reproductie uit de opgeslagen data wijkt af van het bewaarde dashboard; "
            "het bewaarde dashboard is niet aangepast."
        )
    return (
        "De reproductie uit de opgeslagen data wijkt alleen in de opmaak af, niet in de waarden; "
        "het bewaarde dashboard is niet aangepast."
    )


async def _refresh_dashboard(
    recipe: list[dict],
    figure_recipes: list[dict],
    current_spec: dict,
    session: dict,
    emit,
    model: str | None,
    mode: str = MODE_VERVERS,
) -> None:
    await emit({"type": "dashboard_generating"})
    try:
        spec, info, veranderingen = await _do_refresh(recipe, figure_recipes, current_spec, mode)
        if info:
            level = "warning" if "niet" in info else "info"
            await emit({"type": "toast", "message": info, "level": level})
        for verandering in veranderingen[:3]:
            await emit({"type": "toast", "message": verandering, "level": "info"})
        await emit({"type": "dashboard_ready", "spec": spec.to_dict()})
    except RefreshError as e:
        await emit({"type": "error", "message": str(e)})
    except Exception as e:
        await emit(error_event(e))


@router.post("/api/dashboard/refresh")
async def refresh_dashboard_endpoint(request: Request):
    if not DASHBOARDS_ENABLED:
        return JSONResponse({"error": "Dashboards zijn niet beschikbaar"}, status_code=403)

    if AUTH_ENABLED:
        auth = request.headers.get("authorization", "")
        token = auth.removeprefix("Bearer ").strip()
        if not verify_token(token):
            return JSONResponse({"error": "Niet geautoriseerd"}, status_code=401)

    body = await request.json()
    recipe = body.get("recipe") or []
    figure_recipes = body.get("figure_recipes") or []
    current_spec = body.get("spec") or {}
    mode = body.get("mode") or MODE_VERVERS
    if not geldige_modus(mode):
        return JSONResponse({"error": f"Onbekende modus; kies {MODE_VERVERS} of {MODE_REPRODUCEER}."}, status_code=400)

    try:
        spec, info, veranderingen = await _do_refresh(recipe, figure_recipes, current_spec, mode)
        return {"spec": spec.to_dict(), "mode": mode, "melding": info, "veranderingen": veranderingen}
    except RefreshError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.exception("Dashboard refresh failed")
        return JSONResponse({"error": friendly_error(e)}, status_code=500)


def _parse_history(raw: list) -> list[dict]:
    """Convert frontend message objects to bare {role, content} dicts.

    Capped at MAX_HISTORY beurten en HISTORY_MAX_CHARS tekens in totaal (#500, S15):
    de historie komt van de client en ging zonder tekencap integraal naar het model.
    Boven de cap vallen de oudste beurten af — dezelfde strategie als MAX_HISTORY —
    zodat een bestaand lang gesprek blijft openen. De historie begint na het afvallen altijd
    met een gebruikersbeurt en bevat nooit een beurt zonder tekst.

    Een antwoord dat de browser als afgebroken bewaarde (`afgebroken`) krijgt zijn markering terug,
    ook als er geen tekst van was: anders stond de vraag ervóór weer open (#548).
    """
    valid_roles = {"user", "assistant"}
    result = []
    for m in raw:
        if not isinstance(m, dict) or m.get("role") not in valid_roles or not isinstance(m.get("content"), str):
            continue
        content = m["content"]
        if m["role"] == "assistant" and m.get("afgebroken") is True:
            content = afgebroken_beurt(content)["content"]
        if content.strip():
            result.append({"role": m["role"], "content": content})
    kept: list[dict] = []
    totaal = 0
    for m in reversed(result[-MAX_HISTORY:]):
        content = m["content"]
        if not kept and len(content) > HISTORY_MAX_CHARS:
            # Zelfs de jongste beurt is groter dan de hele cap: afkappen, niet weigeren.
            content = content[:HISTORY_MAX_CHARS]
            m = {**m, "content": content}
        # Een beurt die na afkappen leeg is (cap van 0 tekens) geeft providers een 400.
        if not content.strip() or totaal + len(content) > HISTORY_MAX_CHARS:
            break
        totaal += len(content)
        kept.append(m)
    kept.reverse()
    if len(kept) < len(result):
        # Providers eisen dat de historie met een gebruikersbeurt begint (anders 400): na het
        # afvallen van de oudste beurten kan een antwoord zonder bijbehorende vraag vooraan staan.
        while kept and kept[0]["role"] == "assistant":
            kept.pop(0)
    return kept


def _task_busy(current_task: asyncio.Task | None) -> bool:
    return current_task is not None and not current_task.done()


BUSY_MESSAGE = "Er loopt nog een antwoord. Stop dat eerst of wacht even."


async def _reject_busy(emit) -> None:
    """A request that arrives during a run is refused out loud, never dropped (#145)."""
    await emit({"type": "busy", "message": BUSY_MESSAGE})


def _signal_stop(session: dict) -> None:
    stop_event = session.get("stop_event")
    if stop_event:
        stop_event.set()


def _stop_task(session: dict, task: asyncio.Task | None) -> None:
    if _task_busy(task):
        _signal_stop(session)
        task.cancel()


_STOP_TIMEOUT_S = 5


async def _stop_task_and_wait(session: dict, task: asyncio.Task | None) -> None:
    """Stop the run and wait until it has really ended (#337).

    cancel() only asks; the old run could still send text_deltas after the reset_done of a new
    conversation, which then landed in the new chat.
    """
    if task is None or task.done():
        return
    _stop_task(session, task)
    await asyncio.wait({task}, timeout=_STOP_TIMEOUT_S)


async def _handle_stop(msg: dict, session: dict, emit, current_task: asyncio.Task | None) -> asyncio.Task | None:
    _signal_stop(session)
    return current_task


async def _handle_reset(msg: dict, session: dict, emit, current_task: asyncio.Task | None) -> None:
    await _stop_task_and_wait(session, current_task)
    _reset_session(session)
    await emit({"type": "reset_done"})


async def _handle_ping(msg: dict, session: dict, emit, current_task: asyncio.Task | None) -> asyncio.Task | None:
    # Hartslag van de frontend (#489): een stil weggevallen verbinding merkt de browser
    # anders pas na de TCP-timeout. Het antwoord bewijst dat de lijn nog leeft.
    await emit({"type": "pong"})
    return current_task


async def _handle_settings(msg: dict, session: dict, emit, current_task: asyncio.Task | None) -> asyncio.Task | None:
    session["chat_settings"] = msg.get("settings", {})
    return current_task


async def _handle_history(msg: dict, session: dict, emit, current_task: asyncio.Task | None) -> None:
    await _stop_task_and_wait(session, current_task)
    conv_id = msg.get("conv_id")
    data_keys = await asyncio.to_thread(recepten.keys_van_gesprek, session["username"], conv_id)
    _open_conversation(session, msg.get("messages") or [], data_keys)
    if conv_id is not None:
        # Of een rapport op de data van dit gesprek kan, zonder eerst een vraag opnieuw te stellen (#472).
        await emit({"type": "history_data", "data_keys": len(data_keys)})


def _invoer(msg: dict, sleutel: str) -> str:
    """New user input from a frame, stripped; anything that is not a string counts as empty (#481)."""
    waarde = msg.get(sleutel, "")
    return waarde.strip() if isinstance(waarde, str) else ""


def _te_lang(content: str) -> str | None:
    """The refusal text for new input over MAX_MESSAGE_CHARS (#481), or None when it fits.

    Expects the stripped input from _invoer, so what is measured is what goes on to the agent.
    The text names only the lengths, never the content.
    """
    lengte = len(content)
    if lengte <= MAX_MESSAGE_CHARS:
        return None
    return (
        f"Je bericht is te lang ({lengte} tekens). Het maximum is {MAX_MESSAGE_CHARS} tekens. "
        "Kort het in en probeer opnieuw."
    )


async def _weiger_te_lang(content: str, emit) -> bool:
    """Refuse input over the limit out loud; True when it was refused."""
    melding = _te_lang(content)
    if melding is None:
        return False
    await emit({"type": "error", "message": melding, "modelafhankelijk": False})
    return True


def _limietsleutel(session: dict) -> str:
    username = session.get("username") or FALLBACK_USER
    return username if username != FALLBACK_USER else f"verbinding:{session.get('verbinding')}"


async def _binnen_limiet(session: dict, emit) -> bool:
    """Telt een verzoek dat het model kost mee; boven de limiet een melding met de wachttijd (#444, S5)."""
    sleutel = _limietsleutel(session)
    if _berichtlimiter.is_allowed(sleutel):
        return True
    wacht = _berichtlimiter.retry_after(sleutel) or CHAT_RATE_WINDOW_S
    # Geen gebruikersnaam in het log; de verbinding is aan de regels van die verbinding te koppelen.
    logger.warning("BERICHTLIMIET bereikt  limiet=%d/%ds  wacht=%ds", CHAT_RATE_LIMIT, CHAT_RATE_WINDOW_S, wacht)
    await emit({"type": "error", "message": _LIMIET_MELDING.format(wacht=wacht), "modelafhankelijk": False})
    return False


async def _handle_message(msg: dict, session: dict, emit, current_task: asyncio.Task | None) -> asyncio.Task | None:
    if _task_busy(current_task):
        await _reject_busy(emit)
        return current_task
    content = _invoer(msg, "content")
    if not content or await _weiger_te_lang(content, emit):
        return current_task
    model = session["chat_settings"].get("model") or None
    session["current_model"] = model
    session["clarify_rondes"] = 0
    session["clarify_keuzes"] = []
    if content in TAG_STARTERS:
        tags = TAG_STARTERS[content]
        label = content.removeprefix("Verken ")
        await emit({"type": "starter_questions", "label": label, "questions": tag_voorbeeldvragen(tags)})
        return current_task
    if not await _binnen_limiet(session, emit):
        return current_task
    return asyncio.create_task(_in_een_runplaats(lambda: _process_message(content, session, emit, model), emit))


async def _handle_clarification(
    msg: dict, session: dict, emit, current_task: asyncio.Task | None
) -> asyncio.Task | None:
    if _task_busy(current_task):
        await _reject_busy(emit)
        return current_task
    choice = _invoer(msg, "choice")
    if not choice or await _weiger_te_lang(choice, emit):
        return current_task
    if not await _binnen_limiet(session, emit):
        return current_task
    model = session.get("current_model")
    session["clarify_rondes"] = session.get("clarify_rondes", 0) + 1
    # Afbakening voor de controle na het antwoord, niet alleen tekst in het gesprek (#246).
    session.setdefault("clarify_keuzes", []).append(choice)
    return asyncio.create_task(_in_een_runplaats(lambda: _process_message(choice, session, emit, model), emit))


async def _handle_generate_dashboard(
    msg: dict, session: dict, emit, current_task: asyncio.Task | None
) -> asyncio.Task | None:
    if not DASHBOARDS_ENABLED:
        await emit({"type": "error", "message": "Dashboards zijn niet beschikbaar"})
        return current_task
    if _task_busy(current_task):
        await _reject_busy(emit)
        return current_task
    if not await _binnen_limiet(session, emit):
        return current_task
    model = session["chat_settings"].get("model") or None
    return asyncio.create_task(_in_een_runplaats(lambda: _generate_dashboard(session, emit, model), emit))


async def _handle_generate_report(
    msg: dict, session: dict, emit, current_task: asyncio.Task | None
) -> asyncio.Task | None:
    if _task_busy(current_task):
        await _reject_busy(emit)
        return current_task
    # De onderzoeksvraag die de gebruiker vóór het genereren bevestigde (#750): nieuwe invoer, dus dezelfde grens als
    # een bericht. Zonder (oudere client, API) blijft het onderwerp de eerste vraag van het gesprek.
    onderzoeksvraag = _invoer(msg, "onderzoeksvraag")
    if await _weiger_te_lang(onderzoeksvraag, emit):
        return current_task
    if not await _binnen_limiet(session, emit):
        return current_task
    model = session["chat_settings"].get("model") or None
    author = msg.get("author")
    return asyncio.create_task(
        _in_een_runplaats(
            lambda: _generate_report(session, emit, model, author=author, onderzoeksvraag=onderzoeksvraag or None), emit
        )
    )


async def _handle_refresh_dashboard(
    msg: dict, session: dict, emit, current_task: asyncio.Task | None
) -> asyncio.Task | None:
    if not DASHBOARDS_ENABLED:
        await emit({"type": "error", "message": "Dashboards zijn niet beschikbaar"})
        return current_task
    if _task_busy(current_task):
        await _reject_busy(emit)
        return current_task
    recipe = msg.get("recipe") or []
    figure_recipes = msg.get("figure_recipes") or []
    current_spec = msg.get("spec") or {}
    mode = msg.get("mode") or MODE_VERVERS
    if not geldige_modus(mode):
        await emit({"type": "error", "message": f"Onbekende modus; kies {MODE_VERVERS} of {MODE_REPRODUCEER}."})
        return current_task
    model = session["chat_settings"].get("model") or None
    return asyncio.create_task(
        _in_een_runplaats(
            lambda: _refresh_dashboard(recipe, figure_recipes, current_spec, session, emit, model, mode), emit
        )
    )


Handler = Callable[[dict, dict, Callable, asyncio.Task | None], Awaitable[asyncio.Task | None]]

# Per actie van de frontend een handler: (bericht, sessie, emit, lopende taak) -> lopende taak (#206).
ACTIES: dict[str, Handler] = {
    "stop": _handle_stop,
    "ping": _handle_ping,
    "reset": _handle_reset,
    "settings": _handle_settings,
    "history": _handle_history,
    "message": _handle_message,
    "clarification_choice": _handle_clarification,
    "generate_dashboard": _handle_generate_dashboard,
    "generate_report": _handle_generate_report,
    "refresh_dashboard": _handle_refresh_dashboard,
}


# Noemt de actie niet: de melding herhaalt geen invoer (#637).
ONBEKENDE_ACTIE = "Onbekende actie. Ververs de pagina en probeer opnieuw."


async def _dispatch(msg: dict, session: dict, emit, current_task: asyncio.Task | None) -> asyncio.Task | None:
    actie = msg.get("action")
    # Een lijst of object als actie is niet hashbaar: dat gaf een TypeError en sloot de verbinding.
    handler = ACTIES.get(actie) if isinstance(actie, str) else None
    if handler is None:
        # Type plus een ingekorte repr: de verbinding blijft open, dus een enorme actie niet per frame volledig loggen.
        logger.warning("Onbekende websocket-actie genegeerd: %s %.80r", type(actie).__name__, actie)
        # Hardop weigeren, zoals bij een te lang bericht: anders wacht de client tot zijn time-out.
        await emit({"type": "error", "message": ONBEKENDE_ACTIE, "modelafhankelijk": False})
        return current_task
    return await handler(msg, session, emit, current_task)


@router.websocket("/api/chat")
async def chat_websocket(ws: WebSocket) -> None:
    # Vóór het token: een andere site die de gebruiker open heeft, krijgt geen verbinding, ook zonder login (#682).
    origin = ws.headers.get("origin")
    if not origin_toegestaan(origin, ws.headers.get("host"), _CORS_ORIGINS, lokaal=Config.APP_ENV == "local"):
        logger.warning("VERBINDING geweigerd: origin niet toegestaan")
        await ws.close(code=4003, reason="Origin niet toegestaan")
        return
    username = None
    token = token_uit_protocol(ws.headers.get("sec-websocket-protocol"))
    if AUTH_ENABLED:
        username = verify_token(token or "")
        if not username:
            await ws.close(code=4001, reason="Niet geautoriseerd")
            return

    # Het subprotocol bevestigen, anders sluit de browser de verbinding (#103).
    await ws.accept(subprotocol=WS_SUBPROTOCOL if token else None)
    # Elke logregel van deze verbinding, ook uit taken en threads, draagt dit ID (#502).
    # Het pseudoniem koppelt de TOKENS-regels van deze verbinding aan een gebruiker, voor de kosten (#678).
    logger.info("VERBINDING open verbinding=%s gebruiker=%s", nieuwe_verbinding(), gebruiker_kenmerk(username))

    # Zonder login heet iedereen "gast": dan telt alleen het totaal (#688).
    sleutel = username if username and username != FALLBACK_USER else None
    if not _verbindingen.open(sleutel):
        # Pas na accept: zo leest de gebruiker waarom, in plaats van een kale 1006.
        logger.warning("VERBINDINGEN vol  open=%d  max=%d/%d", _verbindingen.aantal, MAX_WS_PER_USER, MAX_WS_TOTAL)
        await ws.send_text(json.dumps({"type": "error", "message": _TE_VEEL_MELDING, "modelafhankelijk": False}))
        await ws.close(code=_TE_VEEL_VERBINDINGEN)
        return
    try:
        await _bedien(ws, username)
    finally:
        _verbindingen.sluit(sleutel)


async def _bedien(ws: WebSocket, username: str | None) -> None:
    """Eén geaccepteerde chatverbinding, tot de browser hem sluit."""
    session = _new_session(username=username)

    async def emit(event: dict) -> None:
        await ws.send_text(json.dumps(event))

    from core.config import get_all_api_key_env_vars

    is_ollama = MODEL.startswith(("ollama_chat/", "ollama/"))
    if not is_ollama and not any(os.getenv(k) for k in get_all_api_key_env_vars()):
        await emit(
            {
                "type": "system_message",
                "message": "Geen API key gevonden. Stel een omgevingsvariabele in (bijv. ANTHROPIC_API_KEY) en herstart de app.",
            }
        )

    current_task: asyncio.Task | None = None

    try:
        # Elke tool van deze verbinding, ook in een taak of thread, kent de keys van het eigen gesprek (#13).
        with store.gesprek(lambda: session.get("data_keys") or []):
            while True:
                raw = await ws.receive_text()
                msg = json.loads(raw)
                current_task = await _dispatch(msg, session, emit, current_task)
    except WebSocketDisconnect:
        _stop_task(session, current_task)
