"""Je-vorm in de verduidelijkingsvraag (#341, UX-10.2), het eindantwoord, het rapport en de meldingen (#536).

De app spreekt de gebruiker aan met je (besluit #326); het model schrijft in de clarify-vraag
soms 'Welk schooljaar bedoelt u?'. Na inversie verandert het werkwoord ('wilt u'
wordt 'wil je', 'heeft u' wordt 'heb je'), maar 'moet u' blijft 'moet je'. Dat is
zonder woordenboek niet te raden, dus alleen werkwoorden uit de lijst worden
omgezet. Blijft er daarna nog een u-vorm over, dan gaat de tekst ongewijzigd terug:
liever 'u' dan kapot Nederlands.

`in_je_vorm` doet dat voor een langere tekst per zin: één onzekere zin houdt de rest niet
tegen, en na een lijstteken of kop begint de zin ook. Code, links (ook de linktekst: vaak de
titel van een pagina, dus een citaat) en HTML blijven ongemoeid. Alleen 'jullie' vóór
instelling, opleiding(en) of school wordt 'je'; elk ander 'jullie' blijft staan.
`overgebleven_u_vormen` vindt wat daarna nog over is, voor de controle in `aanspreekcontrole.py`.

Alles loopt in lineaire tijd, zoals de getalnotatie: het draait synchroon op het eindantwoord.
"""

import re

from .beschermd import BESCHERMD, lopende_regels

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


# Een hele markdownlink: de linktekst is vaak de titel van een pagina, dus een citaat.
_LINK = r"\[[^\[\]\n]*\]\((?:[^()\n]|\([^()\n]*\))*\)"
_NIET_OMZETTEN = re.compile(rf"{_LINK}|{BESCHERMD.pattern}")
# Staat voor een beschermd stuk tijdens de omzetting: geen woordteken, dus nooit een u-vorm of werkwoord.
_PLAATS = "\ue000"
# Een zin eindigt op . ! ? of : met witruimte erna, ook achter een vetgedrukte kop ("**Let op:** u kunt").
_ZINSGRENS = re.compile(r"(?<=[.!?:])(\*{0,2}\s+)")
# Wat vóór het eerste woord van een zin staat: lijstteken, kop, citaat, haakje, nadruk.
_ZINSBEGIN = re.compile(r"(?:[\s>#*+\-_\"'“‘„(]|\d{1,3}[.)]\s)*")
# 'jullie' alleen waar de instelling of opleiding van de gebruiker bedoeld is.
_JULLIE = re.compile(r"\b(jullie)(?=\s+(?:eigen\s+)?(?:instelling|opleidingen?|school)\b)", re.IGNORECASE)
# Een u-vorm of 'jullie' als los woord; niet in een afkorting (U.S., a.u.b.) of samenstelling (U-bocht).
_OVERGEBLEVEN = re.compile(r"(?<![\w.-])(?:[uU]w?|(?i:jullie))(?![\w-])(?!\.\w)")


def _zin_in_je_vorm(zin: str) -> str:
    begin = m.end() if (m := _ZINSBEGIN.match(zin)) else 0
    kern = je_vorm(_JULLIE.sub(lambda m: _hoofdletter(m[1], "je"), zin[begin:]))
    return zin if _U_VORM.search(kern) else zin[:begin] + kern


def _regel_in_je_vorm(regel: str) -> str:
    if _PLAATS in regel:  # dan is een beschermd stuk niet terug te zetten
        return regel
    beschermd = [m.group(0) for m in _NIET_OMZETTEN.finditer(regel)]
    stukken = _ZINSGRENS.split(_NIET_OMZETTEN.sub(_PLAATS, regel))
    stukken[::2] = [_zin_in_je_vorm(zin) for zin in stukken[::2]]
    terug = iter(beschermd)
    return re.sub(_PLAATS, lambda _: next(terug), "".join(stukken))


def in_je_vorm(tekst: str) -> str:
    """Lopende tekst in de je-vorm, per zin; een zin met een u-vorm die niet zeker om te zetten is, blijft gelijk."""
    return "\n".join(_regel_in_je_vorm(r) if lopend else r for r, lopend in lopende_regels(tekst.split("\n")))


def overgebleven_u_vormen(tekst: str) -> list[str]:
    """De zinnen van de lopende tekst met nog een u, uw of jullie; code, links en HTML tellen niet mee."""
    zinnen = [
        zin.strip()
        for regel, lopend in lopende_regels(tekst.split("\n"))
        if lopend
        for zin in _ZINSGRENS.split(_NIET_OMZETTEN.sub("…", regel))[::2]
        if _OVERGEBLEVEN.search(zin)
    ]
    return list(dict.fromkeys(zinnen))
