import asyncio
import contextlib
import json
import logging
import uuid
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agent import beurtbewijs, rapportselectie, recepten
from agent import run as agent_run
from agent.history import afgebroken_beurt, trim
from agent.report import RapportGeannuleerd, RapportGeweigerd
from agent.report import generate as generate_report_spec
from agent.timebox import harde_grens
from config import Config
from core.auth import AUTH_ENABLED, FALLBACK_USER, WS_SUBPROTOCOL, token_uit_protocol, verify_token
from core.config import (
    CHAT_RATE_LIMIT,
    CHAT_RATE_WINDOW_S,
    GENEREER_TIMEOUT_S,
    HISTORY_MAX_CHARS,
    MAX_CONCURRENT_RUNS,
    MAX_MESSAGE_CHARS,
    MAX_WS_PER_USER,
    MAX_WS_TOTAL,
    MODEL,
    RUN_QUEUE_TIMEOUT_S,
    toegestaan_model,
)
from core.errors import MODEL_ZONDER_SLEUTEL, Gebruikersfout, error_event, log_interne_fout
from core.gelijktijdig import Druk, Runplaatsen, Verbindingen
from core.herkomst import origin_toegestaan
from core.logging_context import nieuwe_verbinding
from core.logging_util import gebruiker_kenmerk, tekst_kenmerk
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
# "Try again later" (RFC 6455). De frontend probeert het dan niet zelf opnieuw, maar wacht op "Opnieuw verbinden" (#783).
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


def _open_conversation(
    session: dict, messages: list, data_keys: list[str] | None = None, bewijs: dict[str, dict] | None = None
) -> None:
    """Continue a stored conversation: a fresh session that knows its text and its own data keys.

    Nothing of the previously open conversation may leak into it — not its turns,
    and not its loaded data, which a report would otherwise pick up. `data_keys` are the
    keys this user saved a recipe for with this conversation (#472). `bewijs` are the rows
    of the answers in it (lineage, calculations, maps), so a report sees what the living
    conversation saw (ADR-009, #875).
    """
    _reset_session(session)
    session["messages"] = _parse_history(messages)
    session["data_keys"] = list(data_keys or [])
    beurtbewijs.zet_terug(session, bewijs or {})


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
        # Stopknop of tijdsgrens: wat er al stond plus de markering, geen beurt voor het rapport.
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
        # Het bewijs van dit antwoord wacht tot de client het gesprek opslaat (ADR-009, #875).
        beurtbewijs.zet_klaar(session, turns[-1], response_text)
    session["messages"] = messages


# Wat de gebruiker leest als een rapport de tijdsgrens haalt (#759); de minuten uit GENEREER_TIMEOUT_S.
def _over_de_tijdsgrens(wat: str) -> str:
    return f"{wat} kwam niet binnen {GENEREER_TIMEOUT_S / 60:.0f} minuten af. Probeer het opnieuw, of kies een ander model."


async def _generate_report(
    session: dict,
    emit,
    model: str | None,
    author: str | None = None,
    onderzoeksvraag: str | None = None,
    beurten: frozenset[int] | None = None,
) -> None:
    await emit({"type": "report_generating"})
    stop_event = asyncio.Event()
    session["stop_event"] = stop_event
    # Aan de serverkant (#759): een hangende modelaanroep hield anders de runplaats bezet, en elke nieuwe vraag kreeg
    # "Er loopt nog een antwoord", ook nadat de frontend na 10 min zelf had opgegeven.
    try:
        async with harde_grens(GENEREER_TIMEOUT_S) as grens:
            spec = await generate_report_spec(
                session,
                emit,
                model=model,
                stop_event=stop_event,
                author=author or session.get("username"),
                onderzoeksvraag=onderzoeksvraag,
                beurten=beurten,
            )
        await emit({"type": "report_ready", "spec": spec.to_dict()})
    except TimeoutError as e:
        if not grens.expired():
            # Een time-out van iets binnen het rapport (een bron), niet de grens: de gewone foutmelding.
            log_interne_fout(e, "rapport")
            await emit({"type": "report_error", "message": "Rapport kon niet worden gemaakt. Probeer het opnieuw."})
            return
        logger.warning("RAPPORT TIMEOUT na %.0f s", GENEREER_TIMEOUT_S)
        # `herstel`: de frontend biedt het rapport opnieuw aan, zoals bij een weigering (#515).
        await emit({"type": "report_error", "message": _over_de_tijdsgrens("Het rapport"), "herstel": "rapport"})
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


