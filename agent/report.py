"""Report generation orchestrator.

Produces a compact, professional report from the loaded session data:
the research question front and centre, chosen definitions (what the
report does and does not answer), 1-2 visualisations with an explanation,
and a conclusion. Unlike the dashboard, the report stays focused on the
user's question instead of exploring the full potential of the data.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

import plotly.io as pio

from agent import manifest
from agent.aanspreekvorm import in_je_vorm
from agent.afkapping import afkappingsregels
from agent.antwoordtaal import taal
from agent.dashboard import (
    _build_recipe,
    _extract_json_object,
    _sources_from_recipe,
    build_dataset_context,
    herstel_data,
)
from agent.figuurbron import figuurbron
from agent.getalnotatie import nl_notatie
from agent.loop import ToolCall, tool_loop
from agent.probleem import controlenamen, harde, meldingen
from agent.publicatie import RAPPORT, log_publicatie
from agent.recepten import van_session
from agent.report_bronnen import gebruikte_datasets
from agent.report_checks import report_problems
from agent.report_definities import definities_uit_bron
from agent.report_periode import bijgesneden, gevraagd_bereik
from agent.report_titel import rapporttitel
from agent.selectie import stapkeys
from agent.session_data import rekenbewijs
from agent.stream import Emit
from core.config import MODEL
from core.errors import Gebruikersfout
from core.logging_util import tekst_kenmerk
from tools.schemas import TOOL_CREATE_CHOROPLETH_MAP, TOOL_CREATE_PLOT, TOOL_QUERY_DATA, TOOL_SCHEMAS

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "report.md"

# Met de kaarttool: het rapport van een kaartvraag toont de kaart (#648).
_REPORT_TOOLS = [
    s for s in TOOL_SCHEMAS if s["function"]["name"] in (TOOL_QUERY_DATA, TOOL_CREATE_PLOT, TOOL_CREATE_CHOROPLETH_MAP)
]

logger = logging.getLogger(__name__)

_MAX_TOOL_ITERATIONS = 15
_MAX_TOOL_RESULT_CHARS = 8000
_MAX_VISUALISATIES = 2

_DUTCH_MONTHS = [
    "januari",
    "februari",
    "maart",
    "april",
    "mei",
    "juni",
    "juli",
    "augustus",
    "september",
    "oktober",
    "november",
    "december",
]


def _nl_datum(today: date | None = None) -> str:
    today = today or date.today()
    return f"{today.day} {_DUTCH_MONTHS[today.month - 1]} {today.year}"


class RapportGeannuleerd(Exception):
    """De gebruiker stopte de rapportgeneratie: er komt geen (half) rapport (#339)."""


# Vaste tekst bij een geweigerd rapport (#515): geen getallen of controlenamen, wel een vervolgstap.
RAPPORT_GEWEIGERD = (
    "De cijfers in het rapport klopten niet met de laatste analyse, daarom heb ik het niet getoond. "
    "Probeer het opnieuw, of stel je vraag opnieuw."
)


class RapportGeweigerd(Gebruikersfout):
    """De controle hield het rapport tegen (#207); wat ze vond, staat alleen in het log (#515)."""

    def __init__(self) -> None:
        super().__init__(RAPPORT_GEWEIGERD)


@dataclass
class ReportSpec:
    title: str = ""
    onderzoeksvraag: str = ""
    definities: list[dict] = field(default_factory=list)
    beantwoordt: list[str] = field(default_factory=list)
    beantwoordt_niet: list[str] = field(default_factory=list)
    visualisaties: list[dict] = field(default_factory=list)
    conclusie: str = ""
    bronnen: list[str] = field(default_factory=list)
    auteur: str = ""
    datum: str = ""
    # Herkomst van het rapport: model, prompt-, catalogus- en dataversie (#345). Reist mee
    # in het workbook en de export; geen inhoud, geen persoonsgegevens.
    manifest: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _describe_call(call: dict) -> str:
    return f"{call['name']} {json.dumps(call['arguments'], ensure_ascii=False)}"


# Per eerdere berekening in de rapportprompt; de controle ziet het hele resultaat (#397).
_MAX_BEWIJS_TEKENS = 1500


def _describe_herkomst(herkomst: list[dict]) -> str:
    """The tool calls that produced a dataset, so the report reuses that selection (#174)."""
    if not herkomst:
        return "onbekend (niet vastgelegd in dit gesprek)"
    return " → ".join(_describe_call(call) for call in herkomst)


def _kaarten_in_gesprek(session: dict) -> dict[str, dict]:
    """Per data_key de laatste kaart die het gesprek ervan tekende (#648).

    De herkomst noemt alleen de aanroepen die de data maakten, niet de kaart erop; zonder deze regel weet het
    rapport niet dat er een kaart was, of met welke kolommen. Een onleesbare aanroep slaat het over, en ook een
    aanroep die geen kaart opleverde: de beurt bewaart wat het model vroeg, niet wat lukte.
    """
    kaarten: dict[str, dict] = {}
    for turn in session.get("turns") or []:
        getekend = _getekende_kaarten(turn)
        for call in turn.get("tool_calls") or []:
            if call.get("name") != TOOL_CREATE_CHOROPLETH_MAP:
                continue
            try:
                args = json.loads(call.get("arguments") or "")
            except (TypeError, ValueError):
                continue
            if not isinstance(args, dict) or not isinstance(args.get("data_key"), str):
                continue
            if (args.get("location_col"), args.get("value_col")) in getekend:
                kaarten[args["data_key"]] = args
    return kaarten


def _getekende_kaarten(turn: dict) -> set[tuple]:
    """(location_col, value_col) van elke kaart die deze beurt tekende, uit de layout.meta van haar figuren."""
    getekend: set[tuple] = set()
    for figuur in turn.get("figures") or []:
        meta = getattr(getattr(figuur, "layout", None), "meta", None)
        if isinstance(meta, dict) and meta.get("type") == "choropleth":
            getekend.add((meta.get("location_col"), meta.get("value_col")))
    return getekend


# Wat de kaartregel van een gesprekskaart noemt. Niet de titel (tekst van het model) en niet `data` (rijen buiten
# de store): het rapport zou ze herhalen, en via zijn toolresultaat telden ze dan toch als bewijs (#211).
_KAARTREGEL_ARGUMENTEN = ("data_key", "location_col", "value_col", "level")


def _describe_kaart(kaart: dict | None) -> str:
    if not kaart:
        return ""
    argumenten = {k: kaart[k] for k in _KAARTREGEL_ARGUMENTEN if k in kaart}
    return f"\n- Kaart in het gesprek: {_describe_call({'name': TOOL_CREATE_CHOROPLETH_MAP, 'arguments': argumenten})}"


def _build_system_prompt(context: dict) -> str:
    """Build the system prompt with injected dataset context.

    `context["kaarten"]` (per data_key) is for the prompt only: `generate` keeps it out of the evidence.
    """
    base = _PROMPT_PATH.read_text() if _PROMPT_PATH.exists() else ""

    kaarten = context.get("kaarten") or {}
    dataset_blocks: list[str] = []
    for ds in context.get("datasets", []):
        cols = "\n".join(f"  - {c['naam']} ({c['type']}): {', '.join(c['voorbeelden'])}" for c in ds["columns"])
        dataset_blocks.append(
            f"### {ds['data_key']}\n- Rijen: {ds['row_count']}\n"
            f"- Herkomst: {_describe_herkomst(ds.get('herkomst') or [])}{_describe_kaart(kaarten.get(ds['data_key']))}\n"
            f"- Kolommen:\n{cols}"
        )

    datasets_section = "\n\n".join(dataset_blocks) if dataset_blocks else "Geen datasets geladen."

    instelling = context.get("instelling", "")
    topic = context.get("topic", "")
    berekeningen = "\n".join(
        f"- {b['tool']}({json.dumps(b['argumenten'], ensure_ascii=False, default=str)}): "
        f"{b['resultaat'][:_MAX_BEWIJS_TEKENS]}"
        for b in context.get("berekeningen") or []
    )
    berekeningen_section = (
        f"""

## Eerder berekend in het gesprek

Deze uitkomsten kwamen uit de data; je mag ze in het rapport gebruiken, met dezelfde selectie.

{berekeningen}
"""
        if berekeningen
        else ""
    )

    injected = f"""

## Beschikbare datasets in deze sessie

{datasets_section}
{berekeningen_section}

## Gebruikerscontext
- Instelling: {instelling or "niet opgegeven"}
- Onderwerp (onderzoeksvraag): {topic or "niet opgegeven"}
"""
    return base + injected


async def generate(
    session: dict,
    emit: Emit,
    model: str | None = None,
    stop_event: asyncio.Event | None = None,
    author: str | None = None,
) -> ReportSpec:
    """Generate a report from the loaded session data.

    The report must agree with its own data (#175). If it does not, the model
    gets one correction; a report that still contradicts its data is refused.
    """
    await herstel_data(session, emit)
    context = build_dataset_context(session)

    if not context["datasets"]:
        raise Gebruikersfout("Geen datasets geladen. Stel eerst een vraag waarvoor data wordt opgehaald.")

    # Een KPI of afgeleid getal uit het gesprek is bewijs, alleen als toolresultaat (#397).
    bewijs = rekenbewijs(session)
    context["berekeningen"] = bewijs
    # De kaarten uit het gesprek zijn modelaanroepen, geen data: alleen in de prompt, niet in `context`, dat de
    # controles als bewijs lezen (#211, #648).
    prompt_context = {**context, "kaarten": _kaarten_in_gesprek(session)}
    messages: list[dict] = [
        {"role": "system", "content": _build_system_prompt(prompt_context)},
        {"role": "user", "content": "Stel een professioneel rapport op dat antwoord geeft op de onderzoeksvraag."},
    ]
    figures: list[str] = []
    # Per figuur de bronregel eronder, uit de key die de grafiek tekende (#569).
    figuurbronnen: list[dict | None] = []
    # De keys die de rapportrun las: haar bevragingen en de grafieken die in het rapport komen (#738).
    gelezen: list = []
    dataset_context = json.dumps(context, default=str)

    async def keep_figure(call: ToolCall, result: str, figure) -> None:
        _log_tool_call(call.name, call.args, result)
        gelezen.extend(stapkeys(result))
        if figure is not None and len(figures) < _MAX_VISUALISATIES:
            figures.append(pio.to_json(figure))
            data_key = (call.args or {}).get("data_key")
            figuurbronnen.append(figuurbron(data_key))
            gelezen.append(data_key)

    def check(text: str, tool_results: list[str]) -> list[str]:
        # De controles oordelen over wat het model schreef, niet over het voorbehoud uit code (#578).
        spec = _parse_spec_from_response(text, figures, context, author, figuurbronnen, met_voorbehoud=False)
        return report_problems(spec, figures, [*tool_results, dataset_context, *(b["resultaat"] for b in bewijs)])

    result = await tool_loop(
        messages,
        model=model or MODEL,
        tools=_REPORT_TOOLS,
        emit=emit,
        stop_event=stop_event,
        max_iterations=_MAX_TOOL_ITERATIONS,
        max_result_chars=_MAX_TOOL_RESULT_CHARS,
        on_tool_result=keep_figure,
        check=check,
        correction=_correction,
        keep_partial=lambda: bool(figures),
        recept_van=van_session(session),
    )
    if result.aborted:
        raise RapportGeannuleerd
    if result.partial_error:
        await emit(
            {
                "type": "toast",
                "message": "Rapport deels gegenereerd (fout: rate limit). Figuren tot nu toe bewaard.",
                "level": "warning",
            }
        )
    # Alleen een hard probleem houdt het rapport tegen; een zacht wordt een waarschuwing (#207).
    if harde(result.problems):
        logger.error("RAPPORT GEWEIGERD: controles=%s", controlenamen(result.problems))
        logger.debug("RAPPORT MELDINGEN  %s", result.problems)
        raise RapportGeweigerd
    if result.problems:
        logger.warning("RAPPORT MET WAARSCHUWING: controles=%s", controlenamen(result.problems))
        logger.debug("RAPPORT MELDINGEN  %s", result.problems)
        await emit({"type": "toast", "message": "Let op: " + " ".join(meldingen(result.problems)), "level": "warning"})
    # Bronnen, definities, voorbehoud en dataversie van wat het rapport gebruikte, niet van het hele gesprek (#738).
    gebruikt = {**context, "datasets": gebruikte_datasets(context["datasets"], gelezen, bewijs, result.text)}
    spec = _parse_spec_from_response(result.text, figures, gebruikt, author, figuurbronnen)
    keys = [ds["data_key"] for ds in gebruikt["datasets"] if ds.get("data_key")]
    spec.manifest = manifest.bouw(model or MODEL, keys, model_versie=getattr(result, "model_versie", None))
    log_publicatie(RAPPORT, keys, spec.manifest)
    return spec


def _correction(problems: list[str]) -> str:
    return (
        "Je rapport klopt niet met de data die je hebt opgehaald:\n"
        + "\n".join(f"- {p}" for p in problems)
        + "\nHerstel dit: gebruik alleen getallen uit de toolresultaten en beschrijf wat de "
        "grafieken tonen. Geef daarna opnieuw het volledige JSON-blok."
    )


def _log_tool_call(name: str, args: dict | None, result: str) -> None:
    """Log what the report fetched: a misfilter must be traceable afterwards (#174).

    Argument values and tool messages carry text from the question, so INFO gets only the argument
    names, lengths and hashes; the arguments themselves go to DEBUG (#475).
    """
    try:
        parsed = json.loads(result)
        outcome = f"totaal_rijen={parsed.get('totaal_rijen')}" if isinstance(parsed, dict) else "ok"
    except (TypeError, ValueError):
        outcome = tekst_kenmerk(result, "melding_")
    argumenten = json.dumps(args, ensure_ascii=False)
    namen = ",".join(sorted(args or {}))
    logger.info("RAPPORT TOOL %s argumenten=%s %s %s", name, namen, tekst_kenmerk(argumenten, "args_"), outcome)
    logger.debug("RAPPORT TOOL %s args=%s", name, argumenten)


def _parse_spec_from_response(
    response: str,
    figures_json: list[str],
    context: dict,
    author: str | None = None,
    figuurbronnen: list[dict | None] | None = None,
    *,
    met_voorbehoud: bool = True,
) -> ReportSpec:
    """Parse the LLM response into a ReportSpec.

    `figuurbronnen` is per figuur de bronregel uit code (#569), in dezelfde volgorde als
    `figures_json`; een figuur zonder regel krijgt `bron: None`. `met_voorbehoud` zet per
    afgekapte laadkey het voorbehoud uit code vooraan in `beantwoordt_niet` (#578); de controle
    in `generate` zet het uit.
    """
    spec_data: dict = {}
    with contextlib.suppress(json.JSONDecodeError, ValueError):
        spec_data = _extract_json_object(response)

    recipe = _build_recipe(context.get("datasets", []))
    topic = context.get("topic", "Rapport")

    bronnen = _sources_from_recipe(recipe)

    onderzoeksvraag = (spec_data.get("onderzoeksvraag") or "").strip() or topic
    # De vraag van de gebruiker, niet een titel van het model: elke run gaf een andere (#416).
    title = rapporttitel(topic, context.get("instelling"))

    vis_meta = spec_data.get("visualisaties") or []
    visualisaties: list[dict] = []
    for idx, figure_json in enumerate(figures_json):
        meta = vis_meta[idx] if idx < len(vis_meta) else {}
        titel = in_je_vorm((meta.get("titel") or "").strip())
        # De grafiek toont de periode die erboven staat, niet de volle dataset (#385).
        bereik = gevraagd_bereik(titel, title, onderzoeksvraag)
        visualisaties.append(
            {
                "titel": titel or f"Visualisatie {idx + 1}",
                "toelichting": in_je_vorm((meta.get("toelichting") or "").strip()),
                "figure_json": bijgesneden(figure_json, bereik) if bereik else figure_json,
                "bron": figuurbronnen[idx] if figuurbronnen and idx < len(figuurbronnen) else None,
            }
        )

    # De modeltekst in de je-vorm (#536); de onderzoeksvraag en de titel citeren de gebruiker en blijven.
    beantwoordt = _lijst_in_je_vorm(spec_data.get("beantwoordt") or [])
    beantwoordt_niet = _lijst_in_je_vorm(spec_data.get("beantwoordt_niet") or [])
    conclusie = _conclusie((spec_data.get("conclusie") or "").strip())
    # Wat het rapport toont, om te bepalen welke brondefinities erbij horen (#422).
    rapporttekst = "\n".join(
        [
            title,
            onderzoeksvraag,
            conclusie,
            *map(str, beantwoordt),
            *map(str, beantwoordt_niet),
            *(f"{v['titel']} {v['toelichting']} {v['figure_json']}" for v in visualisaties),
        ]
    )
    # Na de rapporttekst: het voorbehoud is geen modeltekst en haalt geen definitie binnen.
    if met_voorbehoud:
        beantwoordt_niet = _voorbehoud_vooraan(
            afkappingsregels(context.get("datasets", []), "rapport"), beantwoordt_niet
        )

    return ReportSpec(
        title=title,
        onderzoeksvraag=onderzoeksvraag,
        definities=definities_uit_bron(context.get("datasets", []), rapporttekst),
        beantwoordt=beantwoordt,
        beantwoordt_niet=beantwoordt_niet,
        conclusie=conclusie,
        visualisaties=visualisaties,
        bronnen=bronnen,
        auteur=(author or "").strip(),
        datum=_nl_datum(),
    )


def _conclusie(tekst: str) -> str:
    """De conclusie in de vorm van de app: je-vorm, en getallen als in tekst en grafiek (248.930, BEV-10).

    Dezelfde taalregel als het chatantwoord (`run._antwoordtekst`, #326): een Engelse conclusie houdt de
    notatie van het model. Zonder de stappen van de run: codes en jaren herkent `nl_notatie` aan hun vorm
    en het woord ervoor; de grondingscontrole leest 248930 en 248.930 als hetzelfde getal."""
    return in_je_vorm(tekst if taal(tekst) == "en" else nl_notatie(tekst))


def _voorbehoud_vooraan(regels: list[str], items: list[str] | str) -> list[str]:
    """De regels uit code vóór wat het model als niet beantwoord noemde, altijd als lijst (#583).

    Het model geeft `beantwoordt_niet` meestal als lijst, maar mag één string teruggeven: die telt als
    één item. Ook zonder regels komt die als lijst terug — `ReportSpec.beantwoordt_niet` is een lijst en
    de export mapt erover."""
    return [*regels, *(items if isinstance(items, list) else [items])]


def _lijst_in_je_vorm(items):
    """Een lijst uit de JSON van het model met elke tekst in de je-vorm; wat geen tekst of lijst is, blijft."""
    if not isinstance(items, list):
        return items
    return [in_je_vorm(item) if isinstance(item, str) else item for item in items]
