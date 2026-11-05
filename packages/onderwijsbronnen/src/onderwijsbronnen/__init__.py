"""Open Nederlandse onderwijs- en arbeidsmarktbronnen in één pakket (#890, #910).

Per bron een subpakket: `cbs`, `duo`, `rio`, `roa`, `uwv`, `inspectie` en `sbb`; wat ze delen staat in `_kern`. Elk
bron-subpakket heeft dezelfde interface (`BRON`, `catalogusrecords()`, `laad`, `metadata()`, zie
`_kern.broncontract`). Een bron importeert alleen `_kern`, nooit een andere bron. Deze bovenlaag (dit bestand,
`contract` en `scope`) mag alle bronnen gebruiken.

    from onderwijsbronnen import duo, roa, uwv
    from onderwijsbronnen.cbs import data
    from onderwijsbronnen.rio import fetch, get, related

`riodata` en `onderwijsdata` blijven tijdens de overgang importeerbaar als shim (DeprecationWarning).
"""

from functools import cache

from . import cbs, duo, inspectie, rio, roa, sbb, uwv
from . import contract, scope
from ._kern.bron_id import BRONNEN, AmbigueBronId, BronId, BronIdFout, OnbekendBronId, Register, bron_van_sleutel
from ._kern.resolutie import AmbigueResource, ResourceNietGevonden
from ._kern.versie import VERSIE as __version__

# De volgorde van catalog(source="all") (zonder CBS: die catalogus staat apart in `cbs`).
_CATALOGUS_ALLES = ("rio", "duo", "roa", "uwv", "inspectie", "sbb")
_BRON = {"cbs": cbs, "rio": rio, "duo": duo, "roa": roa, "uwv": uwv, "inspectie": inspectie, "sbb": sbb}


def catalogus() -> dict[str, list[dict]]:
    """De samengevoegde catalogus (#912): per bron, in de volgorde van `BRONNEN`, haar catalogusrecords.

    Eén aanroep voor alle zeven bronnen, zodat een gebruiker (de chat) niet zelf twee catalogi samenvoegt. De records
    zijn die van `<bron>.catalogusrecords()`, ongewijzigd; elke aanroep geeft nieuwe lijsten.
    """
    return {bron: _BRON[bron].catalogusrecords() for bron in BRONNEN}


@cache
def register() -> Register:
    """Alle catalogus-ID's per bron (`<bron>.metadata(record)["id"]`), voor het ID-contract `bron:id`."""
    return Register({bron: [_BRON[bron].metadata(r)["id"] for r in records] for bron, records in catalogus().items()})


def parse_bron_id(tekst: str) -> BronId:
    """Het `BronId` (`bron:id`, in de spelling van de catalogus) achter elke ID-vorm; zie `_kern/bron_id.py`."""
    return BronId.parse(tekst, register())


def normaliseer_bron_id(tekst: str) -> str:
    """`str(parse_bron_id(tekst))`, bijvoorbeeld `cbs_85423ned` → `cbs:85423NED`."""
    return BronId.normaliseer(tekst, register())


def catalog(source: str = "rio", ai: bool = True, live: bool = False) -> list[dict]:
    """Geef catalogusrecords terug (alle bronnen behalve CBS; die staat in `cbs.catalog()`).

    Args:
        source: "rio"       — alleen RIO LOD API resources (lokale JSON, snel)
                "duo"       — alleen DUO datasets (lokale snapshot)
                "roa"       — alleen ROA arbeidsmarktdata
                "uwv"       — alleen UWV Open Match Data
                "inspectie" — alleen Inspectie van het Onderwijs datasets
                "sbb"       — alleen SBB kwalificatiestructuur datasets
                "all"       — alles gecombineerd
        ai:     Bij source="rio"/"all": gebruik AI-verrijkte beschrijvingen (default True).
        live:   Bij source="duo"/"all": haal DUO-records live op van CKAN i.p.v. lokale
                snapshot (default False). Vereist internetverbinding.
    """
    lezers = {
        "rio": lambda: rio.catalogusrecords(ai=ai),
        "duo": lambda: duo.catalogusrecords(live=live),
        "roa": roa.catalogusrecords,
        "uwv": uwv.catalogusrecords,
        "inspectie": inspectie.catalogusrecords,
        "sbb": sbb.catalogusrecords,
    }
    if source == "all":
        return [record for bron in _CATALOGUS_ALLES for record in lezers[bron]()]
    if source in lezers:
        return lezers[source]()
    raise ValueError(
        f"Ongeldige source '{source}'. "
        f"Kies 'rio', 'duo', 'roa', 'uwv', 'inspectie', 'sbb' of 'all'."
    )


__all__ = ["BRONNEN", "catalog", "catalogus", "register", "parse_bron_id", "normaliseer_bron_id", "bron_van_sleutel",
           "BronId", "BronIdFout", "OnbekendBronId", "AmbigueBronId", "Register", "cbs", "duo", "rio", "roa", "uwv",
           "inspectie", "sbb", "contract", "scope", "AmbigueResource", "ResourceNietGevonden", "__version__"]
