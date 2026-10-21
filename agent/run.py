import asyncio
import json
import logging
from collections.abc import Callable
from functools import partial

import plotly.io as pio

from core.config import (
    MAX_TOOL_ITERATIONS,
    MODEL,
    RUN_SLOW_S,
    RUN_TIMEOUT_S,
    SEARCH_CATALOG_LIMIT,
    TOOL_RESULT_MAX_CHARS,
)
from core.errors import log_interne_fout
from core.logging_util import tekst_kenmerk
from tools import LABELS, SCHEMAS, ho_markers
from tools.csv_export import export_key, geen_export_reden
from tools.schemas import TOOL_CLARIFY_SCOPE

from . import manifest, recepten, vervolgvragen
from .aanspreekcontrole import overgebleven_u_vorm
from .aanspreekvorm import in_je_vorm, je_vorm
from .antwoordtaal import Taal, taal, taalinstructie, verkeerde_antwoordtaal
from .beweringen import onbeschikbaar_zonder_zoekpad, ongedekte_oorzaak
from .binding import verkeerd_gebonden
from .bronvermelding import bronlinks_van, bronnen_van, buiten_bronnensectie, zonder_bronnensectie, zonder_eigen_bronnen
from .budget import AFRONDEN, DEELANTWOORD, zonder_antwoord
from .citaties import citaties
from .dimensielabels import verkeerde_dimensielabels
from .genoemde_bronnen import genoemde_bronnen
from .getalnotatie import engels_gelezen, heeft_tabel, nl_notatie
from .grafiekvraag import ontbrekende_grafiek
from .grounding import afgeleide_verschillen, unverified
from .history import afgeronde_stappen, trim
from .instellingswissel import eerdere_instellingen, wisselcontext
from .interpretatie import interpretatie_bij, is_vervolgvraag
from .kenmerken import verkeerde_kenmerken
from .keuze import genegeerde_keuze
from .kpi_periode import verkeerde_kpi_periodes
from .kpi_scope import kpi_naast_filter
from .labels import onbekende_datasets, ongebruikte_bronnen, verkeerde_opleidingsvormen
from .loop import LoopResult, ToolCall, tool_loop
from .metatekst import metatekst, zonder_toolnamen
from .models import build_system
from .po_vraag import po_vraag
from .probleem import INGEHOUDEN, Probleem, controlenamen, hard, harde, meldingen, uitkomsten, veilig
from .publicatie import ANTWOORD, FIGUUR, log_publicatie
from .schrappen import zonder_ongedekte_zinnen
from .scopevraag import Kaart, scopevraag
from .selectie import data_keys, ontbrekende_instellingen, ontbrekende_schooljaren, onvolledige_selecties
from .session_data import record_data_key, record_rekenbewijs
from .stream import Emit
from .tekens import zonder_citaatkop
from .telling import met_telling
from .timebox import timebox
from .uitgangspunt import met_uitgangspunt
from .vaste_antwoorden import (
    SCOPE_UITLEG,
    SENTINEL_ANTWOORD,
    VO_ANTWOORD,
    WEIGER_ANTWOORD,
    scope_uitleg,
    sentinelvraag,
    weigering,
)
from .vo_school import vo_schoolvraag
from .zelfcorrectie import zonder_zelfcorrectie

logger = logging.getLogger(__name__)

# Een lege modelrespons zonder weigering of fout (CH-32): "stuur je vraag opnieuw" helpt dan niet.
LEEG_ANTWOORD = (
    "Het model gaf op deze vraag geen antwoord, ook geen weigering. Opnieuw sturen helpt meestal niet: "
    "formuleer de vraag anders, of stel een vraag over de open onderwijsdata."
)

_TOOL_LIMITS: dict[str, int] = {"search_catalog": SEARCH_CATALOG_LIMIT}
_MAX_TOOL_RESULT_CHARS = TOOL_RESULT_MAX_CHARS

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
        "of compute_kpi, selecteer het gevraagde schooljaar en de gevraagde instelling, of laat het weg. "
        "Dat geldt ook voor verschillen, percentages en aandelen: bereken die met compute_kpi of query_data, "
        "schrijf ze niet uit je hoofd op.\n"
        "Schrijf daarna een volledig nieuw antwoord voor de gebruiker, alsof het het eerste is: zonder kop of inleiding "
        "over de herziening, zonder te verwijzen naar een eerdere versie of naar deze controle, en zonder toolnamen."
    )


