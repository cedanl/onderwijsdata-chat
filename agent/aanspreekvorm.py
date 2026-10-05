"""Je-vorm in de verduidelijkingsvraag (#341, UX-10.2).

De app spreekt de gebruiker aan met je; het model schrijft in de clarify-vraag
soms 'Welk schooljaar bedoelt u?'. Na inversie verandert het werkwoord ('wilt u'
wordt 'wil je', 'heeft u' wordt 'heb je'), maar 'moet u' blijft 'moet je'. Dat is
zonder woordenboek niet te raden, dus alleen werkwoorden uit de lijst worden
omgezet. Blijft er daarna nog een u-vorm over, dan gaat de tekst ongewijzigd terug:
liever 'u' dan kapot Nederlands.
"""

import re

# Werkwoord vóór 'u' (inversie) → de vorm vóór 'je'.
_INVERSIE = {
    "bedoelt": "bedoel",
    "bent": "ben",
    "doet": "doe",
    "gaat": "ga",
    "heeft": "heb",
    "hebt": "heb",
    "kiest": "kies",
    "kunt": "kun",
    "mag": "mag",
    "moet": "moet",
    "vindt": "vind",
    "weet": "weet",
    "wenst": "wens",
    "wilt": "wil",
    "zoekt": "zoek",
    "zou": "zou",
}
# Werkwoord ná 'u' dat bij 'je' anders luidt; de rest is gelijk (u kunt → je kunt).
_NA_U = {"heeft": "hebt"}

_GEINVERTEERD = re.compile(rf"\b({'|'.join(_INVERSIE)}) u\b", re.IGNORECASE)
# 'u' als onderwerp vóór het werkwoord: aan het begin van een zin of na een voegwoord.
_ONDERWERP = re.compile(r"(^|[.!?:]\s+|\b(?i:als|dat|of|omdat|wanneer|zodat|waar|wat|die)\s+)([uU]) (\w+)")
_BEZITTELIJK = re.compile(r"\b([uU])w\b")
_U_VORM = re.compile(r"\b[uU]w?\b")


def _hoofdletter(origineel: str, vervanging: str) -> str:
    return vervanging[0].upper() + vervanging[1:] if origineel[0].isupper() else vervanging


def je_vorm(tekst: str) -> str:
    """`tekst` in de je-vorm; ongewijzigd als een u-vorm niet zeker om te zetten is."""
    nieuw = _GEINVERTEERD.sub(lambda m: _hoofdletter(m[1], _INVERSIE[m[1].lower()]) + " je", tekst)
    nieuw = _ONDERWERP.sub(lambda m: m[1] + _hoofdletter(m[2], "je") + " " + _NA_U.get(m[3], m[3]), nieuw)
    nieuw = _BEZITTELIJK.sub(lambda m: _hoofdletter(m[1], "je"), nieuw)
    return tekst if _U_VORM.search(nieuw) else nieuw
