"""Getallen in modeltekst moeten uit de toolresultaten komen.

Een model kan een getal verzinnen, afronden of uit een andere selectie halen. Dat
is per model anders, maar met code te controleren: elk getal van vier of meer
cijfers in de tekst moet ergens in de toolresultaten van dezelfde run staan.
Jaartallen en kleinere getallen vallen buiten de controle.
"""

import re

# Een getal in Nederlandse notatie: 378.490 of 378490, optioneel met decimale komma.
# Niet aan een letter of cijfer vast: 85423NED, 2024SJ00 en T001228 zijn codes (#48).
_TEXT_NUMBER = re.compile(r"(?<![\w.,])(\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?(?!\w)")
_TOOL_NUMBER = re.compile(r"\d+")
_MIN_DIGITS = 4
_YEARS = range(1900, 2101)


def _checked(number: str) -> bool:
    return len(number) >= _MIN_DIGITS and int(number) not in _YEARS


def unsourced_numbers(text: str, tool_results: list[str]) -> set[str]:
    """Getallen (≥ 4 cijfers, geen jaartal) uit `text` die in geen enkel toolresultaat staan."""
    in_text = {m.group(1).replace(".", "") for m in _TEXT_NUMBER.finditer(text)}
    in_tools = {n for result in tool_results for n in _TOOL_NUMBER.findall(str(result))}
    return {n for n in in_text if _checked(n)} - in_tools