def _veilige_citaties(text: str, steps: list[tuple[str, str]]) -> list[dict]:
    """Citaties zijn geen controle: lukt het niet, dan gaat het antwoord zonder citaties (#392, #419)."""
    try:
        return citaties(text, steps)
    except Exception as exc:
        log_interne_fout(exc, "citaties")
        return []


def _veilige_bronnen(steps: list[tuple[str, str]]) -> list[str]:
    """Net als de citaties: lukt het niet, dan blijft de eigen Bronnen-sectie van het model staan (#416)."""
    try:
        return bronnen_van(steps)
    except Exception as exc:
        log_interne_fout(exc, "bronnen")
        return []


def _veilige_bronlinks(steps: list[tuple[str, str]]) -> dict[str, str]:
    """De links bij de bronnen (#621) zijn een extra: lukt het niet, dan staan de bronnen er als tekst."""
    try:
        return bronlinks_van(steps)
    except Exception as exc:
        log_interne_fout(exc, "bronlinks")
        return {}


_MAX_CLARIFY_RONDES = 1


async def _vaste_verduidelijking(kaart: Kaart, messages: list[dict], session: dict, emit: Emit) -> str:
    """De verduidelijkingskaart uit code (#348): dezelfde beurt als na clarify_scope, zonder modelronde.

    De vraag komt als assistentbeurt in het gesprek, zodat de keuze van de gebruiker erna haar context
    heeft; `_clarified` laat de chatroute de beurt niet als gewoon antwoord bewaren.
    """
    logger.info("SCOPEVRAAG  slot=%s  opties=%d", kaart.slot, len(kaart.opties))
    messages.append({"role": "assistant", "content": kaart.vraag})
    session["_clarified"] = True
    session["_last_turn_tool_calls"] = []
    await emit({"type": "clarification", "vraag": kaart.vraag, "opties": kaart.opties})
    return ""


def tools_for(session: dict) -> list[dict]:
    """De toolset van deze beurt. Na een beantwoorde scopevraag is clarify_scope er niet meer:
    nooit twee clarifies achter elkaar voor dezelfde vraag (#75), in code en niet alleen in de prompt."""
    if session.get("clarify_rondes", 0) < _MAX_CLARIFY_RONDES:
        return SCHEMAS
    return [t for t in SCHEMAS if t["function"]["name"] != TOOL_CLARIFY_SCOPE]


def _tekst(content) -> str:
    return (
        " ".join(b.get("text", "") for b in content if isinstance(b, dict))
        if isinstance(content, list)
        else str(content)
    )


def _laatste_vraag(messages: list[dict]) -> str:
    return _tekst(next((m["content"] for m in reversed(messages) if m.get("role") == "user"), ""))


def _vragen(messages: list[dict]) -> list[str]:
    return [_tekst(m["content"]) for m in messages if m.get("role") == "user"]


def _poortvraag(messages: list[dict], session: dict) -> str:
    """De tekst waarop de zoekpoort voor vo-context beslist (#597): de vraag van de gebruiker, bij een keuze op
    een verduidelijkingsvraag samen met de vraag die ze afbakent (een keuze als "2023/24" noemt zelf niets)."""
    return " ".join(_vragen(messages)[-(session.get("clarify_rondes", 0) + 1) :])


async def _vast_vooraf(vraag: str, messages: list[dict], session: dict) -> str | None:
    """Een vast antwoord uit code, vóór elke kaart en vóór het model; anders None.

    De betekenis van -1, een vo-school (#549), of een po/so/vo-vraag zonder ho-context (#647). Die laatste alleen
    bij een nieuwe vraag: een keuze op een verduidelijkingskaart beslist het model. Het register laadt bij een
    schoolnaam of een po/so/vo-vraag over het netwerk: niet op de event loop."""
    if vast := sentinelvraag(vraag) or await asyncio.to_thread(vo_schoolvraag, vraag):
        return vast
    if session.get("clarify_rondes", 0):
        return None
    vragen = _vragen(messages)
    return await asyncio.to_thread(po_vraag, vraag, vragen[-2] if len(vragen) > 1 else "")


