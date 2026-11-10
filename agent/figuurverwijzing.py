"""Een rapport staat op zichzelf: de tekst wijst niet naar het gesprek en noemt geen figuur die er niet in staat (#994).

Rapport 0573ff89 had één staafgrafiek, en de toelichting zei "De Sankey-visualisatie uit het gesprek toont dezelfde
gegevens als stroomdiagram". De lezer van een rapport zag het gesprek vaak niet, en zoekt dan een figuur die er niet is.

De soort van een figuur staat in haar Plotly-JSON: het trace-type, en bij scatter de mode (lijn of punten). Welke woorden
bij een soort horen en welke trace-types haar tekenen, staat in `SOORTEN`, op één plek.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from agent.probleem import Probleem


@dataclass(frozen=True)
class Soort:
    naam: str  # zoals de melding haar noemt
    woorden: re.Pattern  # zoals de tekst haar noemt
    sporen: frozenset[str]  # de Plotly-trace-types die zo'n figuur tekenen


def _soort(naam: str, woorden: str, *sporen: str) -> Soort:
    return Soort(naam, re.compile(rf"\b(?:{woorden})", re.IGNORECASE), frozenset(sporen))


# Staand of liggend (bar met orientation "h"): allebei een staafdiagram. Een scatter is een lijngrafiek of een
# spreidingsdiagram naar zijn mode (`_soorten_van`). "In kaart brengen" is een uitdrukking, geen kaart.
SOORTEN: dict[str, Soort] = {
    "sankey": _soort("sankey-diagram", r"sankey[\w-]*|stroomdiagram\w*", "sankey"),
    "kaart": _soort(
        "kaart",
        r"(?<!\bin )(?:land)?kaart(?:en)?\b",
        "choropleth",
        "choroplethmap",
        "choroplethmapbox",
        "scattergeo",
        "scattermap",
        "scattermapbox",
        "densitymap",
        "densitymapbox",
    ),
    "taartdiagram": _soort("taartdiagram", r"(?:taart|cirkel)(?:diagram|grafiek)\w*", "pie"),
    "spreidingsdiagram": _soort("spreidingsdiagram", r"spreidingsdiagram\w*|puntenwolk\w*", "scatter", "scattergl"),
    "lijngrafiek": _soort("lijngrafiek", r"lijn(?:grafiek|diagram)\w*", "scatter", "scattergl"),
    "staafdiagram": _soort("staafdiagram", r"(?:staaf|kolom)(?:diagram|grafiek)\w*", "bar"),
    "heatmap": _soort("heatmap", r"heatmap\w*", "heatmap"),
    "treemap": _soort("treemap", r"treemap\w*", "treemap"),
}

# "uit het gesprek", "eerder in het gesprek", "zoals in de chat getoond", "zie de chat": het gesprek als vindplaats.
_GESPREK = re.compile(
    r"\b(?:(?:eerder\s+)?(?:in|uit|tijdens|via)|zie)\s+(?:het|dit|ons|de|deze)\s+(?:eerdere\s+|vorige\s+)?"
    r"(?:gesprek|chat(?:gesprek)?|conversatie)\b"
    r"|\b(?:het\s+gesprek|de\s+chat)\s+(?:toon\w*|liet\b|laat\b|gaf\b|geeft\b)",
    re.IGNORECASE,
)

_OPDRACHT = (
    "Beschrijf alleen de figuren in dit rapport en verwijs niet naar het gesprek: de lezer ziet alleen het rapport."
)


def _sporen(figure_json: str) -> list[dict]:
    traces = json.loads(figure_json).get("data") or []
    return [t for t in traces if isinstance(t, dict)]


def _soorten_van(trace: dict) -> set[str]:
    """De soorten die deze trace tekent; een scatter zonder mode kan beide zijn (Plotly kiest dan zelf)."""
    spoor = trace.get("type") or "scatter"
    soorten = {sleutel for sleutel, soort in SOORTEN.items() if spoor in soort.sporen}
    if isinstance(mode := trace.get("mode"), str) and soorten & {"lijngrafiek", "spreidingsdiagram"}:
        soorten.discard("spreidingsdiagram" if "lines" in mode else "lijngrafiek")
    return soorten


def figuursoorten(figures_json: list[str]) -> set[str]:
    """De soorten (sleutels van `SOORTEN`) van de figuren in het rapport."""
    return {soort for figuur in figures_json for trace in _sporen(figuur) for soort in _soorten_van(trace)}


def gesprek_als_vindplaats(text: str) -> list[Probleem]:
    """Een verwijzing naar het gesprek of de chat als plek waar iets te zien is."""
    if match := _GESPREK.search(text):
        return [
            Probleem(
                f"De tekst verwijst naar '{match.group(0)}', maar de lezer van het rapport ziet het gesprek niet.",
                _OPDRACHT,
            )
        ]
    return []


def verkeerde_figuurverwijzing(text: str, figures_json: list[str]) -> list[Probleem]:
    """Per grafieksoort die de tekst noemt en die geen figuur van het rapport heeft, één probleem."""
    aanwezig = figuursoorten(figures_json)
    problemen: list[Probleem] = []
    for sleutel, soort in SOORTEN.items():
        if sleutel not in aanwezig and (match := soort.woorden.search(text)):
            problemen.append(
                Probleem(
                    f"De tekst noemt '{match.group(0)}', maar het rapport heeft geen {soort.naam}.",
                    _OPDRACHT,
                )
            )
    return problemen
