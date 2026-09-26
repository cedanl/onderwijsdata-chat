"""Controles op een gegenereerd rapport vóór het de gebruiker bereikt (#175).

Het rapport is door een model geschreven. Of dat klopt met zijn eigen data en
grafieken, is met code te controleren, voor elk model gelijk:
- het rapport heeft inhoud: reikwijdte, conclusie en een getal of grafiek (#189);
- elk groot getal in de tekst komt uit de data van het rapport;
- de tekst claimt geen afwezigheid van data naast een gevulde grafiek;
- opleidingsvorm, dataset-ID en teleenheid in de tekst kloppen met de bron (#196).
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from agent.grounding import unsourced_numbers
from agent.labels import onbekende_datasets, verkeerde_opleidingsvormen, verkeerde_teleenheid

if TYPE_CHECKING:
    from agent.report import ReportSpec

# Vaste lijst: een model dat "geen data" schrijft naast een grafiek met waarden
# spreekt zichzelf tegen (live-audit 5: "bevat geen rijen met ... 25DW").
_ABSENCE = re.compile(
    r"\b(?:bevat |zijn |er zijn )?geen (?:rijen|data|gegevens|cijfers)\b"
    r"|\bkunnen geen\b.{0,60}\bworden gepresenteerd\b",
    re.IGNORECASE,
)


# Een getal dat geen jaartal is: "2021" alleen is een periode, geen bevinding.
_FINDING_NUMBER = re.compile(r"\b(?!(?:19|20)\d{2}\b)\d+")


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


def _missing(spec: ReportSpec) -> list[str]:
    """Wat een rapport minimaal nodig heeft.

    Zonder geldige JSON van het model blijft er een schil over met alleen vraag en
    bron (#189). De getalcontrole laat die door: zonder getallen is er niets te
    controleren.
    """
    missing = []
    if not spec.conclusie.strip():
        missing.append("Het rapport heeft geen conclusie.")
    if not (spec.beantwoordt or spec.beantwoordt_niet):
        missing.append("Het rapport heeft geen reikwijdte (beantwoordt / beantwoordt_niet).")
    if not spec.visualisaties and not any(_FINDING_NUMBER.search(c or "") for c in _claims(spec)):
        missing.append("Het rapport bevat geen getal of grafiek uit de data.")
    return missing


def report_problems(spec: ReportSpec, figures_json: list[str], sources: list[str]) -> list[str]:
    """Wat ontbreekt en wat de tekst tegenspreekt aan de data; leeg als het klopt.

    `sources` zijn de toolresultaten en de datasetcontext van deze rapportrun.
    """
    problems = _missing(spec)
    text = _all_text(spec)

    unsourced = unsourced_numbers(text, sources)
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

    problems += verkeerde_opleidingsvormen(text)
    problems += onbekende_datasets(text)
    problems += verkeerde_teleenheid(text, sources)
    return problems