def _met_kopregels(tekst: str, messages: list[dict], session: dict, steps: list[tuple[str, str]]) -> str:
    """Boven een antwoord met data, uit code: de lezing van een vaag thema (#514) en de Uitgangspunt-regel (#620).

    De lezing beslist op de modeltekst zelf: de regel mag een eigen "Ik ga uit van" van het model niet uit de eerste
    regels duwen. Op `messages`, niet op de ingekorte history: daar kunnen oude beurten uit zijn (#545). De regel
    kijkt naar de vraag met de gekozen verduidelijkingsopties: een gekozen instelling of jaar noemde de gebruiker."""
    zin = interpretatie_bij(tekst, _laatste_vraag(messages), steps, session, vervolg=is_vervolgvraag(messages))
    tekst = met_uitgangspunt(tekst, _poortvraag(messages, session), steps)
    return f"{zin}\n\n{tekst}" if zin else tekst


def _beurtcontext(vraag: str, settings: dict, turns: list[dict]) -> str:
    """Systeemtekst voor deze vraag: de taal van het antwoord (#326), de dataset-ID's die ze noemt (#334) en een
    instellingswissel in dit gesprek (#543)."""
    delen = (
        taalinstructie(vraag),
        genoemde_bronnen(vraag),
        wisselcontext(settings.get("instelling"), eerdere_instellingen(turns)),
    )
    return "\n\n".join(tekst for tekst in delen if tekst)


def _leestekst(antwoord: str) -> str:
    """De tekst waarop de taal van het antwoord beslist wordt: wat de gebruiker leest, zonder zelfcorrectie,
    eigen Bronnen-sectie, toolnamen en citaatkop (#326).

    Controles en weergave beslissen de taal op deze tekst. Op de ruwe modeltekst maakte een Nederlandse
    Bronnen-lijst een Engels antwoord Nederlands voor de controle, terwijl de gebruiker het Engels las."""
    zonder_correctie, _ = zonder_zelfcorrectie(antwoord)
    return zonder_citaatkop(zonder_toolnamen(zonder_bronnensectie(zonder_correctie)))


def _antwoordtaal(antwoord: str) -> Taal | None:
    return taal(_leestekst(antwoord))


def _lezingen(antwoord: str) -> list[str]:
    """Het antwoord met de getallen zoals de grondingscontrole ze moet lezen: zoals de gebruiker ze ziet.

    Een Nederlands antwoord krijgt na de controle de notatie (9.5% wordt 9,5%), dus toetst de controle die al.
    Een Engels antwoord houdt 12,345: dat is twaalfduizend, geen twaalf met decimalen. Bij een onduidelijke taal
    leest de gebruiker 12,345 misschien zo of zo: dan toetst de controle beide lezingen (#326)."""
    geschreven = _antwoordtaal(antwoord)
    lezingen = []
    if geschreven != "en":
        lezingen.append(nl_notatie(antwoord))
    if geschreven != "nl":
        lezingen.append(engels_gelezen(antwoord))
    return lezingen


