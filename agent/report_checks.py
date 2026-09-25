"""Controles op een gegenereerd rapport vóór het de gebruiker bereikt (#175).

Het rapport is door een model geschreven. Of dat klopt met zijn eigen data en
grafieken, is met code te controleren, voor elk model gelijk:
- elk groot getal in de tekst komt uit de data van het rapport;
- de tekst claimt geen afwezigheid van data naast een gevulde grafiek.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from agent.grounding import unsourced_numbers

if TYPE_CHECKING:
    from agent.report import ReportSpec

# Vaste lijst: een model dat "geen data" schrijft naast een grafiek met waarden
# spreekt zichzelf tegen (live-audit 5: "bevat geen rijen met ... 25DW").
_ABSENCE = re.compile(
    r"\b(?:bevat |zijn |er zijn )?geen (?:rijen|data|gegevens|cijfers)\b"
    r"|\bkunnen geen\b.{0,60}\bworden gepresenteerd\b",
    re.IGNORECASE,
)


def _claims(spec: ReportSpec) -> list[str]:
    """De beweringen van het rapport; beantwoordt_niet noemt legitiem wat ontbreekt."""
    return [
        spec.conclusie,
        *spec.beantwoordt,
        *(v.get("toelichting", "") for v in spec.visualisaties),
    ]


def _all_text(spec: ReportSpec) -> str:
    """Alle modeltekst behalve de onderzoeksvraag (die komt van de gebruiker) en de bronnen (#48)."""
    definities = (f"{d.get('begrip', '')} {d.get('definitie', '')}" for d in spec.definities)
    titels = (v.get("titel", "") for v in spec.visualisaties)
    return "\n".join([spec.title, *definities, *spec.beantwoordt_niet, *titels, *_claims(spec)])


def _has_values(figure_json: str) -> bool:
    traces = json.loads(figure_json).get("data", [])
    return any(len(t.get("y") or t.get("values") or []) > 0 for t in traces)


def _nl(number: str) -> str:
    return f"{int(number):,}".replace(",", ".")


def report_problems(spec: ReportSpec, figures_json: list[str], sources: list[str]) -> list[str]:
    """Tegenstrijdigheden tussen de tekst en de data van het rapport; leeg als het klopt.

    `sources` zijn de toolresultaten en de datasetcontext van deze rapportrun.
    """
    problems: list[str] = []

    unsourced = unsourced_numbers(_all_text(spec), sources)
    if unsourced:
        problems.append(
            "Deze getallen staan niet in de opgehaalde data: "
            f"{', '.join(_nl(n) for n in sorted(unsourced, key=int))}."
        )

    if any(_has_values(f) for f in figures_json):
        for claim in _claims(spec):
            if match := _ABSENCE.search(claim or ""):
                problems.append(
                    f"De tekst zegt '{match.group(0)}', maar de grafiek in het rapport bevat wel waarden."
                )
                break

    return problems
