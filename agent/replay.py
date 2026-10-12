"""De twee herhaalmodi van een dashboard: ververs en reproduceer (#346).

- ververs: voer de dataoproepen opnieuw uit tegen de bron en maak de figuren
  opnieuw; de aanroeper vergelijkt met het bewaarde dashboard en toont het
  verschil (agent/figuurverschil.py).
- reproduceer: maak de figuren opnieuw uit de data die al in de store staat,
  zonder netwerk. Dezelfde data en hetzelfde recept geven byte-identieke
  figuren terug.
"""

import json
import logging
from dataclasses import dataclass, field

import plotly.io as pio

from tools import dispatch, store
from tools.catalog import catalogus_laatste_update
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


def replay_dashboard_figures(
    recipe: list[dict],
    figure_recipes: list[dict],
) -> list[str]:
    """Reload data and re-create figures. Returns updated figures_json.

    1. Replay data-load calls (populates store with fresh data)
    2. For each figure recipe: re-query data, re-create plot
    """
    replay_data_calls(recipe)
    return [figuur for fr in figure_recipes if (figuur := _figuur(fr)) is not None]


@dataclass(frozen=True)
class Reproductie:
    """Figuren uit de opgeslagen data, met wat er niet (meer) te maken was."""

    figures_json: list[str] = field(default_factory=list)
    ontbrekend: list[str] = field(default_factory=list)  # data-keys die niet meer in de store staan


def reproduceer_figures(figure_recipes: list[dict]) -> Reproductie:
    """Maak de figuren opnieuw uit de data die al in de store staat — zonder netwerk (#346).

    Een key die de store kwijt is (herstart), komt in `ontbrekend`: reproduceren
    belooft identieke uitkomsten en haalt dus niets opnieuw op. Dat is aan ververs.
    """
    figures_json: list[str] = []
    ontbrekend: list[str] = []
    for fr in figure_recipes:
        key = (fr.get("query") or {}).get("data_key")
        if not isinstance(key, str) or not key:
            continue
        if store.get(store.canoniek(key)) is None:
            ontbrekend.append(key)
            continue
        if (figuur := _figuur(fr)) is not None:
            figures_json.append(figuur)
        else:
            ontbrekend.append(key)
    return Reproductie(figures_json, ontbrekend)


def _figuur(fr: dict) -> str | None:
    """Eén figuurrecept uitvoeren tegen de store: query de data, maak de plot."""
    query = fr.get("query")
    plot = fr.get("plot") or {}
    if not query or not query.get("data_key"):
        return None
    try:
        result_str, _ = dispatch(TOOL_QUERY_DATA, query)
        rows = json.loads(result_str).get("rijen", [])
        if not rows:
            return None
        _, figure = dispatch(TOOL_CREATE_PLOT, {**plot, "data": rows})
        if figure is None:
            return None
        return pio.to_json(figure)
    except Exception:
        logger.debug("Figure replay mislukt, overgeslagen", exc_info=True)
        return None


def ankers_van_recipe(recipe: list[dict]) -> dict[str, str]:
    """Per CBS-dataset in het recept de laatste-update-datum uit de catalogus (#346).

    Het anker van een dashboard: bij ververs vertelt het verschil met het bewaarde
    anker dat de bron zelf is bijgewerkt, los van wat er in de figuren verschuift.
    """
    ankers: dict[str, str] = {}
    for call in recipe:
        if call.get("name") != TOOL_GET_CBS_DATA:
            continue
        try:
            args = json.loads(call.get("arguments") or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        dataset = args.get("dataset_id")
        if isinstance(dataset, str) and dataset and (update := catalogus_laatste_update(dataset)):
            ankers[dataset] = update
    return ankers


def anker_verschillen(oud: dict[str, str], nieuw: dict[str, str]) -> list[str]:
    """Meldingen voor bronnen die sinds het bewaarde anker zijn bijgewerkt."""
    return [
        f"CBS-tabel {dataset} is bij de bron bijgewerkt op {datum} (was {was})."
        for dataset, datum in nieuw.items()
        if (was := (oud or {}).get(dataset)) and was != datum
    ]
