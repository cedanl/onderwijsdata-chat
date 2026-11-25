"""Een getal in het antwoord dat een onderdrukte cel terugrekent, geldt niet als gedekt (#1265).

run_analysis en compute_kpi weigeren een uitkomst die een onderdrukte cel exact teruggeeft (`tools.terugrekenen`).
Het model kan het verschil ook zelf opschrijven: "het totaal is 203, Economie 120 en Zorg 80, dus Techniek 3". Deze
controle vangt dat in het antwoord: een getal dat gelijk is aan een reconstructie en in een zin staat die de cel
noemt (haar label, het totaal of de som van de zichtbare delen), is een hard probleem. De getalcontrole telt zo'n
verschil van twee genoemde getallen ook niet meer als afgeleid (`afgeleide_verschillen`, #409).

Eigenaar: de reconstructieregel staat in `tools/terugrekenen.py` (de bron en wat een totaal is), deze module past hem
toe op de antwoordtekst. Heroverwegen als de bronnen zelf secundair onderdrukken (dan is er geen exact verschil meer),
of als de controle een kwartaal lang niet afgaat in de logregel CONTROLES.
"""

import re
from decimal import Decimal

from tools import terugrekenen

from .grounding import decimalen_met_positie, getallen_met_positie, kleine_getallen_met_positie
from .probleem import Probleem
from .selectie import stapkeys

# Een zin of een tabelrij, zoals in agent/binding.py: een punt in een getal (27.135) wordt niet gevolgd door witruimte.
_SEGMENT = re.compile(r"\n|(?<=[.!?;])\s+")
_CIJFERS = re.compile(r"\D")
# Woorden waarmee een zin een verschil uitrekent of de cel aanwijst.
_REKENWOORD = re.compile(
    r"\b(?:dus|blijft|blijven|resteert|rest|over|min|minus|verschil|onderdrukt|afgeschermd|ontbrekende?)\b|-1",
    re.IGNORECASE,
)


def _keys(tool_results: list[str]) -> list[str]:
    return list(dict.fromkeys(k for result in tool_results for k in stapkeys(result)))


def _waarden(tekst: str) -> set[float]:
    """Elk getal in de tekst, in Nederlandse notatie gelezen (jaartallen niet)."""
    gehele = [cijfers for _, cijfers, _ in (*getallen_met_positie(tekst), *kleine_getallen_met_positie(tekst))]
    return {float(c) for c in gehele} | {float(d) for _, d, _ in decimalen_met_positie(tekst)}


def _noemt_de_cel(zin: str, reconstructie: terugrekenen.Reconstructie, waarden: set[float]) -> bool:
    """Gaat de zin over de cel: haar label, de som van de zichtbare delen, of het totaal met een rekenwoord erbij?
    Alleen het totaal is te weinig: "203 studenten in 3 sectoren" noemt het totaal en een 3 die geen cel is."""
    label = re.escape(reconstructie.label.strip())
    return (
        bool(label and re.search(rf"(?<!\w){label}(?!\w)", zin, re.IGNORECASE))
        or reconstructie.zichtbaar in waarden
        or (reconstructie.totaal in waarden and bool(_REKENWOORD.search(zin)))
    )


def teruggerekende_cellen(text: str, tool_results: list[str]) -> list[Probleem]:
    """Een hard probleem als het antwoord een onderdrukte cel noemt die het uit totaal en delen terugrekende."""
    gezocht = terugrekenen.reconstructies(_keys(tool_results))
    if not gezocht:
        return []
    for zin in _SEGMENT.split(text):
        waarden = _waarden(zin)
        if any(r.waarde in waarden and _noemt_de_cel(zin, r, waarden) for r in gezocht):
            return [
                Probleem(
                    terugrekenen.MELDING,
                    "Noem geen getal voor die cel, ook niet als totaal min de andere delen: zeg dat de bron haar "
                    "onderdrukte en geef alleen de zichtbare delen en het totaal.",
                )
            ]
    return []


def zonder_teruggerekend(geschreven: set[str], tool_results: list[str]) -> set[str]:
    """De getallen (zoals geschreven, geheel) die geen reconstructie van een onderdrukte cel zijn."""
    if not geschreven:
        return geschreven
    gezocht = {r.waarde for r in terugrekenen.reconstructies(_keys(tool_results))}
    return {g for g in geschreven if float(Decimal(_CIJFERS.sub("", g) or "0")) not in gezocht}
