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

from . import cbs, duo, inspectie, rio, roa, sbb, uwv
from . import contract, scope
from ._kern.resolutie import AmbigueResource, ResourceNietGevonden
from ._kern.versie import VERSIE as __version__

# Alle bronnen, en de volgorde van catalog(source="all") (zonder CBS: die catalogus staat apart in `cbs`).
BRONNEN = ("cbs", "rio", "duo", "roa", "uwv", "inspectie", "sbb")
_CATALOGUS_ALLES = ("rio", "duo", "roa", "uwv", "inspectie", "sbb")


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


__all__ = ["BRONNEN", "catalog", "cbs", "duo", "rio", "roa", "uwv", "inspectie", "sbb", "contract", "scope",
           "AmbigueResource", "ResourceNietGevonden", "__version__"]
