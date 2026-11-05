"""Overgangsnaam: `onderwijsdata` heet nu `onderwijsbronnen.cbs` (#910). Weg in #914.

`import onderwijsdata` geeft de module `onderwijsbronnen.cbs` zelf (via `sys.modules`), geen kopie: elk attribuut,
ook een monkeypatch, is dat van de echte module. Dat houdt ook de bekende naambotsing gelijk: `from onderwijsdata import
data` vóór een catalogusaanroep is de functie, daarna wijst het attribuut `data` naar de datamap
(tests/test_bron_id_vormen.py in de chat). `onderwijsdata.client`, `.contract` en `.validatie` zijn de nieuwe modules.
"""

import sys
import warnings

from onderwijsbronnen import cbs
from onderwijsbronnen.cbs import *  # noqa: F403 — dezelfde namen ook voor een typechecker; runtime telt sys.modules
from onderwijsbronnen.cbs import client, contract, validatie

warnings.warn(
    "`onderwijsdata` heet nu `onderwijsbronnen.cbs`; de oude naam verdwijnt na de overgang (#914).",
    DeprecationWarning,
    stacklevel=2,
)

sys.modules.update({f"{__name__}.client": client, f"{__name__}.contract": contract, f"{__name__}.validatie": validatie})
sys.modules[__name__] = cbs