def _parse_history(raw: list) -> list[dict]:
    """Convert frontend message objects to bare {role, content} dicts.

    Capped at MAX_HISTORY beurten en HISTORY_MAX_CHARS tekens in totaal (#500, S15):
    de historie komt van de client en ging zonder tekencap integraal naar het model.
    Het aantal kort agent/history.trim in, zoals in het live gesprek: de eerste vraag blijft,
    want die is het onderwerp van het rapport (#789). Boven de tekencap vallen daarna
    de oudste beurten af, zodat een bestaand lang gesprek blijft openen. De historie begint na
    het afvallen altijd met een gebruikersbeurt en bevat nooit een beurt zonder tekst.

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
    for m in reversed(trim(result)[0]):
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
    instellingen = msg.get("settings", {})
    if not isinstance(instellingen, dict):
        # Elke lezer van chat_settings verwacht een object (#758): de vorige instellingen blijven staan.
        logger.warning("Websocket-instellingen genegeerd: %s in plaats van een object", type(instellingen).__name__)
        await _weiger_frame(emit)
        return current_task
    session["chat_settings"] = instellingen
    return current_task


async def _handle_history(msg: dict, session: dict, emit, current_task: asyncio.Task | None) -> asyncio.Task | None:
    berichten = msg.get("messages") or []
    if not isinstance(berichten, list):
        # Een getal als historie gaf een TypeError en sloot de verbinding (#758); het open gesprek blijft.
        logger.warning("Websocket-historie genegeerd: %s in plaats van een lijst", type(berichten).__name__)
        await _weiger_frame(emit)
        return current_task
    await _stop_task_and_wait(session, current_task)
    conv_id = msg.get("conv_id")
    data_keys = await asyncio.to_thread(recepten.keys_van_gesprek, session["username"], conv_id)
    bewijs = await asyncio.to_thread(beurtbewijs.rijen_voor, session["username"], conv_id, berichten)
    _open_conversation(session, berichten, data_keys, bewijs)
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


def _model(session: dict) -> str:
    """Het model van deze beurt uit de instellingen van de client, begrensd tot het aanbod (#755)."""
    instellingen = session.get("chat_settings")
    gevraagd = instellingen.get("model") if isinstance(instellingen, dict) else None
    model = toegestaan_model(session.get("username"), gevraagd)
    if gevraagd and gevraagd != model:
        # De naam is invoer van de client: alleen een kenmerk in het log (#580).
        logger.warning("Modelkeuze buiten het aanbod, MODEL gebruikt: %s", tekst_kenmerk(str(gevraagd), "model_"))
    return model


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
    model = _model(session)
    session["current_model"] = model
    session["clarify_rondes"] = 0
    session["clarify_keuzes"] = []
    session["clarify_slots"] = []
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
    # De beurten met data die de gebruiker in het rapport hield (#908): de client wordt niet vertrouwd, dus de selectie
    # wordt tegen het gesprek gecontroleerd, vóór er een run of een berichtlimiet aan te pas komt.
    try:
        beurten = rapportselectie.kies(session, msg.get("beurten"))
    except Gebruikersfout as e:
        await emit({"type": "error", "message": str(e), "modelafhankelijk": False})
        return current_task
    if not await _binnen_limiet(session, emit):
        return current_task
    model = _model(session)
    author = msg.get("author")
    return asyncio.create_task(
        _in_een_runplaats(
            lambda: _generate_report(
                session, emit, model, author=author, onderzoeksvraag=onderzoeksvraag or None, beurten=beurten
            ),
            emit,
        )
    )


async def _handle_report_checklist(
    msg: dict, session: dict, emit, current_task: asyncio.Task | None
) -> asyncio.Task | None:
    """De beurten met data van het open gesprek, voor de checklist bij "Genereer rapport" (#908).

    Alleen lezen, uit code: geen model, geen run, dus ook geen berichtlimiet. Het antwoord kan leeg zijn (geen data, of
    een gesprek van vóór #875 zonder bewijs per beurt); de frontend toont dan alleen het veld met de onderzoeksvraag.
    In het log staan alleen aantallen: een vraag van de gebruiker hoort daar op INFO niet.
    """
    items = rapportselectie.beurten_met_data(session)
    logger.info("RAPPORT checklist  beurten=%d", len(items))
    await emit({"type": "report_checklist", "items": items})
    return current_task


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
    "generate_report": _handle_generate_report,
    "report_checklist": _handle_report_checklist,
}


# Noemt de actie niet: de melding herhaalt geen invoer (#637).
ONBEKENDE_ACTIE = "Onbekende actie. Ververs de pagina en probeer opnieuw."


