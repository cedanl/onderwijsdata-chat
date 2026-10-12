"""Wat het log van gebruikers- en antwoordtekst mag weten (#475, #502).

Het stdout-log gaat naar de logaggregatie en valt buiten "gesprek verwijderen". Op
INFO en hoger staat daarom geen vraag, antwoord, toolargument of fouttekst die zulke
tekst kan citeren, alleen de lengte en een korte hash: genoeg om een regel aan een
gesprek in de database te koppelen. De tekst zelf mag alleen op DEBUG.

Met LOG_HASH_SECRET (een serverzijdig geheim, via SOPS/Flux, nooit in de repo) is de hash
een HMAC: wie het log heeft, kan dan geen geraden vraag tegen de hash controleren. Zonder
geheim blijft het een kale SHA-256, zoals in de demo-fase.
"""

import hashlib
import hmac
import os

_SECRET = os.getenv("LOG_HASH_SECRET", "").encode()


def _digest(tekst: str) -> str:
    data = tekst.encode("utf-8", "surrogatepass")
    if _SECRET:
        return hmac.new(_SECRET, data, hashlib.sha256).hexdigest()[:8]
    return hashlib.sha256(data).hexdigest()[:8]


def tekst_kenmerk(tekst: str, prefix: str = "") -> str:
    """``len=<n> hash=<8 hex>`` van *tekst*; met *prefix* ``vraag_`` wordt het ``vraag_len=… vraag_hash=…``.

    Een afgekapte SHA-256 (of HMAC met LOG_HASH_SECRET), niet ``hash()``: die verschilt per
    proces en is dus niet te correleren.
    """
    return f"{prefix}len={len(tekst)} {prefix}hash={_digest(tekst)}"


def foutkenmerk(e: BaseException) -> str:
    """Het type van een uitzondering met het kenmerk van haar tekst: ``ValueError fout_len=… fout_hash=…``.

    Een fouttekst van een tool, de sandbox of een provider kan toolargumenten of modeltekst
    citeren; op INFO en hoger alleen dit, de tekst zelf op DEBUG.
    """
    return f"{type(e).__name__} {tekst_kenmerk(str(e), 'fout_')}"
