"""Modeltekst met gewone tekens (#326).

gpt-oss schrijft getallen en namen met U+202F (smalle vaste spatie) en gebruikt U+2011
(vast koppelteken) als minteken. De gebruiker zag vreemde tekens en kon niet zoeken of
kopiëren zonder rommel. De grondingscontrole kent die spaties als duizendtalscheiding;
na normalisatie herkent hij de gewone spatie net zo.
"""

_VERVANGINGEN = str.maketrans(
    {
        "\u202f": " ",  # smalle vaste spatie
        "\u00a0": " ",  # vaste spatie
        "\u2011": "-",  # vast koppelteken
    }
)


def normaliseer(tekst: str) -> str:
    return tekst.translate(_VERVANGINGEN)
