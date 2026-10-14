"""Wat in een antwoord geen lopende tekst is: code, links, HTML en linkreferenties (CH-11r, #445, #536).

De getalnotatie (`getalnotatie.py`) en de je-vorm (`aanspreekvorm.py`) passen alleen lopende tekst
aan: een getal of een 'u' in code, een linkdoel of een HTML-tag blijft zoals het model het schreef.
"""

import re
from collections.abc import Iterable, Iterator

# Ongemoeid: inline code (ook tussen dubbele backticks), links en hun doel, HTML-tags.
# Lineair: geen alternatief zoekt vanaf elk volgend begin opnieuw tot het einde van de regel.
# Een linkdoel mag één paar haakjes bevatten (wiki/Lijst_(12345)); elk teken past op één
# manier, dus terugzoeken blijft binnen dat ene doel.
BESCHERMD = re.compile(
    r"``[^\n]*?``|`[^`\n]*`|https?://[^\s<>()]+|www\.[^\s<>()]+|\]\((?:[^()\n]|\([^()\n]*\))*\)|<[^<>\n]+>"
)
CODEBLOK = re.compile(r"^\s*(```|~~~)")
REFERENTIE = re.compile(r" {0,3}\[[^\]\n]*\]:")  # [1]: /pad?n=12345


def lopende_regels(regels: Iterable[str]) -> Iterator[tuple[str, bool]]:
    """Elke regel met of het lopende tekst is: niet in een codeblok of op een hek ervan, geen linkreferentie."""
    in_codeblok = False
    for regel in regels:
        if hek := bool(CODEBLOK.match(regel)):
            in_codeblok = not in_codeblok
        yield regel, not (in_codeblok or hek or REFERENTIE.match(regel))
