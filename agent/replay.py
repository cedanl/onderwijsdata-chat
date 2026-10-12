"""De twee herhaalmodi van een dashboard: ververs en reproduceer (#346).

- ververs: voer de dataoproepen opnieuw uit tegen de bron en maak de figuren
  opnieuw; de aanroeper vergelijkt met het bewaarde dashboard en toont het
  verschil (agent/figuurverschil.py).
- reproduceer: maak de figuren opnieuw uit de data die al in de store staat,
  zonder netwerk. Dezelfde data en hetzelfde recept geven byte-identieke
  figuren terug.
"""

import hashlib
import json
import logging
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

import plotly.io as pio

from tools import dispatch, store
from tools.catalog import catalogus_laatste_update
from tools.cbs import bron_laatste_update
from tools.schemas import (
    TOOL_CREATE_PLOT,
    TOOL_GET_CBS_DATA,
    TOOL_GET_DUO_DATA,
    TOOL_GET_RIO_DATA,
    TOOL_QUERY_DATA,
)

logger = logging.getLogger(__name__)

MODE_VERVERS = "ververs"
MODE_REPRODUCEER = "reproduceer"
MODES = frozenset({MODE_VERVERS, MODE_REPRODUCEER})


def geldige_modus(mode: object) -> bool:
    """Of een ruwe clientwaarde een bekende modus is; een lijst of dict is dat nooit.

    `in MODES` hasht de waarde en gooit bij een onhashbare waarde een TypeError.
    """
    return isinstance(mode, str) and mode in MODES


# De enige tools die een recept mag herhalen: de load-tools waaruit _build_recipe het
# samenstelt. Het recept komt van de client, en zonder deze grens kon een ingelogde
# client er elke tool mee aanroepen, run_analysis inbegrepen (#505). De scopecontrole
# (#355) zit in de tools zelf en geldt zo ook voor dit pad.
REPLAYABLE_TOOLS = frozenset({TOOL_GET_DUO_DATA, TOOL_GET_CBS_DATA, TOOL_GET_RIO_DATA})


def replay_data_calls(calls: list[dict]) -> list[dict]:
    """Re-execute data-fetching calls. Returns per-call status.

    De fouttekst per mislukte call is een vaste, veilige melding: de ruwe uitzondering
    (met paden of parser-details) gaat alleen naar het log (#503).
    """
    results: list[dict] = []
    for tc in calls:
        name = tc.get("name")
        if name not in REPLAYABLE_TOOLS:
            logger.warning("Replay geweigerd: tool %r staat niet in het recept-allowlist", name)
            results.append(
                {
                    "name": name,
                    "arguments": tc.get("arguments"),
                    "success": False,
                    "error": "tool niet toegestaan bij verversen",
                }
            )
            continue
        try:
            args = json.loads(tc.get("arguments") or "{}")
            output, _ = dispatch(name, args)
            results.append({"name": name, "arguments": tc.get("arguments"), "success": True, "output": output})
        except Exception:
            logger.warning("Herladen van %s mislukt", name, exc_info=True)
            results.append(
                {"name": name, "arguments": tc.get("arguments"), "success": False, "error": "herladen mislukt"}
            )
    return results


class Reden(StrEnum):
    """Waarom een figuurrecept geen figuur gaf (#523): een vaste zin, nooit de ruwe fout (#503)."""

    DATA_ONTBREEKT = "data ontbreekt"  # de key staat niet (meer) in de store
    GEEN_DATABRON = "geen databron"  # het recept noemt geen data_key
    QUERY_MISLUKT = "query mislukt"  # fouttekst, geen JSON of een uitzondering
    GEEN_RIJEN = "geen rijen"
    GEEN_GRAFIEK = "grafiek niet gemaakt"  # create_plot gaf geen figuur, bv. bij één datapunt


@dataclass(frozen=True)
class Figuuruitkomst:
    """Eén figuurrecept na uitvoeren: de figuur-JSON, of de reden waarom die er niet is."""

    recept_id: str
    naam: str  # zoals de grafiek in een melding heet: 'titel', anders "Grafiek N"
    figuur_json: str | None = None
    reden: Reden | None = None


