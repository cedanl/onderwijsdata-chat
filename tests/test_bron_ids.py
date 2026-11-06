"""De chat herleidt ID's en datasleutels alleen via het ID-contract `bron:id` (#912, #914): één pad, geen vlag."""

from pathlib import Path

import pytest
import yaml

from tools import bron_ids, store


def test_het_contract_kent_ook_wat_de_oude_herleiding_niet_kende():
    """`roa:ais2030`: de herleiding van vóór #912 haalde alleen cbs/duo/rio als voorvoegsel weg."""
    assert bron_ids.bron_id("roa:ais2030") == "ais2030"


def test_elke_spelling_wordt_de_catalogusspelling():
    assert bron_ids.bron_id("cbs_85423ned") == "85423NED"
    assert bron_ids.bron_id("DUO:P01HOINGES") == "p01hoinges"
    assert bron_ids.cbs_tabel_id("71733NED") == "71733ned"
    assert bron_ids.cbs_tabel_id("p01hoinges") == "p01hoinges"  # een DUO-ID aan de CBS-toolgrens blijft zoals het is


@pytest.mark.parametrize(
    ("invoer", "verwacht"), [("duo:bestaat-niet", "bestaat-niet"), ("x:p01hoinges", "x:p01hoinges")]
)
def test_een_onbekend_id_blijft_staan_zonder_voorvoegsel(invoer, verwacht):
    """De tool meldt daarna zelf dat het ID onbekend is."""
    assert bron_ids.bron_id(invoer) == verwacht


@pytest.mark.parametrize(
    ("key", "bron"),
    [("rio:aangeboden-opleidingen:naam=x", "rio"), ("duo:p01hoinges:4", "duo"), ("analysis:abc", "analysis")],
)
def test_een_sleutel_zonder_metadata_noemt_zijn_bron_in_het_voorvoegsel(key, bron):
    store.clear()
    assert bron_ids.bron_van(key) == bron


def test_geen_omgeving_zet_de_vlag_van_voor_914_nog():
    """De vlag `BRON_ID_CONTRACT` bestaat in de code niet meer; geen omgeving zet hem nog."""
    root = Path(__file__).resolve().parent.parent
    for omgeving in ("test", "playground", "production", "development"):
        pad = root / "manifests" / omgeving / "values.yaml"
        if not pad.is_file():
            continue
        waarden = yaml.safe_load(pad.read_text(encoding="utf-8")) or {}
        assert "BRON_ID_CONTRACT" not in {e["name"] for e in waarden.get("env", [])}, omgeving
