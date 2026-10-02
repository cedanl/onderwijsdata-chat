"""Bindt een gekozen verduidelijkingsoptie aan het antwoord (#246).

Audit 11: de gebruiker koos "2023 (laatste beschikbare werkelijke cijfers)", het
antwoord vergeleek toch met 2018 uit een bestand dat bij 2018 ophoudt. Elk getal
kwam uit een tool, dus de getalcontrole zweeg. Een jaar uit een keuze is
afbakening: het antwoord gebruikt het, of zegt dat het in de data ontbreekt.
In beide gevallen staat het jaar in de tekst; een stil ander jaar niet.
"""

import re

from tools import periode

_JAAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")


def _genoemd(jaar: int, tekst: str) -> bool:
    return re.search(rf"(?<!\d){jaar}(?!\d)", tekst) is not None


def genegeerde_keuze(keuzes: list[str], tekst: str) -> list[str]:
    """Jaren uit de gekozen opties van deze beurt die het antwoord niet noemt.

    Een schooljaar ("2023/24") moet als schooljaar terugkomen, een los jaar ("2023")
    als dat jaar in welke vorm ook.
    """
    in_tekst = periode.gevraagde_schooljaren(tekst)
    problemen = []
    for keuze in keuzes:
        if schooljaren := periode.gevraagde_schooljaren(keuze):
            ontbreekt = [periode.label(j) for j in sorted(schooljaren - in_tekst)]
        else:
            ontbreekt = [j for j in dict.fromkeys(_JAAR.findall(keuze)) if not _genoemd(int(j), tekst)]
        problemen += [
            f"De gebruiker koos '{keuze}', maar het antwoord noemt {jaar} niet. Gebruik die periode, "
            f"of zeg expliciet dat {jaar} niet in de data staat; kies niet stil een ander jaar."
            for jaar in ontbreekt
        ]
    return problemen
