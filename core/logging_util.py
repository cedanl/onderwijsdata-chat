"""Wat het log van gebruikers- en antwoordtekst mag weten (#475).

Het stdout-log gaat naar de logaggregatie en valt buiten "gesprek verwijderen". Op
INFO en hoger staat daarom geen vraag, antwoord of toolargument, alleen de lengte en
een korte hash: genoeg om een regel aan een gesprek in de database te koppelen. De
tekst zelf mag alleen op DEBUG.
"""

import hashlib


def tekst_kenmerk(tekst: str, prefix: str = "") -> str:
    """``len=<n> hash=<8 hex>`` van *tekst*; met *prefix* ``vraag_`` wordt het ``vraag_len=… vraag_hash=…``.

    Een afgekapte SHA-256, niet ``hash()``: die verschilt per proces en is dus niet te correleren.
    """
    digest = hashlib.sha256(tekst.encode("utf-8", "surrogatepass")).hexdigest()[:8]
    return f"{prefix}len={len(tekst)} {prefix}hash={digest}"