def _getalcontrole(earlier: list[str], said_by_user: list[str]) -> Callable[[str, list[str]], list[Probleem]]:
    """De getalcontrole van een antwoord: per getal dat niet in de data staat één probleem.

    Wat de assistent al zei telt als bron: een vervolgvraag mag een getal uit een eerdere
    beurt herhalen. Wat de gebruiker zei niet (#211): dat is een bewering om te toetsen.
    """

    def ongedekt(n: str) -> Probleem:
        # In de notatie van het antwoord dat de gebruiker ziet (CH-11r).
        getal = nl_notatie(n)
        if unverified(n, [], said_by_user):
            (verzonnen,) = hard([Probleem(f"{getal} staat niet in de opgehaalde data.")])
            verzonnen.getal = n
            return verzonnen
        # Zacht: een correcte weerlegging citeert het getal van de gebruiker ook (#207, #214).
        return Probleem(
            f"{getal} staat alleen in een eerder bericht van de gebruiker, niet in de opgehaalde data.",
            "Dat is een bewering om te toetsen: haal het getal uit de data of laat het weg.",
        )

    def ongedekt_gelezen(gelezen: str, tool_results: list[str]) -> list[str]:
        # Het verschil van twee genoemde getallen uit de data is na te rekenen, niet verzonnen (CH-01).
        afgeleid = afgeleide_verschillen(gelezen, tool_results)
        return [n for n in unverified(gelezen, tool_results, earlier) if n not in afgeleid]

    def ongedekte_getallen(text: str, tool_results: list[str]) -> list[Probleem]:
        # Een getal dat in één lezing ongedekt is, telt: ook 3303 en 3.303 uit twee lezingen geven één melding.
        gevonden = [n for gelezen in _lezingen(text) for n in ongedekt_gelezen(gelezen, tool_results)]
        return list(dict.fromkeys(ongedekt(n) for n in gevonden))

    return ongedekte_getallen


def _antwoordcontrole(
    vraag: str,
    earlier: list[str],
    said_by_user: list[str],
    session: dict,
    getalcontrole: Callable[[str, list[str]], list[Probleem]] | None = None,
) -> Callable[[str, list[str]], list[str]]:
    """De controle van een antwoord tegen de data van dit gesprek, voor tool_loop."""
    getalcontrole = getalcontrole or _getalcontrole(earlier, said_by_user)

    def ongedekte_getallen(text: str, tool_results: list[str]) -> list[str]:
        return list(getalcontrole(text, tool_results))

    def check(text: str, tool_results: list[str]) -> list[str]:
        leestekst = _leestekst(text)
        # (controle, argumenten, hard): blijft een hard probleem na de herkansing, dan wordt het antwoord
        # ingehouden (#207).
        controles = [
            (ongedekte_getallen, (text, tool_results), False),
            (ontbrekende_schooljaren, (vraag, tool_results), True),
            (ontbrekende_instellingen, (vraag, tool_results), True),
            (onvolledige_selecties, (text, tool_results), True),
            (verkeerde_opleidingsvormen, (text, tool_results), False),
            (verkeerde_dimensielabels, (text, tool_results), False),
            (onbekende_datasets, (text,), False),
            (ongebruikte_bronnen, (text, tool_results), False),
            (verkeerd_gebonden, (text, tool_results), False),
            (verkeerde_kenmerken, (text, tool_results), True),
            (verkeerde_kpi_periodes, (text, tool_results), True),
            (kpi_naast_filter, (text, tool_results), False),
            (genegeerde_keuze, (session.get("clarify_keuzes", []), text), False),
            (onbeschikbaar_zonder_zoekpad, (vraag, text, tool_results), False),
            (ongedekte_oorzaak, (text, tool_results), False),
            (ontbrekende_grafiek, (vraag, text, tool_results, session.get("data_keys", [])), False),
            (metatekst, (text,), False),
            (verkeerde_antwoordtaal, (vraag, leestekst), False),
            # Op de tekst na de omzetting naar de je-vorm, zoals in _antwoordtekst (#536).
            (overgebleven_u_vorm, (leestekst, taal(leestekst)), False),
        ]
        problemen: list[str] = [
            p
            for controle, args, streng in controles
            for p in (hard(veilig(controle, *args)) if streng else veilig(controle, *args))
        ]
        # Per antwoord welke controle wat gaf: regressietestbaar en de afvuurfrequentie per controle (CH-01).
        per_controle = uitkomsten((c.__name__ for c, _, _ in controles), problemen)
        logger.info("CONTROLES  %s", "  ".join(f"{naam}={uitkomst}" for naam, uitkomst in per_controle.items()))
        return problemen

    return check


