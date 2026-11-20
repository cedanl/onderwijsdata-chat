"""De onderwijslicenties van een instelling in RIO v3, op een peildatum (#1060).

Een licentie zegt dat een instelling een erkende opleiding mag verzorgen, met een ``begindatum`` en ``einddatum``. RIO
kent geen relatie "opvolger" tussen opleidingen, maar de licenties van twee dagen naast elkaar laten zien welke
opleiding er sinds de ene dag bij kwam en welke verdween. Zo zette Avans (07GR) Informatica (34479, einde 2026-09-01)
om naar HBO-ICT (30020, begin 2026-09-01); gemeten op 19-11-2026: 58 licenties op 2025-10-01, 62 vandaag.

``/erkenningen/{brin}/onderwijslicenties?datumGeldigOp=…`` geeft de licenties zonder opleidingscode; die staat in de
opleidingserkenning achter de link ``opleidingserkenning`` (één aanroep per licentie): ``erkendeopleidingscode`` (de
CROHO-code in het ho), ``onderdeel`` (TECHNIEK, ...), ``ingangsdatum`` en ``instroomEinddatum``. De lijst kent geen
``page``-parameter (HTTP 400); ``related`` volgt de next-links.

Elke aanroep geeft ``datumGeldigOp`` mee. Een bronfout gaat naar de aanroeper; bewaren (cache) doet de aanroeper.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, replace

from .client import link, related


@dataclass(frozen=True)
class Licentie:
    """Eén onderwijslicentie van een instelling op een peildatum.

    ``begindatum`` en ``einddatum`` zijn jjjj-mm-dd (``einddatum`` None: loopt door). ``erkenning`` is de link naar de
    opleidingserkenning; ``croho``, ``onderdeel`` en ``instroom_einddatum`` zijn None tot ``met_erkenning`` ze invult.
    """

    id: str
    begindatum: str | None
    einddatum: str | None
    erkenning: str | None
    croho: str | None = None
    onderdeel: str | None = None
    instroom_einddatum: str | None = None


def _iso(datum: dt.date | str | None) -> str:
    if datum is None:
        return dt.date.today().isoformat()
    return datum.isoformat() if isinstance(datum, dt.date) else str(datum)


def onderwijslicenties(brin: str, peildatum: dt.date | str | None = None) -> tuple[Licentie, ...]:
    """De licenties van erkenning ``brin`` die op ``peildatum`` (standaard vandaag) gelden, zonder hun erkenning.

    Eén aanroep (plus een per volgende pagina); leeg als RIO er geen kent.
    """
    uit = []
    for item in related("erkenningen", brin, "onderwijslicenties", datumGeldigOp=_iso(peildatum)):
        href = item.get("_links", {}).get("opleidingserkenning", {}).get("href")
        uit.append(Licentie(str(item["id"]), item.get("begindatum"), item.get("einddatum"), href))
    return tuple(uit)


def met_erkenning(licentie: Licentie) -> Licentie:
    """De licentie met de CROHO-code, het onderdeel en de instroomeinddatum uit haar opleidingserkenning (één aanroep).

    De link draagt al de ``datumGeldigOp`` van de lijst waar de licentie uit kwam. Zonder link blijft ze zoals ze is.
    """
    if not licentie.erkenning:
        return licentie
    erkenning = link(licentie.erkenning)
    code = erkenning.get("erkendeopleidingscode")
    return replace(
        licentie,
        croho=str(code) if code is not None else None,
        onderdeel=erkenning.get("onderdeel"),
        instroom_einddatum=erkenning.get("instroomEinddatum"),
    )
