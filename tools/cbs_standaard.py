"""Een vaste standaardselectie per CBS-tabel, uit code (#653).

Dezelfde vraag "vmbo → mbo" telde op 19-10 de mbo-instromers inclusief extranei (83.020 van 157.450) en op 20-10
exclusief (82.780 van 155.270). Beide cijfers klopten en waren gelabeld, maar de keuze maakte het model, per run
anders. Gelijke vragen horen gelijke getallen te geven (#191: code beslist), dus bij de mbo-tabellen die in Leerweg
beide totalen hebben, kiest de code de ruimste telling: "Totaal mbo (incl. extranei)". De smallere telling blijft
alleen staan als de gebruiker extranei in het gesprek uitsluit ("zonder extranei", "bol en bbl"). Buiten de chat
(MCP, evals) is er geen gesprek en geldt de code die de aanroeper koos.

Het model kiest alleen het totaal van de smallere telling niet meer zelf: uitsplitsen (`*`), bol, bbl, extranei of
meer codes tegelijk blijven zoals het ze koos.
"""

import contextlib
import re
from collections.abc import Generator, Iterable
from contextvars import ContextVar
from dataclasses import dataclass

from .canoniek import zonder_cbs_prefix


@dataclass(frozen=True)
class Standaard:
    dimensie: str
    code: str  # de ruimste telling: de standaard
    label: str
    smaller: str  # de smallere telling: alleen als de gebruiker erom vraagt
    smaller_label: str
    uitsluiting: re.Pattern[str]  # hoe een gebruiker de smallere telling kiest

    def alternatief(self, selectie: dict, *, beide: bool) -> dict:
        """De selectie met de smallere telling (#658): alleen die, of samen met de standaard in één aanroep."""
        dimensies = selectie["dimensies"]
        codes = [self.code, self.smaller] if beide else self.smaller
        return {**selectie, "dimensies": {**dimensies, self.dimensie: codes}}

    def uitleg(self) -> str:
        """Voor het model, als de code zijn keuze verving: waarom de telling anders is dan gevraagd."""
        return (
            f"{self.dimensie} staat op {self.code} '{self.label}' in plaats van {self.smaller} "
            f"'{self.smaller_label}': de vaste standaard van deze tabel (#653). De telling zonder extranei alleen "
            "als de gebruiker daarom vraagt; die staat dan klaar in `alternatieve_telling`."
        )


_ZONDER_EXTRANEI = re.compile(
    r"\b(?:zonder|excl(?:\.|usief)?|geen|behalve)\s+(?:de\s+)?extranei\b"
    r"|\bextranei\s+(?:niet|uitgesloten|buiten\s+beschouwing)\b"
    r"|\bbol\s*(?:en|\+|&)\s*bbl\b",
    re.IGNORECASE,
)
_EXTRANEI = Standaard(
    "Leerweg", "A025290", "Totaal mbo (incl. extranei)", "A041867", "Totaal mbo (excl. extranei)", _ZONDER_EXTRANEI
)
# De opvraagbare CBS-tabellen waarvan Leerweg zowel A025290 als A041867 kent (alle catalogustabellen nagelopen,
# 21-10-2026). Andere tabellen hebben er hooguit één van, vaak in een andere dimensie, en dus niets te kiezen.
TABELLEN = (
    "83850NED",
    "83851NED",
    "83852NED",
    "83895NED",
    "83896NED",
    "83897NED",
    "85352NED",
    "85353NED",
    "85354NED",
    "85355NED",
    "85356NED",
    "85357NED",
    "85569NED",
    "85574NED",
)
_STANDAARD = {tabel.lower(): _EXTRANEI for tabel in TABELLEN}

# De vragen van de gebruiker in dit gesprek; taken en threads van de beurt erven ze (asyncio.to_thread).
_gespreksvragen: ContextVar[tuple[str, ...] | None] = ContextVar("gespreksvragen", default=None)


@contextlib.contextmanager
def gesprek(vragen: Iterable[str]) -> Generator[None, None, None]:
    """Binnen dit blok geldt de standaardselectie, tenzij een van `vragen` haar uitsluit."""
    token = _gespreksvragen.set(tuple(vragen))
    try:
        yield
    finally:
        _gespreksvragen.reset(token)


def _gepind(waarde) -> str | None:
    """De ene code waarop een dimensie gepind is; None bij `*`, bij meer codes of zonder code."""
    codes = waarde if isinstance(waarde, list) else [waarde]
    return str(codes[0]).strip() if len(codes) == 1 else None


def toegepast(dataset_id: str, selectie: dict) -> tuple[dict, Standaard | None]:
    """De selectie met de standaard in plaats van de smallere telling, en de standaard als die iets verving.

    De selectie van het model zelf blijft ongemoeid: de cache van de beurt en de toolstap tonen wat het vroeg.
    """
    standaard = _STANDAARD.get(zonder_cbs_prefix(dataset_id).lower())
    vragen = _gespreksvragen.get()
    dimensies = selectie.get("dimensies") if isinstance(selectie, dict) else None
    if (
        standaard is None
        or vragen is None
        or not isinstance(dimensies, dict)
        or _gepind(dimensies.get(standaard.dimensie)) != standaard.smaller
        or any(standaard.uitsluiting.search(vraag) for vraag in vragen)
    ):
        return selectie, None
    return {**selectie, "dimensies": {**dimensies, standaard.dimensie: standaard.code}}, standaard