async def _intrekken(emit: Emit, problems: list[str]) -> None:
    # Welke controle afging, voor de afvuurfrequentie: elke herschrijving kost een modelronde (CH-01).
    logger.info("HERKANSING  controles=%s", controlenamen(problems))
    # De reden in gewone taal gaat mee, zodat de ingetrokken versie haar kan tonen.
    await emit({"type": "message_cancel", "reden": meldingen(problems)})
    await emit(
        {
            "type": "toast",
            "message": "Een controle vond iets om aan te passen; het antwoord wordt herschreven.",
            "level": "info",
        }
    )


async def _bewaar_stap(session: dict, emit: Emit, call: ToolCall, result: str, figure) -> None:
    record_data_key(session, result, {"name": call.name, "arguments": call.args})
    record_rekenbewijs(session, result, {"name": call.name, "arguments": call.args})
    if figure is not None:
        # De figuur gaat met haar rijen naar de client (export, #183): herkomst in het log (#169).
        log_publicatie(FIGUUR, [k for k in ((call.args or {}).get("data_key"),) if isinstance(k, str)])
    await _handle_figure(call.name, figure, session, emit)


async def _vroeg_einde(
    result: LoopResult, nieuw: list[dict], messages: list[dict], session: dict, emit: Emit
) -> str | None:
    """Het einde van een beurt zonder gewoon antwoord; None als er een gewoon antwoord is."""
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
        return await _handle_clarify_scope(result.halted_on, result.text, nieuw, messages, session, emit)
    if result.exhausted:
        text_content = zonder_antwoord(result.steps)
        # partial: the frontend offers 'Opnieuw met <ander model>' (#405). No data answer, so no sources (#416).
        await emit({"type": "message_end", "content": text_content, "actions": [], "bronnen": [], "partial": True})
        return text_content
    return None


def _antwoordtekst(result: LoopResult, antwoord: str, earlier: list[str], bronnen: list[str]) -> str:
    """De modeltekst in de vorm van de app: zonder eigen Bronnen als de app ze geeft, met Telling.

    Alleen een antwoord dat niet Engels is, krijgt de Nederlandse getalnotatie (#326) en de je-vorm (#536);
    de taal komt van `_antwoordtaal`, net als in de controle. Een eigen Bronnen-sectie die blijft, citeert
    brontitels: daar blijft een u-vorm staan."""
    tekst = zonder_citaatkop(zonder_toolnamen(zonder_eigen_bronnen(antwoord, bronnen)))
    if _antwoordtaal(antwoord) != "en":
        tekst = buiten_bronnensectie(nl_notatie(tekst, result.steps, earlier), in_je_vorm)
    return met_telling(tekst, result.tool_results)


def _vast_antwoord(result: LoopResult, antwoord: str, vraag: str, earlier: list[str], session: dict) -> str | None:
    """Een vast antwoord uit code in plaats van de modeltekst: de weigering of de scope-uitleg (BEV-12)."""
    return weigering(antwoord, result.tool_calls, eerder_gesprek=bool(earlier or session.get("data_keys"))) or (
        scope_uitleg(antwoord, result.tool_results, vraag)
    )


def _eindtekst(
    result: LoopResult, antwoord: str, vraag: str, earlier: list[str], session: dict, model: str, bronnen: list[str]
) -> str:
    """Het antwoord zoals de gebruiker het ziet: weigering, scope-uitleg of antwoord met Telling, of ingehouden.

    Een vast antwoord rust niet op de modeltekst: wat de controle daarin vond, houdt het niet tegen."""
    if vast := _vast_antwoord(result, antwoord, vraag, earlier, session):
        logger.info("VAST ANTWOORD  %s  controles=%s", tekst_kenmerk(vast), controlenamen(result.problems))
        return vast
    text_content = _antwoordtekst(result, antwoord, earlier, bronnen)
    if result.wrapped_up:
        text_content = f"{DEELANTWOORD}\n\n{text_content}"
    # Geen antwoordtekst op INFO: het log valt buiten "gesprek verwijderen" (#475).
    logger.info("FINALE ANTWOORD  %s", tekst_kenmerk(text_content))
    logger.debug("FINALE ANTWOORD TEKST  %r", text_content[:500])
    if not text_content.strip():
        # Vaak een contentfilter van de provider: opnieuw sturen geeft weer niets (CH-32).
        logger.warning("LEEG ANTWOORD  model=%s  finish_reason=%s", model, result.finish_reason)
        text_content = LEEG_ANTWOORD
    if result.problems:
        logger.warning(
            "CONTROLE niet in orde of niet gecontroleerd  model=%s  controles=%s",
            model,
            controlenamen(result.problems),
        )
        logger.debug("CONTROLE MELDINGEN  %s", result.problems)
    if harde(result.problems):
        logger.warning("ANTWOORD INGEHOUDEN  model=%s  %s", model, tekst_kenmerk(text_content))
        text_content = INGEHOUDEN
    return text_content


