"""`from onderwijsbronnen.cbs import data` is altijd de functie, ook na een catalogusaanroep (#1104).

Het laden van de catalogusbestanden importeerde vroeger het subpakket `cbs/data/`, en dat overschreef het attribuut
`data` van `onderwijsbronnen.cbs`: de volgende CBS-snippet in hetzelfde proces gaf `'module' object is not callable`.
Elke regel draait in een eigen interpreter, zoals een notebook of pijplijn waarin de README-controle voor de snippet staat.
"""

import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).parent.parent / "src"


@pytest.mark.parametrize(
    "voorloop",
    [
        "pass",
        "o.cbs.catalog_manifest()",
        "o.cbs.catalog()",
        "o.cbs.catalog_records()",
        "o.normaliseer_bron_id('cbs_85423ned')",
        "o.catalogus()",
    ],
)
def test_data_is_na_een_catalogusaanroep_de_functie(voorloop):
    code = f"import onderwijsbronnen as o\n{voorloop}\nfrom onderwijsbronnen.cbs import data\nassert callable(data), type(data)"
    uit = subprocess.run(
        [sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(SRC)!r})\n{code}"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert uit.returncode == 0, uit.stderr


def test_de_catalogusbestanden_staan_niet_onder_de_naam_van_een_functie():
    """Een map naast `__init__.py` die heet als een functie van het pakket is dezelfde val."""
    import onderwijsbronnen.cbs as cbs

    map_namen = {p.name for p in Path(cbs.__file__).parent.iterdir() if p.is_dir()}
    assert not map_namen & set(cbs.__all__)
