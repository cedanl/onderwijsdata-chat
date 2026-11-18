"""Vraagt de gebruiker om een verklaring? Code beslist, niet het model (#1036).

Een antwoord met data geeft alleen een oorzaak of hypothese als de gebruiker daarom vraagt: een niet onderbouwde
verklaring stuurt de lezer. `vraagt_verklaring` beslist dat op de vraag van de gebruiker; `agent.run` geeft de
uitkomst mee aan het model (beurtcontext) en aan de antwoordcontrole (`ongedekte_oorzaak`).

"reden" telt alleen in een verzoekvorm ("de reden voor/van/achter", "om welke reden", "wat is de reden"): als los
woord is het ook een onderwerp ("redenen om te studeren"). "verklaring" telt niet als het om een woordbetekenis gaat
("de verklaring van de afkorting HBO") of om een verklaring omtrent gedrag (VOG).

Een vervolgvraag zonder eigen verzoek houdt het verzoek van de vorige vraag, maar alleen als ze elliptisch is: ze
begint met "en" of "ook", of telt hooguit vier woorden ("En voor wo?"). Een volledige nieuwe vraag staat op zichzelf.

Deze module kent alleen strings, zoals `ho_markers`: geen import uit de agent of de catalogus.
"""

import re

_VERZOEK = re.compile(
    r"\bwaarom\b"
    r"|\bhoe\s+komt\s+(?:het|dat|dit)\b"
    r"|\boorza(?:ak|ken)\b"
    r"|\bverkla(?:ar[dt]?|ren|ring(?:en)?)\b"
    r"(?!\s+(?:van\s+(?:de|het|een)\s+(?:afkorting|term|begrip|woord)|omtrent\s+gedrag)\b)"
    r"|\bkomt\s+(?:dat|dit|het)\s+(?:door|doordat|omdat)\b"
    r"|\bwat\s+zit\s+(?:er\s*)?achter\b"
    r"|\bde\s+reden(?:en)?\s+(?:voor|van|achter)\b"
    r"|\bom\s+welke\s+reden(?:en)?\b"
    r"|\bwat\s+(?:is|zijn|was|waren)\s+(?:de\s+)?reden(?:en)?\b",
    re.IGNORECASE,
)
_ELLIPTISCH_BEGIN = re.compile(r"^\W*(?:en|ook)\b", re.IGNORECASE)
_MAX_WOORDEN_ELLIPTISCH = 4


def _is_verzoek(tekst: str) -> bool:
    return bool(_VERZOEK.search(tekst))


def _is_elliptisch(vraag: str) -> bool:
    return bool(_ELLIPTISCH_BEGIN.match(vraag)) or len(vraag.split()) <= _MAX_WOORDEN_ELLIPTISCH


def vraagt_verklaring(vraag: str, vorige: str = "") -> bool:
    """Vraagt `vraag` om een oorzaak, reden of verklaring; een elliptische vervolgvraag erft dat van `vorige`."""
    if _is_verzoek(vraag):
        return True
    return bool(vorige) and bool(vraag.strip()) and _is_elliptisch(vraag) and _is_verzoek(vorige)