# Vaste antwoorden uit code: ze rusten niet op de data van de beurt, dus ook geen bronnen eronder.
# Een weigering komt nu alleen zonder tools (dus zonder bronnen), maar hoort er ook met tools bij.
_VASTE_ANTWOORDEN = frozenset({WEIGER_ANTWOORD, SCOPE_UITLEG})
_ZONDER_BRONNEN = frozenset({INGEHOUDEN, LEEG_ANTWOORD, *_VASTE_ANTWOORDEN})
# Teksten die helemaal uit code komen, zonder model als schrijver: de frontend noemt er geen model onder (#565).
# Code beslist op de eindtekst: een modelantwoord waar zo'n zin in staat, is niet gelijk en houdt het label.
_UIT_CODE = frozenset({SENTINEL_ANTWOORD, VO_ANTWOORD, *_VASTE_ANTWOORDEN})


def _vast(text_content: str) -> dict:
    """`{"vast": True}` voor een message_end met een tekst die helemaal uit code komt; anders leeg."""
    return {"vast": True} if text_content in _UIT_CODE else {}


def _slotbericht(
    text_content: str,
    result: LoopResult,
    herzien: list[str],
    truncated: bool,
    bronnen: list[str],
    bronlinks: dict[str, str] | None = None,
    manifest: dict | None = None,
    vervolgvragen: list[str] | None = None,
) -> dict:
    """Het message_end-event van een gewoon antwoord, met alleen de velden die er zijn.

    `bronnen` staat er altijd, ook leeg: zo weet de frontend dat het een nieuw antwoord is (#416).
    `bronlinks` (bronregel → bronpagina, #621) alleen als er links zijn, en nooit onder een vast antwoord."""
    vast_zonder_bronnen = text_content in _ZONDER_BRONNEN
    return {
        "type": "message_end",
        "content": text_content,
        "actions": [],
        "bronnen": [] if vast_zonder_bronnen else bronnen,
        **({"bronlinks": bronlinks} if bronlinks and not vast_zonder_bronnen else {}),
        **({"manifest": manifest} if manifest else {}),
        **({"citaties": cites} if (cites := _veilige_citaties(text_content, result.steps)) else {}),
        **({"tussentekst": herzien} if herzien else {}),
        **({"truncated": True} if truncated else {}),
        **({"partial": True} if result.wrapped_up else {}),
        # Een vast antwoord rust niet op de modeltekst: de meldingen over die tekst horen er niet onder.
        **(
            {"controle": meldingen(result.problems)}
            if result.problems and text_content not in _VASTE_ANTWOORDEN
            else {}
        ),
        **({"vervolgvragen": vervolgvragen} if vervolgvragen else {}),
        **_vast(text_content),
    }


def _log_export(text_content: str, steps: list[tuple[str, str]]) -> None:
    """Per antwoord: staat er een tabel in, en welke stap leverde een exporteerbare tabel (#544)?

    De CSV-knop onder een tabelantwoord ontbrak wisselend. Alleen tellingen en toolnamen: zo is per beurt
    te meten hoe vaak een antwoord met een tabel geen tabel-key kreeg, en via welke tools het dan liep.
    Kreeg een tabelantwoord geen key, dan zegt `reden` waarom dat een keuze van de code is (#605)."""
    tabellen = [tool for tool, result in steps if export_key(tool, result)]
    tabel = heeft_tabel(text_content)
    logger.info(
        "EXPORT  tabel_in_antwoord=%s  tabellen=%d  tabelstap=%s  tools=%s  reden=%s",
        tabel,
        len(tabellen),
        tabellen[-1] if tabellen else "-",
        ",".join(dict.fromkeys(tool for tool, _ in steps)) or "-",
        geen_export_reden(steps) if tabel and not tabellen else "-",
    )


