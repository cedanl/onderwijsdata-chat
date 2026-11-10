"""Een CBS-periodecode in de lopende tekst van het antwoord als leesbaar jaar (#989, reaudit 10-11 A04).

`get_maat` geeft naast `Perioden: "2023SJ00"` het label `"2023/'24"`; het model schreef soms toch de code
in de tekst. Hier gebeurt de omzetting in code, zodat het niet van de formulering afhangt: een schooljaar
`2023SJ00` wordt 2023/24 (`periode.label`), een kalenderjaar `2023JJ00` wordt 2023.

Andere codes blijven staan: een kwartaal (2023KW01), een maand (2023MM01) en een ander volgnummer dan 00
(2023SJ01). Code, links en HTML ook (`beschermd.py`): een code die de gebruiker moet zien, staat daarin.
"""

import re

from tools import periode

from .beschermd import BESCHERMD, lopende_regels

# Niet aan een letter, cijfer of underscore vast: 12023SJ00 en 2023SJ00X zijn geen periodecode.
_PERIODECODE = re.compile(r"(?<!\w)([0-9]{4})(SJ|JJ)00(?!\w)")


def _als_label(m: re.Match) -> str:
    if m.group(2) == "JJ":
        return m.group(1)
    startjaar = periode.startjaar("cbs", m.group(0))
    return periode.label(startjaar) if startjaar is not None else m.group(0)


def _in_tekst(tekst: str) -> str:
    """De labels in een stuk lopende tekst, buiten code, links en HTML."""
    stukken, vorige = [], 0
    for m in BESCHERMD.finditer(tekst):
        stukken += [_PERIODECODE.sub(_als_label, tekst[vorige : m.start()]), m.group(0)]
        vorige = m.end()
    return "".join([*stukken, _PERIODECODE.sub(_als_label, tekst[vorige:])])


def periodecode_als_label(tekst: str) -> str:
    """`tekst` met elke CBS-periodecode voor een schooljaar of kalenderjaar in de lopende tekst als label."""
    return "\n".join(_in_tekst(regel) if lopend else regel for regel, lopend in lopende_regels(tekst.split("\n")))
