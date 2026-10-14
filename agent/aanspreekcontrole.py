"""Zachte controle: een u-vorm die de code niet kon omzetten (#536, besluit #326).

De app spreekt de gebruiker aan met je. `aanspreekvorm.in_je_vorm` zet wat zeker kan om; deze
controle kijkt naar wat daarna nog over is. Zo kost alleen een u-vorm die de code niet kan
herstellen een herkansing (#409), en blijft hij daarna, dan is het een waarschuwing, nooit een
ingehouden antwoord: het gaat om de toon, niet om de data.

Een aparte module, want `probleem.meldingen` gebruikt `aanspreekvorm` en die mag `Probleem` dus
niet importeren.
"""

from .aanspreekvorm import in_je_vorm, overgebleven_u_vormen
from .antwoordtaal import Taal
from .probleem import Probleem

_MAX_ZINNEN = 3
_MAX_TEKENS = 160


def overgebleven_u_vorm(tekst: str, geschreven: Taal | None = None) -> list[Probleem]:
    """Zacht: een zin die na de omzetting nog u, uw of jullie zegt. Een Engels antwoord (`geschreven`) niet."""
    if geschreven == "en" or not (zinnen := overgebleven_u_vormen(in_je_vorm(tekst))):
        return []
    melding = (
        "Een zin spreekt je aan met u of jullie in plaats van met je."
        if len(zinnen) == 1
        else f"{len(zinnen)} zinnen spreken je aan met u of jullie in plaats van met je."
    )
    citaten = "; ".join(repr(zin[:_MAX_TEKENS]) for zin in zinnen[:_MAX_ZINNEN])
    return [Probleem(melding, f"Spreek de gebruiker aan met je/jij, niet met u, uw of jullie. Herschrijf: {citaten}.")]
