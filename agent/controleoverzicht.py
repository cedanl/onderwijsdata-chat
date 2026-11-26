"""Wat de antwoordcontrole bij een data-antwoord deed, als veld `controles` op `message_end` (#1260).

Onder elk data-antwoord staat de regel "Wat is gecontroleerd" (frontend/src/controleRegel.js). Die leest alleen dit
veld, uit code: welke controle draaide, hoeveel getallen tegen de data zijn gelegd, of jaar en instelling zijn
nagelopen, en hoe vaak het antwoord na de controle is ingetrokken of gecorrigeerd. Wat het model over zijn eigen
controle schrijft ("alle getallen gecontroleerd"), verandert hier niets aan. Alleen tellingen: geen tekst van het
antwoord, geen getallen eruit.
"""

from collections.abc import Mapping

from .controles import leestekst
from .grounding import getoetste_getallen

# De uitkomst van een controle die zelf niet kon draaien (agent/probleem.py, `uitkomsten`).
_NIET_GEDRAAID = "niet gecontroleerd"
# De controles die een getal aan het jaar en de instelling van zijn rij binden (#187, #197): zijn ze alle drie gedraaid,
# dan zijn jaar en instelling nagelopen.
JAAR_EN_INSTELLING = ("ontbrekende_schooljaren", "ontbrekende_instellingen", "verkeerd_gebonden")


def overzicht(
    per_controle: Mapping[str, str],
    antwoord: str,
    citaties: list[dict] | None,
    ingetrokken: int,
    gecorrigeerd: int,
) -> dict:
    """Het veld `controles`: per controle of ze draaide en wat ze gaf, en de tellingen voor de regel.

    `antwoord` is de modeltekst waarop de laatste controle draaide; `citaties` de getallen met hun herkomst
    (agent/citaties.py); `ingetrokken` hoe vaak het antwoord na de controle opnieuw is geschreven, `gecorrigeerd` hoe
    vaak de app er zelf zinnen uit haalde (#619)."""
    gedraaid = {naam: uitkomst != _NIET_GEDRAAID for naam, uitkomst in per_controle.items()}
    return {
        "per_controle": {
            naam: {"gedraaid": gedraaid[naam], "uitkomst": uitkomst} for naam, uitkomst in per_controle.items()
        },
        "getallen": getoetste_getallen(leestekst(antwoord)) if antwoord else 0,
        "gebonden": sum(1 for c in citaties or [] if c.get("vastgesteld")),
        "jaar_en_instelling": bool(per_controle) and all(gedraaid.get(naam, False) for naam in JAAR_EN_INSTELLING),
        "niet_gedraaid": sum(1 for g in gedraaid.values() if not g),
        "ingetrokken": ingetrokken,
        "gecorrigeerd": gecorrigeerd,
    }
