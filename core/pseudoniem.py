"""Een pseudoniem voor een accountnaam of adres dat de database in gaat (#1112, #1117; AVG art. 25 en 32).

Een accountnaam is met SRAM een e-mailadres en een IPv4-adres telt hooguit 2^32 waarden: een kale SHA-256 ervan is met
één hash terug te rekenen. Wat in `tokengebruik` en `rate_limit_hits` komt, is daarom een HMAC met een servergeheim,
zoals `core.logging_util.gebruiker_kenmerk` voor het log.

Het geheim is `CHAT_SECRET`, dat elke omgeving met een login al heeft (core/auth.py); de sleutel van het pseudoniem is
daar met een vaste context van afgeleid, zodat de handtekening van een sessietoken en het pseudoniem nooit dezelfde
HMAC-sleutel gebruiken. Roteer je `CHAT_SECRET`, dan verlopen de sessies en beginnen de tellers van het budget en de
limieten opnieuw: de oude rijen zijn niet meer aan een account te koppelen en verlopen vanzelf.

`config.py` waarschuwt buiten `local` als `CHAT_SECRET` leeg is: dan is het pseudoniem met een bekende sleutel te
berekenen. De voorloop `h1:` is de versie van deze afleiding; zo is een rij van vóór #1112 (kale hash) te herkennen.
"""

import hashlib
import hmac
import os

VERSIE = "h1:"
_CONTEXT = b"openEDUdata+ pseudoniem v1"


def _sleutel() -> bytes:
    return hmac.new(os.getenv("CHAT_SECRET", "").encode(), _CONTEXT, hashlib.sha256).digest()


def pseudoniem(domein: str, waarde: str) -> str:
    """`h1:` en de HMAC-SHA256 van `waarde` binnen `domein`.

    Het domein (bijvoorbeeld `tokengebruik`) hoort bij de HMAC, zodat dezelfde accountnaam in twee tabellen twee
    verschillende pseudoniemen geeft en de tabellen niet aan elkaar te koppelen zijn.
    """
    bericht = f"{domein}\0{waarde}".encode("utf-8", "surrogatepass")
    return VERSIE + hmac.new(_sleutel(), bericht, hashlib.sha256).hexdigest()
