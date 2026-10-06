"""Controles op een gegenereerd rapport vóór het de gebruiker bereikt (#175).

Het rapport is door een model geschreven. Of dat klopt met zijn eigen data en
grafieken, is met code te controleren, voor elk model gelijk:
- het rapport heeft inhoud: reikwijdte, conclusie en een getal of grafiek (#189);
- elk groot getal in de tekst komt uit de data van het rapport;
- de tekst claimt geen afwezigheid van data naast een gevulde grafiek;
- opleidingsvorm en dataset-ID in de tekst kloppen met de bron (#196);
- een getal staat bij het jaar en de instelling van zijn eigen rij (#197);
- een oorzaak rust op een eigen bron of staat er als niet vast te stellen (#225).
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from agent.beweringen import ongedekte_oorzaak
from agent.binding import verkeerd_gebonden
from agent.dimensielabels import verkeerde_dimensielabels
from agent.grounding import unsourced_numbers
from agent.kenmerken import verkeerde_kenmerken
from agent.kpi_periode import verkeerde_kpi_periodes
from agent.labels import (
    onbekende_datasets,
    ongebruikte_bronnen,
    verkeerde_opleidingsvormen,
)
from agent.probleem import Probleem, hard, veilig

if TYPE_CHECKING:
    from agent.report import ReportSpec

# Vaste lijst: een model dat "geen data" schrijft naast een grafiek met waarden
# spreekt zichzelf tegen (live-audit 5: "bevat geen rijen met ... 25DW").
_ABSENCE = re.compile(
    r"\b(?:bevat |zijn |er zijn )?geen (?:rijen|data|gegevens|cijfers)\b"
    r"|\bkunnen geen\b.{0,60}\bworden gepresenteerd\b",
    re.IGNORECASE,
)


# "resource 3" zegt een lezer niets: de naam van het bestand staat in de bronvermelding (#329).
_RESOURCE_VERWIJZING = re.compile(r"\bresource\s*\d+\b", re.IGNORECASE)

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
    # Hard (#207): een leeg rapport, of een getal of feit dat niet bij de data hoort.
    problems: list[str] = [*hard(_missing(spec))]
    text = _all_text(spec)

    unsourced = unsourced_numbers(text, sources)
    if unsourced:
        problems += hard(
            [
                f"Deze getallen staan niet in de opgehaalde data: {', '.join(_nl(n) for n in sorted(unsourced, key=int))}."
            ]
        )

    if any(_has_values(f) for f in figures_json):
        for claim in _claims(spec):
            if match := _ABSENCE.search(claim or ""):
                problems += hard(
                    [f"De tekst zegt '{match.group(0)}', maar de grafiek in het rapport bevat wel waarden."]
                )
                break

    if match := _RESOURCE_VERWIJZING.search(text):
        problems.append(
            Probleem(
                f"De tekst verwijst naar '{match.group(0)}', dat een lezer niets zegt.",
                "Noem het bestand bij zijn titel of laat de verwijzing weg.",
            )
        )

    problems += veilig(verkeerde_opleidingsvormen, text, sources)
    problems += veilig(verkeerde_dimensielabels, text, sources)
    problems += veilig(onbekende_datasets, text)
    problems += veilig(ongebruikte_bronnen, text, sources)
    problems += hard(veilig(verkeerd_gebonden, text, sources))
    problems += hard(veilig(verkeerde_kenmerken, text, sources))
    problems += hard(veilig(verkeerde_kpi_periodes, text, sources))
    problems += veilig(ongedekte_oorzaak, "\n\n".join(_claims(spec)), sources)
    return problems