def recept_ids(figure_recipes: list[dict]) -> list[str]:
    """Per figuurrecept een stabiele sleutel: een digest van de canonieke JSON van query en plot (#523).

    Afgeleid, niet opgeslagen: ook oude dashboards hebben er zo een. Identieke
    dubbelen krijgen een volgnummer, zodat elke sleutel bij precies één recept hoort.
    """
    gezien: Counter[str] = Counter()
    ids: list[str] = []
    for fr in figure_recipes:
        digest = _recept_digest(fr)
        gezien[digest] += 1
        ids.append(digest if gezien[digest] == 1 else f"{digest}-{gezien[digest]}")
    return ids


def _recept_digest(fr: object) -> str:
    deel = {k: fr.get(k) for k in ("query", "plot")} if isinstance(fr, dict) else {"recept": fr}
    canoniek = json.dumps(deel, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(canoniek.encode()).hexdigest()[:16]


def figuur_uitkomsten(figure_recipes: list[dict]) -> list[Figuuruitkomst]:
    """Voer elk figuurrecept uit tegen de store; één uitkomst per recept, in receptvolgorde (#523).

    Een mislukt recept valt dus niet weg: wie bewaarde en nieuwe figuren vergelijkt,
    koppelt ze via het recept, niet via de positie in een lijst van geslaagde figuren.
    """
    uitkomsten: list[Figuuruitkomst] = []
    for index, (recept_id, fr) in enumerate(zip(recept_ids(figure_recipes), figure_recipes, strict=True)):
        uitkomst = _figuur(fr)
        naam = _recept_naam(fr, index)
        if isinstance(uitkomst, Reden):  # eerst: een Reden is ook een str
            uitkomsten.append(Figuuruitkomst(recept_id, naam, reden=uitkomst))
        else:
            uitkomsten.append(Figuuruitkomst(recept_id, naam, figuur_json=uitkomst))
    return uitkomsten


def _recept_naam(fr: object, index: int) -> str:
    plot = fr.get("plot") if isinstance(fr, dict) else None
    titel = plot.get("title") if isinstance(plot, dict) else None
    return f"'{titel}'" if isinstance(titel, str) and titel.strip() else f"Grafiek {index + 1}"


@dataclass(frozen=True)
class Verversing:
    """Ververs: per dataoproep de status van replay_data_calls, en de figuren als alles herlaadde (#524)."""

    calls: list[dict]
    uitkomsten: list[Figuuruitkomst] = field(default_factory=list)

    @property
    def mislukte_calls(self) -> int:
        return sum(1 for c in self.calls if not c["success"])


def replay_dashboard_figures(recipe: list[dict], figure_recipes: list[dict]) -> Verversing:
    """Ververs: herlaad de data bij de bron en maak per figuurrecept de figuur opnieuw.

    1. Replay data-load calls (populates store with fresh data)
    2. Alleen als elke call slaagde: per figuurrecept een uitkomst, de figuur-JSON of
       de reden waarom niet. Uit half herladen data komen geen figuren: die zouden
       verse en oude data mengen onder het label "ververst" (#524).
    """
    verversing = Verversing(replay_data_calls(recipe))
    if verversing.mislukte_calls:
        return verversing
    return Verversing(verversing.calls, figuur_uitkomsten(figure_recipes))


@dataclass(frozen=True)
class Reproductie:
    """Figuren uit de opgeslagen data, met wat er niet (meer) te maken was."""

    figures_json: list[str] = field(default_factory=list)
    ontbrekend: list[str] = field(default_factory=list)  # data-keys die niet meer in de store staan
    mislukt: list[Figuuruitkomst] = field(default_factory=list)  # elke andere reden (#523)


def reproduceer_figures(figure_recipes: list[dict]) -> Reproductie:
    """Maak de figuren opnieuw uit de data die al in de store staat — zonder netwerk (#346).

    Een key die de store kwijt is (herstart), komt in `ontbrekend`: reproduceren
    belooft identieke uitkomsten en haalt dus niets opnieuw op. Dat is aan ververs.
    Elke andere mislukking komt met haar reden in `mislukt`; ververs helpt daar niet.
    """
    uitkomsten = figuur_uitkomsten(figure_recipes)
    return Reproductie(
        figures_json=[u.figuur_json for u in uitkomsten if u.figuur_json is not None],
        ontbrekend=[
            key
            for fr, u in zip(figure_recipes, uitkomsten, strict=True)
            if u.reden is Reden.DATA_ONTBREEKT and (key := _data_key(fr))
        ],
        mislukt=[u for u in uitkomsten if u.reden not in (None, Reden.DATA_ONTBREEKT)],
    )


def _data_key(fr: object) -> str | None:
    query = fr.get("query") if isinstance(fr, dict) else None
    key = query.get("data_key") if isinstance(query, dict) else None
    return key if isinstance(key, str) and key else None


def _figuur(fr: dict) -> str | Reden:
    """Eén figuurrecept uitvoeren tegen de store: de figuur-JSON, of de reden waarom niet."""
    if (key := _data_key(fr)) is None:
        return Reden.GEEN_DATABRON
    if store.get(store.canoniek(key)) is None:
        return Reden.DATA_ONTBREEKT
    rijen = _rijen(fr["query"])
    if isinstance(rijen, Reden):
        return rijen
    plot = fr.get("plot") or {}
    try:
        _, figure = dispatch(TOOL_CREATE_PLOT, {**plot, "data": rijen})
        return Reden.GEEN_GRAFIEK if figure is None else pio.to_json(figure)
    except Exception:
        logger.debug("Figuur herhalen mislukt bij de plot", exc_info=True)
        return Reden.GEEN_GRAFIEK


def _rijen(query: dict) -> list | Reden:
    """De rijen van de query van een figuurrecept; een fouttekst of uitzondering is QUERY_MISLUKT."""
    try:
        resultaat = json.loads(dispatch(TOOL_QUERY_DATA, query)[0])
    except Exception:
        logger.debug("Figuur herhalen mislukt bij de query", exc_info=True)
        return Reden.QUERY_MISLUKT
    rijen = resultaat.get("rijen") if isinstance(resultaat, dict) else None
    if not isinstance(rijen, list):
        return Reden.QUERY_MISLUKT
    return rijen or Reden.GEEN_RIJEN


def ankers_van_recipe(recipe: list[dict], vorige: Mapping[str, str] | None = None) -> dict[str, str]:
    """Per CBS-dataset in het recept de laatste-update-datum zoals CBS hem nu meldt (#346, #524).

    Het anker van een dashboard: bij ververs vertelt het verschil met het bewaarde
    anker dat de bron zelf is bijgewerkt, los van wat er in de figuren verschuift.
    De datum komt per aanroep bij CBS vandaan (bron_laatste_update): de catalogus is
    een momentopname uit de package. Antwoordt CBS niet, dan blijft het vorige anker
    staan (`vorige`, het bewaarde) en anders geldt de catalogusdatum. Doet netwerk-I/O:
    roep dit niet aan op de event loop.
    """
    vorige = vorige or {}
    ankers: dict[str, str] = {}
    for call in recipe:
        if call.get("name") != TOOL_GET_CBS_DATA:
            continue
        try:
            args = json.loads(call.get("arguments") or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        dataset = args.get("dataset_id")
        if not isinstance(dataset, str) or not dataset:
            continue
        if update := (bron_laatste_update(dataset) or vorige.get(dataset) or catalogus_laatste_update(dataset)):
            ankers[dataset] = update
    return ankers


def anker_verschillen(oud: dict[str, str], nieuw: dict[str, str]) -> list[str]:
    """Meldingen voor bronnen die sinds het bewaarde anker zijn bijgewerkt."""
    return [
        f"CBS-tabel {dataset} is bij de bron bijgewerkt op {datum} (was {was})."
        for dataset, datum in nieuw.items()
        if (was := (oud or {}).get(dataset)) and was != datum
    ]
