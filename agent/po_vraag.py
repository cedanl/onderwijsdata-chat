"""Een vraag over po, so of vo krijgt de scope-uitleg uit code, vóór elke kaart en vóór het model (#647).

"Hoeveel leerlingen zitten er in groep 8?" ging naar het model. Dat bood het totaal basisonderwijs uit
85701NED aan, deed daarvoor een `get_cbs_data`-ronde (de po-rijen haalt `CBS_SECTORFILTER` er toch uit),
en bij "basisschool in Utrecht" kwam eerst de plaatskaart. De scope is mbo/hbo/wo (#355): code beslist
(#191) en geeft de vaste `SCOPE_UITLEG`, zonder modelronde, toolaanroep of kaart.

Een po/so/vo-woord (`scopeprofiel.PO_SO_VO`) is het begin. Een treffer die alleen "so" of "bo" is, beslist
niet: dat is ook Engels ("So, what can you tell me?") of een naam. Noemt de vraag ook het ho, het mbo, studenten,
eerstejaars (`ho_markers`) of een registerinstelling, dan is het een ho-vraag met vo-context en blijft ze bij
het model (epic #554). Dat geldt ook als het vorige gebruikersbericht dat doet: "En hoeveel van het havo?" na
"Hoeveel hbo-studenten zijn er?" vraagt door op ho. Elke treffer betekent de oude weg (fail open), die via
de scopegrens en `CBS_SECTORFILTER` veilig blijft.

Het register laadt als laatste, en alleen als de woorden niets beslisten. Zonder register (offline) noemt
een vraag geen registerinstelling (`instelling.noemt_instelling`): dan beslissen de woorden alleen.
"""

from __future__ import annotations

from tools import instelling, scopeprofiel
from tools.ho_markers import HO_MBO_CONTEXT, noemt_ho

from .vaste_antwoorden import SCOPE_UITLEG

# Ook Engels of een naam: alleen zo'n treffer maakt een vraag geen po/so/vo-vraag.
_DUBBELZINNIG = frozenset({"so", "bo"})


def _noemt_po_so_vo(vraag: str) -> bool:
    return any(m.group().lower() not in _DUBBELZINNIG for m in scopeprofiel.PO_SO_VO.finditer(vraag))


def _ho_context(tekst: str) -> bool:
    """Noemt de tekst het ho, het mbo, studenten of eerstejaars? Alleen woorden, zonder register."""
    return noemt_ho(tekst) or bool(HO_MBO_CONTEXT.search(tekst))


def po_vraag(vraag: str, vorige_vraag: str = "") -> str | None:
    """De vaste scope-uitleg als de vraag po, so of vo noemt zonder ho-context; anders None.

    `vorige_vraag` is het gebruikersbericht ervoor. Het register laadt alleen als de woorden niets
    beslisten, maar dan over het netwerk: roep dit vanuit async code aan via `asyncio.to_thread`.
    """
    teksten = [t for t in (vraag, vorige_vraag) if t]
    if not _noemt_po_so_vo(vraag) or any(_ho_context(t) for t in teksten):
        return None
    if any(instelling.noemt_instelling(t) for t in teksten):
        return None
    return SCOPE_UITLEG
