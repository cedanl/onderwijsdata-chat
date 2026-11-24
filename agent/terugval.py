"""Een vaste regel onder het antwoord als ROA voor de gevraagde regio terugviel op landelijke cijfers, uit code (#1100).

Op "Hoe staat de arbeidsmarkt voor Mbo4 - zorg en dienstverlening in Midden-Utrecht ervoor?" gaf get_roa_benchmark de
prognose voor Midden-Utrecht en de schoolverlatersinformatie landelijk, met de zin in `terugval`. Of die in het antwoord
kwam, hing van het model af: dan las een landelijk cijfer als regionaal. Nu zet de app de zin zelf onder het antwoord,
één keer; schreef het model hem letterlijk over, dan vervalt die kopie.
"""

import json
import re

from tools.arbeidsmarkt import ROA_ID, roa_blokken

KOP = "**Regio:**"
_LEGE_REGELS = re.compile(r"\n{3,}")
# Wat er van een regel overblijft als de zin eruit is en die regel verder niets zei: leeg, een opsommingsteken, de kop.
_RESTEN = {"", "-", "*", "+", KOP}


def _json(result: str) -> dict:
    try:
        parsed = json.loads(result)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def terugvalzinnen(tool_results: list[str]) -> list[str]:
    """De `terugval`-zinnen van de ROA-resultaten van de beurt, elk één keer, ook die van een ho-onderdeel."""
    zinnen: dict[str, None] = {}
    for result in tool_results:
        if (parsed := _json(result)).get("dataset") != ROA_ID:
            continue
        for blok in roa_blokken(parsed):
            if isinstance(zin := blok.get("terugval"), str) and zin.strip():
                zinnen[zin.strip()] = None
    return list(zinnen)


def _zonder_zin(tekst: str, zin: str) -> str:
    """De tekst zonder de letterlijke zin; een regel die daarna niets meer zegt, vervalt."""
    regels = []
    for regel in tekst.split("\n"):
        if zin in regel:
            regel = regel.replace(f" {zin}", "").replace(f"{zin} ", "").replace(zin, "").rstrip()
            if regel.strip() in _RESTEN:
                continue
        regels.append(regel)
    return _LEGE_REGELS.sub("\n\n", "\n".join(regels)).strip("\n")


def met_terugval(tekst: str, tool_results: list[str]) -> str:
    """Het antwoord met de terugvalregel eronder, als ROA voor de regio landelijke cijfers gaf; anders ongewijzigd."""
    zinnen = terugvalzinnen(tool_results)
    if not zinnen or not tekst.strip():
        return tekst
    for zin in zinnen:
        if zin in tekst:
            tekst = _zonder_zin(tekst, zin)
    regel = f"{KOP} {' '.join(zinnen)}"
    return f"{tekst.rstrip()}\n\n{regel}" if tekst.strip() else regel
