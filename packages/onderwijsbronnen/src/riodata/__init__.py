"""Overgangsnaam: `riodata` heet nu `onderwijsbronnen` (#910). Weg in #914.

Een dunne re-export, geen eigen code: elk attribuut is hetzelfde object als in `onderwijsbronnen`, en elke oude
submodule (`riodata.duo`, `riodata.client`, ...) staat in `sys.modules` als de nieuwe module. Zo werken
`from riodata import duo`, `import riodata.duo` en `monkeypatch.setattr("riodata.duo.load", ...)` op precies de
module die de chat gebruikt. Nieuwe code gebruikt `onderwijsbronnen`; de importtest in de chat (test_importgrens)
staat de oude naam alleen in de shimtests en de nulmeting toe.

    riodata.catalog, duo, roa, uwv, inspectie  ->  onderwijsbronnen.catalog, .duo, .roa, .uwv, .inspectie
    riodata.fetch, get, related, client, …      ->  onderwijsbronnen.rio
    riodata.sbb, crebo, sbb_xml                 ->  onderwijsbronnen.sbb, .sbb.crebo, .sbb.dossiers
"""

import sys
import warnings

from onderwijsbronnen import (
    AmbigueResource,
    ResourceNietGevonden,
    __version__,
    catalog,
    contract,
    duo,
    inspectie,
    roa,
    sbb,
    scope,
    uwv,
)
from onderwijsbronnen._kern import lezen as _lezen
from onderwijsbronnen._kern import resolutie as _resolutie
from onderwijsbronnen._kern import verrijking as _catalog
from onderwijsbronnen.duo import notes as duo_notes
from onderwijsbronnen.rio import (
    Stap,
    _filtercontract,
    aanbieders,
    client,
    fetch,
    filtercontract,
    get,
    onderwijsaanbieders,
    opvolgers,
    overgangen,
    related,
    typewaarden,
    valideer_filters,
    voorgangers,
)
from onderwijsbronnen.sbb import crebo
from onderwijsbronnen.sbb import dossiers as sbb_xml

warnings.warn(
    "`riodata` heet nu `onderwijsbronnen` (RIO in onderwijsbronnen.rio, DUO in onderwijsbronnen.duo, ...); "
    "de oude naam verdwijnt na de overgang (#914).",
    DeprecationWarning,
    stacklevel=2,
)

# De oude submodulepaden wijzen naar de nieuwe modules, zodat `import riodata.duo` geen tweede kopie laadt.
SUBMODULES = {
    "duo": duo,
    "roa": roa,
    "uwv": uwv,
    "inspectie": inspectie,
    "sbb": sbb,
    "crebo": crebo,
    "sbb_xml": sbb_xml,
    "contract": contract,
    "scope": scope,
    "client": client,
    "overgangen": overgangen,
    "aanbieders": aanbieders,
    "duo_notes": duo_notes,
    "_catalog": _catalog,
    "_filtercontract": _filtercontract,
    "_lezen": _lezen,
    "_resolutie": _resolutie,
}
sys.modules.update({f"{__name__}.{naam}": module for naam, module in SUBMODULES.items()})

__all__ = ["fetch", "get", "related", "catalog", "filtercontract", "typewaarden", "valideer_filters", "duo", "roa",
           "uwv", "inspectie", "sbb", "crebo", "contract", "opvolgers", "voorgangers", "Stap", "onderwijsaanbieders",
           "AmbigueResource",
           "ResourceNietGevonden", "__version__"]
