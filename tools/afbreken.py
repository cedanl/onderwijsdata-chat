"""Een lopende tool afbreken als de gebruiker stopt (#1087).

De toolloop draait elke tool in een thread (`asyncio.to_thread`). Een thread is niet te annuleren: bij een stop wacht de
loop er niet meer op, maar wat de tool deed liep door, bij `run_analysis` tot de sandboxgrens van 10 seconden. De loop
geeft elke tool daarom een `threading.Event` mee dat hij zet als de run wordt afgebroken. Een tool die lang werkt in een
proces dat hij kan stoppen (`tools.sandbox`), kijkt ernaar en stopt zelf; een tool die dat niet kan (een bronaanroep)
loopt af en zijn uitkomst gaat verloren.

Het signaal zit in een `ContextVar`: `to_thread` neemt de context mee, dus de tool vindt het zonder extra argument.
"""

import asyncio
import threading
from collections.abc import Callable
from contextvars import ContextVar
from typing import Any, TypeVar

T = TypeVar("T")

_signaal: ContextVar[threading.Event | None] = ContextVar("afbreken", default=None)


async def in_thread(functie: Callable[..., T], *args: Any) -> T:
    """`functie(*args)` in een thread, met een afbreeksignaal dat gezet wordt als de aanroep wordt geannuleerd."""
    signaal = threading.Event()
    token = _signaal.set(signaal)
    try:
        return await asyncio.to_thread(functie, *args)
    except asyncio.CancelledError:
        signaal.set()
        raise
    finally:
        _signaal.reset(token)


def gevraagd() -> bool:
    """Is de tool die hier draait afgebroken? Altijd False buiten `in_thread`."""
    signaal = _signaal.get()
    return signaal is not None and signaal.is_set()
