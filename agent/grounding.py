"""Getallen in modeltekst moeten uit de toolresultaten komen.

Een model kan een getal verzinnen, afronden of uit een andere selectie halen. Dat
is per model anders, maar met code te controleren: elk getal van vier of meer
cijfers in de tekst moet ergens in de toolresultaten van dezelfde run staan.
Jaartallen en kleinere getallen vallen buiten de controle.

Voor chatantwoorden (#185) geldt dat ook voor percentages: een percentage is
bijna altijd een berekening, en die hoort in een tool, niet in het model.
"""

import json
import re
from decimal import ROUND_HALF_UP, Decimal

from tools.analysis import SCRIPTCONSTANTEN

# Een getal in Nederlandse notatie: 378.490 of 378490, optioneel met decimale komma.
# Duizendtallen ook met (harde of smalle) spatie: 378 490, zoals gpt-oss schrijft (#236).
# Niet aan een letter of cijfer vast: 85423NED, 2024SJ00 en T001228 zijn codes (#48).
_TEXT_NUMBER = re.compile(r"(?<![\w.,])(\d{1,3}(?:[. \u00a0\u202f]\d{3})+|\d+)(?:,\d+)?(?!\w)")
_THOUSANDS = re.compile(r"[. \u00a0\u202f]")
_TEXT_PERCENT = re.compile(r"(?<![\w.,])(\d+(?:,\d+)?)\s?(?:%|procent\b)")
_TOOL_NUMBER = re.compile(r"\d+")
# Decimalen in tooluitvoer: JSON schrijft 9.55, compute_kpi's weergave 9,6.
_TOOL_DECIMAL = re.compile(r"\d+(?:[.,]\d+)?")
_MIN_DIGITS = 4
_YEARS = range(1900, 2101)
_TRIVIAL_PERCENTAGES = (Decimal(0), Decimal(100))


def _digits(written: str) -> str:
    return _THOUSANDS.sub("", written)


def _checked(number: str) -> bool:
    return len(number) >= _MIN_DIGITS and int(number) not in _YEARS


def _als_dict(result: str) -> dict:
    try:
        parsed = json.loads(result)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _bronloos(result: str) -> bool:
    """Een toolresultaat dat zelf zegt geen data gelezen te hebben (run_analysis zonder gelezen key, #201)."""
    parsed = _als_dict(result)
    return "bron" in parsed and parsed["bron"] is None


def _scriptconstanten(result: str) -> list:
    """Getallen die een run_analysis-script zelf typte: die bewijzen niets (#410)."""
    constanten = _als_dict(result).get(SCRIPTCONSTANTEN)
    return constanten if isinstance(constanten, list) else []


def bewijs_getallen(result: str) -> set[str]:
    """De gehele getallen (cijfers) die één toolresultaat als bewijs levert; leeg bij een bronloos resultaat."""
    result = str(result)
    if _bronloos(result):
        return set()
    eigen = {n for c in _scriptconstanten(result) for n in _TOOL_NUMBER.findall(str(c))}
    return set(_TOOL_NUMBER.findall(result)) - eigen


def _bewijs_decimalen(result: str) -> set[Decimal]:
    """De decimalen die één toolresultaat als bewijs levert, zoals bewijs_getallen."""
    result = str(result)
    if _bronloos(result):
        return set()
    eigen = {Decimal(n) for c in _scriptconstanten(result) for n in _TOOL_DECIMAL.findall(str(c))}
    return {Decimal(n.replace(",", ".")) for n in _TOOL_DECIMAL.findall(result)} - eigen


def _tool_integers(tool_results: list[str]) -> set[str]:
    return {n for result in tool_results for n in bewijs_getallen(result)}


def checked_numbers(text: str) -> list[tuple[str, str]]:
    """Gehele getallen die de controle meeneemt: (zoals geschreven, cijfers)."""
    return [
        (m.group(0), digits)
        for m in _TEXT_NUMBER.finditer(text)
        if "," not in m.group(0) and _checked(digits := _digits(m.group(1)))
    ]


def unsourced_numbers(text: str, tool_results: list[str]) -> set[str]:
    """Getallen (≥ 4 cijfers, geen jaartal) uit `text` die in geen enkel toolresultaat staan."""
    in_text = {_digits(m.group(1)) for m in _TEXT_NUMBER.finditer(text)}
    return {n for n in in_text if _checked(n)} - _tool_integers(tool_results)


def _percentage_sourced(percentage: Decimal, tool_decimals: set[Decimal]) -> bool:
    """Staat het percentage, afgerond zoals in de tekst, in de tooluitvoer (ook als fractie)?"""
    if percentage in _TRIVIAL_PERCENTAGES:
        return True
    quantum = Decimal(1).scaleb(percentage.as_tuple().exponent)
    return any(
        candidate.quantize(quantum, rounding=ROUND_HALF_UP) == percentage
        for value in tool_decimals
        for candidate in (value, value * 100)
    )


def unverified(text: str, tool_results: list[str], conversation: list[str] = ()) -> list[str]:
    """Getallen en percentages uit `text` die niet gedekt zijn, zoals ze in de tekst staan.

    Getallen volgen de regel van unsourced_numbers; elk percentage moet, afgerond
    op zijn eigen decimalen, als waarde of als fractie in de bronnen staan. Bronnen
    zijn de toolresultaten en `conversation`: eerdere berichten van de assistent, in
    Nederlandse notatie gelezen (28.355 is één getal, geen 28 en 355). Wat de
    gebruiker zei is een bewering om te toetsen en hoort er niet bij (#211).
    """
    integers = _tool_integers(tool_results) | {
        _digits(m.group(1)) for said in conversation for m in _TEXT_NUMBER.finditer(said)
    }
    decimals = {d for r in tool_results for d in _bewijs_decimalen(r)} | {
        Decimal(m.group(1).replace(",", ".")) for said in conversation for m in _TEXT_PERCENT.finditer(said)
    }

    found: list[tuple[int, str]] = []
    percent_spans = []
    for m in _TEXT_PERCENT.finditer(text):
        percent_spans.append(m.span())
        if not _percentage_sourced(Decimal(m.group(1).replace(",", ".")), decimals):
            found.append((m.start(), m.group(0)))
    for m in _TEXT_NUMBER.finditer(text):
        if any(start <= m.start() < end for start, end in percent_spans):
            continue
        number = _digits(m.group(1))
        if _checked(number) and number not in integers:
            found.append((m.start(), m.group(0)))

    return list(dict.fromkeys(shown for _, shown in sorted(found)))