async def _vervolgvragen(result: LoopResult, text_content: str, vraag: str, session: dict) -> list[str]:
    """Vervolgvragen onder elk gewoon antwoord met data (#364): code biedt ze aan, geen keuze van het model (#539).
    De eerste twee uit de vraag zelf (zelfde maat, ander schooljaar, ontwikkeling; #615), de rest uit de dataset.

    Een weigering, een ingehouden of leeg antwoord, een deelantwoord en een afgekapt antwoord krijgen er geen.
    Wat dit gesprek al aanbood, onthoudt de sessie: een nieuw gesprek begint met een lege sessie."""
    if result.wrapped_up or result.finish_reason == "length" or text_content in _ZONDER_BRONNEN:
        return []
    getoond = session.setdefault("vervolgvragen_getoond", [])
    datasets: list[str] = []
    gekozen: list[str] = []
    try:
        datasets = vervolgvragen.datasets_van(result.steps)
        # Een dataset die nog niet getoetst is, kost een paar zoekacties in de catalogus: niet op de event loop.
        gekozen = await asyncio.to_thread(vervolgvragen.kies, result.steps, vraag, getoond, tekst=text_content)
    except Exception as exc:
        # Vervolgvragen zijn een extra: lukt het niet, dan gaat het antwoord zonder (zoals bij citaties).
        log_interne_fout(exc, "vervolgvragen")
    getoond.extend(gekozen)
    # Bij elk gewoon antwoord, ook zonder aanbod: zo is te tellen hoe vaak er knoppen komen, en (met datasets=) hoe
    # vaak een antwoord met data er geen kreeg. Alleen aantallen: het log houdt het bij tellingen, ook voor catalogustekst.
    logger.info("VERVOLGVRAGEN  aangeboden=%d  datasets=%d", len(gekozen), len(datasets))
    return gekozen


