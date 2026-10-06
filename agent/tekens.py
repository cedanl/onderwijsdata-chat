"""Modeltekst met gewone tekens (#326).

gpt-oss schrijft getallen en namen met U+202F (smalle vaste spatie) en gebruikt U+2011
(vast koppelteken) als minteken. De gebruiker zag vreemde tekens en kon niet zoeken of
kopiëren zonder rommel. De grondingscontrole kent die spaties als duizendtalscheiding;
na normalisatie herkent hij de gewone spatie net zo.

Opus begint een antwoord soms met lege regels en een citaatblok
"> **Onderzoeksvraag** ..." (#405); `zonder_citaatkop` maakt daar een gewone
alinea van.
"""

import re

_VERVANGINGEN = str.maketrans(
    {
        "\u202f": " ",  # smalle vaste spatie
        "\u00a0": " ",  # vaste spatie
        "\u2011": "-",  # vast koppelteken
    }
)


def normaliseer(tekst: str) -> str:
    return tekst.translate(_VERVANGINGEN)


# Het eerste blok, als dat een citaat is dat met **Onderzoeksvraag** begint.
_CITAATKOP = re.compile(r"\A\s*(>\s*\*\*Onderzoeksvraag\*\*.*?)(?=\n[ \t]*\n|\Z)", re.DOTALL)


def zonder_citaatkop(tekst: str) -> str:
    """Een openingscitaat met de onderzoeksvraag als gewone alinea, zonder lege regels ervoor."""
    if not (kop := _CITAATKOP.match(tekst)):
        return tekst
    return re.sub(r"^[ \t]*>[ \t]?", "", kop.group(1), flags=re.MULTILINE) + tekst[kop.end() :]
