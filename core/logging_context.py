"""Eén verbindings-ID op elke logregel van een chatverbinding (#502).

In `run()` is het gespreks-ID van de frontend niet bekend (dat kiest de client en komt pas
mee bij het opslaan), dus regels waren niet aan elkaar te koppelen. Elke WebSocket-verbinding
krijgt bij het openen een kort willekeurig ID in een ContextVar; taken en threads die de
verbinding start (asyncio.create_task, asyncio.to_thread) erven de context, dus de agent,
de tools en de controles loggen hetzelfde ID. Geen gebruikersnaam en geen tekst: het ID
zegt alleen welke regels bij elkaar horen.
"""

import logging
import uuid
from contextvars import ContextVar

GEEN = "-"
verbinding: ContextVar[str] = ContextVar("verbinding", default=GEEN)


def nieuwe_verbinding() -> str:
    """Geef deze context een vers verbindings-ID en geef het terug."""
    vid = uuid.uuid4().hex[:8]
    verbinding.set(vid)
    return vid


class VerbindingFilter(logging.Filter):
    """Zet het verbindings-ID van de huidige context op elk record, als `record.verbinding`."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.verbinding = verbinding.get()
        return True
