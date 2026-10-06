"""Een tijdsgrens per run (#90).

Runs liepen minutenlang door zonder dat de gebruiker wist of er nog iets gebeurde.
Na `traag_s` zegt een melding dat lang duren normaal is en dat stoppen kan; na
`grens_s` stopt de run zoals bij de stopknop, via het stopsignaal. Een modelaanroep
of tool die dat signaal niet ziet omdat hij vastzit, breekt `afbreken_s` later af.
"""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass

from .stream import Emit

# Een vastzittende aanroep krijgt na de grens nog even om netjes te stoppen.
_UITLOOP_S = 30


@dataclass
class Timebox:
    stop: asyncio.Event
    grens_s: float
    verlopen: bool = False

    @property
    def afbreken_s(self) -> float:
        return self.grens_s + _UITLOOP_S

    def melding(self) -> dict:
        minuten = max(1, round(self.grens_s / 60))
        return {
            "type": "toast",
            "message": f"De vraag is na {minuten} min gestopt. Maak hem kleiner of specifieker, of probeer een ander model.",
            "level": "warning",
        }


@asynccontextmanager
async def timebox(emit: Emit, stop: asyncio.Event, traag_s: float, grens_s: float):
    box = Timebox(stop, grens_s)

    async def traag():
        await asyncio.sleep(traag_s)
        await emit(
            {
                "type": "toast",
                "message": "Dit duurt langer dan normaal. Bij complexe vragen kan dat; met de stopknop breek je af.",
                "level": "info",
            }
        )

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