async def _weiger_frame(emit) -> None:
    """Hardop weigeren, zoals bij een te lang bericht: anders wacht de client tot zijn time-out. De verbinding blijft."""
    await emit({"type": "error", "message": ONBEKENDE_ACTIE, "modelafhankelijk": False})


def _frame(raw: str) -> dict | None:
    """Het frame als object; None bij geen JSON of een ander type, dat in het log alleen zijn type noemt (#637, #758)."""
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Websocket-frame genegeerd: geen JSON (%d tekens)", len(raw))
        return None
    if not isinstance(msg, dict):
        logger.warning("Websocket-frame genegeerd: %s in plaats van een object", type(msg).__name__)
        return None
    return msg


# Acties die een run starten (model of tools): daarvoor geldt het token opnieuw, niet alleen bij het verbinden (#786).
RUN_ACTIES = frozenset({"message", "clarification_choice", "generate_report"})


async def _token_geldt_nog(msg: dict, token: str | None) -> bool:
    """Toets vóór elke run het token van de handshake opnieuw (#786, besluit A).

    Uitloggen in een ander tabblad, het verlopen van het token en "verwijder al mijn gegevens" raken zo ook een open
    verbinding. Eén DB-lookup in een thread (#763), gedeeld door alle pods (#677). De hartslag en de andere acties
    starten niets dat kost, en lezen de database dus niet bij elk frame.
    """
    actie = msg.get("action")
    if not AUTH_ENABLED or not isinstance(actie, str) or actie not in RUN_ACTIES:
        return True
    return bool(await asyncio.to_thread(verify_token, token or ""))


async def _dispatch(msg: dict, session: dict, emit, current_task: asyncio.Task | None) -> asyncio.Task | None:
    actie = msg.get("action")
    # Een lijst of object als actie is niet hashbaar: dat gaf een TypeError en sloot de verbinding.
    handler = ACTIES.get(actie) if isinstance(actie, str) else None
    if handler is None:
        # Type plus een ingekorte repr: de verbinding blijft open, dus een enorme actie niet per frame volledig loggen.
        logger.warning("Onbekende websocket-actie genegeerd: %s %.80r", type(actie).__name__, actie)
        await _weiger_frame(emit)
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
        # De denylist staat in de database: een trage of volle pool bevroor anders elke chatstream (#763).
        username = await asyncio.to_thread(verify_token, token or "")
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
        await _bedien(ws, username, token)
    finally:
        _verbindingen.sluit(sleutel)


async def _bedien(ws: WebSocket, username: str | None, token: str | None) -> None:
    """Eén geaccepteerde chatverbinding, tot de browser hem sluit of het token niet meer geldt (#786)."""
    session = _new_session(username=username)

    async def emit(event: dict) -> None:
        await ws.send_text(json.dumps(event))

    from core.config import get_all_api_key_env_vars, llm_sleutel_aanwezig

    if not llm_sleutel_aanwezig(MODEL):
        sleutels = get_all_api_key_env_vars()
        # Een beheerderszaak (#712, #790): de namen in het log, de gebruiker een melding zonder `.env`. WARNING: per
        # verbinding herhaald, en /ready geeft dan al 503.
        logger.warning(
            "Geen API-sleutel gezet: verwacht een van %s in het secret of `.env`", ", ".join(sorted(sleutels))
        )
        await emit({"type": "system_message", "message": MODEL_ZONDER_SLEUTEL})

    current_task: asyncio.Task | None = None

    try:
        # Elke tool van deze verbinding, ook in een taak of thread, kent de keys van het eigen gesprek (#13).
        with store.gesprek(lambda: session.get("data_keys") or []):
            while True:
                msg = _frame(await ws.receive_text())
                if msg is None:
                    await _weiger_frame(emit)
                    continue
                try:
                    geldig = await _token_geldt_nog(msg, token)
                except Exception as e:
                    # Een storing is geen "sessie voorbij" (zie verify_token): geen 4001, maar ook geen run.
                    await emit(error_event(e))
                    continue
                if not geldig:
                    # Bij 4001 beëindigt de client de sessie, of verbindt opnieuw met een intussen ververst token
                    # (useChat.js). De finally stopt een lopende taak.
                    logger.info("VERBINDING dicht: token geldt niet meer")
                    await ws.close(code=4001, reason="Niet geautoriseerd")
                    return
                current_task = await _dispatch(msg, session, emit, current_task)
    except WebSocketDisconnect:
        pass
    finally:
        # Ook als de lus om een andere reden eindigt: een lopende taak draaide anders door tot haar volgende emit (#758).
        _stop_task(session, current_task)