async def run(
    messages: list[dict],
    session: dict,
    emit: Emit,
    stop_event: asyncio.Event | None = None,
    model: str | None = None,
) -> str:
    settings: dict = session.get("chat_settings") or {}
    chosen_model = model or MODEL

    last_user_msg = _laatste_vraag(messages)
    logger.info("RUN START  model=%s  %s", chosen_model, tekst_kenmerk(last_user_msg, "vraag_"))
    logger.debug("RUN VRAAG  %r", last_user_msg[:200])

    # Wat code zelf beantwoordt (-1, een vo-school, een po/so/vo-vraag), krijgt geen kaart en geen model.
    if vast := await _vast_vooraf(last_user_msg, messages, session):
        await emit({"type": "message_start"})
        await emit({"type": "message_end", "content": vast, "actions": [], "bronnen": [], **_vast(vast)})
        return vast

    # Een open slot (plaats of instelling, maat) krijgt een vaste kaart uit code, vóór het model (#348).
    # Het register en de catalogus laden over het netwerk: niet op de event loop.
    if session.get("clarify_rondes", 0) < _MAX_CLARIFY_RONDES:
        kaart = await asyncio.to_thread(scopevraag, last_user_msg, settings)
        if kaart is not None:
            return await _vaste_verduidelijking(kaart, messages, session, emit)

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

    # Vóór de loop: dan maakt het correctiebericht met de verdachte getallen ze geen bron.
    earlier = [str(m.get("content") or "") for m in history if m.get("role") == "assistant"]
    said_by_user = [str(m.get("content") or "") for m in history if m.get("role") == "user"]

    # Het profiel kan de instellingenlijst laden (DUO, #448): niet op de event loop.
    beurt = _beurtcontext(last_user_msg, settings, session.get("turns") or [])
    system = await asyncio.to_thread(build_system, settings, beurt=beurt)
    stop = stop_event or asyncio.Event()
    # De tools van deze beurt zien de vraag van de gebruiker: de zoekpoort voor vo-context beslist erop (#597).
    getalcontrole = _getalcontrole(earlier, said_by_user)
    check = _antwoordcontrole(last_user_msg, earlier, said_by_user, session, getalcontrole)
    with ho_markers.beurtvraag(_poortvraag(messages, session)):
        async with timebox(emit, stop, RUN_SLOW_S, RUN_TIMEOUT_S) as box:
            try:
                async with asyncio.timeout(box.afbreken_s):
                    result = await tool_loop(
                        history,
                        model=chosen_model,
                        tools=tools_for(session),
                        emit=emit,
                        stop_event=stop,
                        system=system,
                        stream_text=True,
                        on_llm_start=lambda: emit({"type": "message_start"}),
                        on_tool_result=partial(_bewaar_stap, session, emit),
                        tool_limits=_TOOL_LIMITS,
                        halt_on=frozenset({TOOL_CLARIFY_SCOPE}),
                        max_iterations=MAX_TOOL_ITERATIONS,
                        max_result_chars=_MAX_TOOL_RESULT_CHARS,
                        check=check,
                        correction=_correction,
                        on_correction=partial(_intrekken, emit),
                        wrap_up=AFRONDEN,
                        recept_van=recepten.van_session(session),
                    )
            except TimeoutError:
                # Vastgelopen aanroep die het stopsignaal niet zag.
                result = LoopResult(aborted="tools")
            except Exception:
                # Bijvoorbeeld een rate limit na alle pogingen: wat al opgehaald is, blijft in het
                # gesprek, zodat een nieuwe poging erop voortbouwt (#431).
                messages.extend(afgeronde_stappen(history[initial_history_len:]))
                raise
    if box.verlopen:
        logger.warning("RUN TIMEOUT na %ss  model=%s", RUN_TIMEOUT_S, chosen_model)
        await emit(box.melding())

    if (einde := await _vroeg_einde(result, history[initial_history_len:], messages, session, emit)) is not None:
        return einde

    # Blijven alleen zinnen met een ongedekt getal over, dan vervalt alleen die zin, niet het antwoord (#619).
    result = zonder_ongedekte_zinnen(result, check, getalcontrole)
    # Wat het model onderweg herzag, gaat naar de redeneerkaart; het antwoord zelf herziet niets (#412).
    antwoord, herzien = zonder_zelfcorrectie(result.text)
    if herzien:
        logger.info("ZELFCORRECTIE naar redeneerkaart  herzien=%d", len(herzien))
        logger.debug("ZELFCORRECTIE TEKST  %r", herzien)
    bronnen = _veilige_bronnen(result.steps)
    bronlinks = _veilige_bronlinks(result.steps) if bronnen else {}
    text_content = _eindtekst(result, antwoord, last_user_msg, earlier, session, chosen_model, bronnen)
    if bronnen and text_content not in _ZONDER_BRONNEN:
        # Vóór het eerste getal: op welke lezing het antwoord rust (#514) en wat de selectie afbakent (#620).
        text_content = _met_kopregels(text_content, messages, session, result.steps)
    session["_last_turn_tool_calls"] = result.tool_calls
    _log_export(text_content, result.steps)
    truncated = result.finish_reason == "length"
    if truncated:
        logger.warning("ANTWOORD AFGEKAPT op outputlimiet  model=%s", chosen_model)
    # Herkomst van dit antwoord: model, prompt-, catalogus- en dataversie (#345).
    mani = manifest.bouw(chosen_model, data_keys(result.tool_results), model_versie=result.model_versie)
    gekozen = await _vervolgvragen(result, text_content, last_user_msg, session)
    if text_content not in _ZONDER_BRONNEN:
        log_publicatie(ANTWOORD, data_keys(result.tool_results), mani)
    await emit(
        _slotbericht(text_content, result, herzien, truncated, bronnen, bronlinks, manifest=mani, vervolgvragen=gekozen)
    )
    return text_content
