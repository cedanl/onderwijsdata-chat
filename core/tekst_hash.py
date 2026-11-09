"""De sleutel van een antwoord in `beurtbewijs` (ADR-009): sha256 (hex) van zijn UTF-8-tekst.

Hier en niet in `agent/beurtbewijs.py`, omdat ook de feedbacktrace (`core/answer_feedback.py`) een antwoord aan zijn
rij koppelt, zonder de agent te importeren.
"""

import hashlib


def tekst_hash(tekst: str) -> str:
    """sha256 (hex) van de UTF-8-tekst. Een onbruikbaar teken breekt de hash niet."""
    return hashlib.sha256(tekst.encode("utf-8", errors="replace")).hexdigest()
