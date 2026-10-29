"""Waar het rapport meetbaar afwijkt van de vraag, als eerste regel van het rapport, uit code (#734).

Een gebruiker vroeg om een prognose; het model kon die niet maken en extrapoleerde de eigen trend. Dat stond in het
rapport, maar niet vooraan: "Het veranderen van de onderzoeksvraag had veel prominenter in beeld en als eerste
genoemd moeten zijn." Code legt de vraag naast wat het rapport toont, waar dat verschil meetbaar is:

- **periode**: een gevraagd bereik ("2016 tot 2025"), een begin ("vanaf 2016") of een aantal jaren ("de afgelopen
  10 jaar") tegen de jaren op de tijdas van de grafieken;
- **prognose**: een vraag naar een prognose, terwijl geen geladen bron een prognose is.

Andere afwijkingen blijven tekst van het model. Wat gevraagd was, komt uit de woorden van de gebruiker: de bevestigde
onderzoeksvraag (#750), anders de laatste vraag die een periode of prognose noemt (een bijsturing gaat voor, #733).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date

from tools import periode, store
from tools.arbeidsmarkt import ROA_ID

from .report_periode import startjaar
from .selectie import laadkey

# "vanaf 2016", ook als schooljaar: "sinds 2021/22".
_VANAF = re.compile(r"\b(?:vanaf|sinds)\s+(20\d{2})(?:\s*/\s*'?\d{2,4})?(?!\d)", re.IGNORECASE)
_TELWOORDEN = {
    "twee": 2, "drie": 3, "vier": 4, "vijf": 5, "zes": 6, "zeven": 7, "acht": 8, "negen": 9, "tien": 10,
    "elf": 11, "twaalf": 12, "vijftien": 15, "twintig": 20,
}  # fmt: skip
_LAATSTE = re.compile(
    r"\b(?:afgelopen|laatste|voorbije)\s+(\d{1,2}|"
    + "|".join(_TELWOORDEN)
    + r")\s+(?:jaar|jaren|studiejaren|schooljaren)\b",
    re.IGNORECASE,
)
_PROGNOSE = re.compile(r"\b(prognose\w*|voorspel\w*|raming\w*)\b", re.IGNORECASE)
_TOEKOMSTJAAR = re.compile(r"(?<![\d/])(20\d{2})(?![\d/])")


@dataclass(frozen=True)
class _Periode:
    tekst: str  # hoe de vraag haar noemde, voor de regel
    begin: int | None = None
    eind: int | None = None
    jaren: int | None = None  # "de afgelopen N jaar"


def _periode(vraag: str) -> _Periode | None:
    if bereik := periode.genoemd_bereik(vraag):
        return _Periode(f"{bereik[0]} tot en met {bereik[1]}", begin=bereik[0], eind=bereik[1])
    if match := _LAATSTE.search(vraag):
        aantal = match.group(1).lower()
        n = int(aantal) if aantal.isdigit() else _TELWOORDEN[aantal]
        return _Periode(f"de afgelopen {n} jaar", jaren=n) if n >= 2 else None
    if match := _VANAF.search(vraag):
        return _Periode(f"vanaf {match.group(1)}", begin=int(match.group(1)))
    return None


def getekende_jaren(visualisaties: list[dict]) -> list[int]:
    """De startjaren op de tijdas van de grafieken, gesorteerd; leeg zonder tijdas."""
    jaren: set[int] = set()
    for vis in visualisaties:
        try:
            figuur = json.loads(vis.get("figure_json") or "")
        except (TypeError, ValueError):
            continue
        for trace in (figuur.get("data") or []) if isinstance(figuur, dict) else []:
            waarden = trace.get("x") if isinstance(trace.get("x"), list) else []
            gevonden = [startjaar(w) for w in waarden]
            if waarden and all(j is not None for j in gevonden):
                jaren |= {j for j in gevonden if j is not None}
    return sorted(jaren)


def _periode_afwijking(gevraagd: _Periode, jaren: list[int]) -> str | None:
    eerste, laatste = periode.label(jaren[0]), periode.label(jaren[-1])
    getoond = f"de grafieken tonen {eerste} t/m {laatste}"
    if gevraagd.jaren is not None:
        if len(jaren) >= gevraagd.jaren:
            return None
        return f"Gevraagd was {gevraagd.tekst}; {getoond} ({len(jaren)} jaar), meer staat niet in de bron."
    te_laat = gevraagd.begin is not None and jaren[0] > gevraagd.begin
    te_vroeg = gevraagd.eind is not None and jaren[-1] < gevraagd.eind
    if not (te_laat or te_vroeg):
        return None
    return f"Gevraagd was {gevraagd.tekst}; {getoond}."


def _prognosebron(keys: list[str]) -> bool:
    for key in keys:
        known = store.meta(laadkey(key)) if isinstance(key, str) else None
        if known and ("prognose" in str(known.dataset).lower() or known.dataset == ROA_ID):
            return True
    return False


def _vraagt_prognose(vraag: str, vandaag: date) -> bool:
    return bool(_PROGNOSE.search(vraag)) or any(int(j) > vandaag.year for j in _TOEKOMSTJAAR.findall(vraag))


def afwijkingen(
    vragen: list[str], visualisaties: list[dict], keys: list[str], vandaag: date | None = None
) -> list[str]:
    """De regels voor het begin van het rapport; leeg als het rapport toont wat gevraagd was.

    `vragen` in volgorde van voorrang: de bevestigde onderzoeksvraag alleen, of anders de vragen van de gebruiker van
    laatst naar eerst. De periode komt uit de eerste vraag die er een noemt; een prognose telt als een van de vragen
    erom vraagt. `keys` zijn de keys die het rapport las en tekende.
    """
    vandaag = vandaag or date.today()
    regels: list[str] = []
    gevraagd = next((p for v in vragen if v and (p := _periode(v))), None)
    if gevraagd and (jaren := getekende_jaren(visualisaties)) and (regel := _periode_afwijking(gevraagd, jaren)):
        regels.append(regel)
    if any(v and _vraagt_prognose(v, vandaag) for v in vragen) and not _prognosebron(keys):
        regels.append("Gevraagd was een prognose; dit rapport toont het verloop tot nu toe, geen prognose.")
    return regels
