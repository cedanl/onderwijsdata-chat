"""De sectormapping van de UWV-beroepenclusters is volledig en zegt eerlijk wat er niet van bekend is (#873).

De arbeidsmarktproxy rust op `data/sector_cluster_mapping.json`, een LLM-classificatie. Elk cluster uit de snapshot
heeft er een plaats: bij een of meer sectoren of in `_niet_toegewezen`. Model, prompt en validatie staan in het
manifest, ook als ze onbekend zijn of nog openstaan; de steekproef voor de handmatige beoordeling hoort bij de mapping.
"""

import csv
import io
import json

from data import arbeidsmarkt
from scripts import steekproef_sector_mapping as steekproef
from scripts.uwv_testfixture import lees as snapshotclusters


def _mapping() -> dict:
    return json.loads(arbeidsmarkt.SECTOR_CLUSTER_PATH.read_text(encoding="utf-8"))


def test_elk_cluster_uit_de_snapshot_staat_in_de_mapping():
    mapping = _mapping()
    toegewezen = {c for clusters in arbeidsmarkt.load_sector_cluster_map().values() for c in clusters}
    zonder_plaats = sorted(set(snapshotclusters()) - toegewezen - set(mapping["_niet_toegewezen"]))
    assert not zonder_plaats, f"clusters zonder sector en niet in _niet_toegewezen: {zonder_plaats}"


def test_niet_toegewezen_is_echt_zonder_sector_en_komt_uit_de_snapshot():
    niet_toegewezen = _mapping()["_niet_toegewezen"]
    toegewezen = {c for clusters in arbeidsmarkt.load_sector_cluster_map().values() for c in clusters}
    assert niet_toegewezen == sorted(niet_toegewezen)
    assert not set(niet_toegewezen) & toegewezen
    assert set(niet_toegewezen) <= set(snapshotclusters())


def test_het_manifest_noemt_model_prompt_en_validatie():
    manifest = _mapping()["_manifest"]
    assert manifest["model"] and manifest["prompt"]
    assert manifest["validatie"]["status"] == "open"
    assert manifest["validatie"]["steekproef"] == "docs/sector-cluster-steekproef.csv"


def test_de_steekproef_is_reproduceerbaar_en_hoort_bij_de_mapping():
    """Na een nieuwe mapping of snapshot: scripts/steekproef_sector_mapping.py opnieuw draaien."""
    assert steekproef.steekproef() == steekproef.steekproef()
    assert len(steekproef.steekproef()) == steekproef.AANTAL == 30
    # Alleen cluster en sectoren: het oordeel en de toelichting vult de beoordelaar in.
    assert _zonder_oordeel(steekproef.BESTAND.read_text(encoding="utf-8")) == _zonder_oordeel(steekproef.als_csv())


def _zonder_oordeel(tekst: str) -> list[list[str]]:
    return [rij[:3] for rij in csv.reader(io.StringIO(tekst), delimiter=";")]
