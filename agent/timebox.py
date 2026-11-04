"""Een tijdsgrens per run (#90).

Runs liepen minutenlang door zonder dat de gebruiker wist of er nog iets gebeurde.
Na `traag_s` gaat het signaal `run_slow` naar de chat, die onder de voortgang zegt dat
het even kan duren (#599); na `grens_s` stopt de run zoals bij de stopknop, via het
stopsignaal. Een modelaanroep of tool die dat signaal niet ziet omdat hij vastzit,
breekt `afbreken_s` later af. Het einde van zo'n run zegt in `message_end` dat de grens
het deed, met de reden (#775): anders leek het op de stopknop.

De harde afbraak zelf (`afbreken_s` hier, `GENEREER_TIMEOUT_S` voor het rapport) loopt via
`harde_grens`: een modelaanroep die erdoor wordt afgebroken, ziet zo dat het de grens was en
geen annulering van buitenaf (#800).
"""

import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from .stream import Emit

# Een vastzittende aanroep krijgt na de grens nog even om netjes te stoppen.
_UITLOOP_S = 30

# De harde grens waarbinnen de huidige taak loopt; een contextvar, want de modelaanroep zit diep in de toolloop.
_harde_grens: ContextVar[asyncio.Timeout | None] = ContextVar("harde_grens", default=None)


@asynccontextmanager
async def harde_grens(seconden: float):
    """`asyncio.timeout(seconden)`, en daarbinnen weet `grens_verstreken` of een afbraak van deze grens komt (#800)."""
    async with asyncio.timeout(seconden) as grens:
        token = _harde_grens.set(grens)
        try:
            yield grens
        finally:
            _harde_grens.reset(token)


def grens_verstreken() -> bool:
    """Of de harde grens om de huidige taak verstreken is: een CancelledError is dan zijn afbraak."""
    grens = _harde_grens.get()
    return grens is not None and grens.expired()


@dataclass
class Timebox:
    stop: asyncio.Event
    grens_s: float
    verlopen: bool = False

    @property
    def afbreken_s(self) -> float:
        return self.grens_s + _UITLOOP_S

    def einde(self) -> dict:
        """Wat `message_end` erbij krijgt als de grens de run stopte, anders niets.

        Een eigen veld naast `aborted` (#775): de chat zet de reden als blijvende regel bij het
        bericht, met de knoppen om het opnieuw te proberen. Een toast van vier seconden zag wie
        na vijf minuten wachten even wegkeek niet, en zonder dit heette het "Genereren gestopt",
        net als na de stopknop.
        """
        if not self.verlopen:
            return {}
        minuten = max(1, round(self.grens_s / 60))
        reden = f"De vraag is na {minuten} min gestopt. Maak hem kleiner of specifieker, of probeer een ander model."
        return {"timeout": True, "stopreden": reden}


@asynccontextmanager
async def timebox(emit: Emit, stop: asyncio.Event, traag_s: float, grens_s: float):
    box = Timebox(stop, grens_s)

    # Een signaal, geen toast (#599): een toast verdween na vier seconden, dus wie even wegkeek zag
    # bij een lange vraag geen verwachting. De tekst staat in de chat, naast de klok die doorloopt.
    async def traag():
        await asyncio.sleep(traag_s)
        await emit({"type": "run_slow"})

    async def grens():
        await asyncio.sleep(grens_s)
        box.verlopen = True
        stop.set()

    taken = [asyncio.create_task(traag()), asyncio.create_task(grens())]
    try:
        yield box
    finally:
        for taak in taken:
            taak.cancel()
